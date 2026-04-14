"""Async LX200 protocol client — no Home Assistant dependencies.

Author: Justin Aarden
GitHub: https://github.com/Jaarden/HA-LX200-OnStep
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass

from .const import CONNECT_TIMEOUT, CMD_TIMEOUT

# ---------------------------------------------------------------------------
# Slew rate options (label → OnStep LX200 command)
# ---------------------------------------------------------------------------

SLEW_RATES: dict[str, str] = {
    "0.5x":  ":R1#",
    "1x":    ":R2#",
    "2x":    ":R3#",
    "4x":    ":R4#",
    "8x":    ":R5#",
    "20x":   ":R6#",
    "48x":   ":R7#",
    "Max":   ":R9#",
}


class CannotConnect(Exception):
    """Raised when the TCP connection to the mount fails."""


@dataclass
class TelescopeData:
    ra: float | None
    dec: float | None
    altitude: float | None
    azimuth: float | None
    lst: str | None
    tracking: bool | None   # None = unknown / firmware did not respond
    parked: bool | None     # None = unknown / firmware did not respond
    park_status: str | None # Human-readable park state from :GU#
    local_time: str | None  # Local time HH:MM:SS from :GL#
    guiding: bool | None    # True when mount is guiding/tracking (:GU# 'G' flag)
    ra_hms: str | None      # RA formatted as "HHh MMm SS.SSs"
    dec_dms: str | None     # DEC formatted as "+DD° MM' SS.SS\""
    tracking_rate: str | None  # "Sidereal", "Lunar", "Solar", or None


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _hours_to_hms(h: float) -> str:
    """Convert decimal hours to a 'HHh MMm SS.SSs' string."""
    hh = int(h)
    mm = int((h - hh) * 60)
    ss = ((h - hh) * 60 - mm) * 60
    return f"{hh:02d}h {mm:02d}m {ss:05.2f}s"


def _deg_to_dms(deg: float) -> str:
    """Convert decimal degrees to a '+DD° MM′ SS.SS″' string."""
    sign = "-" if deg < 0 else "+"
    d = abs(deg)
    dd = int(d)
    mn = int((d - dd) * 60)
    ss = ((d - dd) * 60 - mn) * 60
    return f"{sign}{dd:02d}\u00b0 {mn:02d}\u2032 {ss:05.2f}\u2033"


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _parse_ra(raw: str) -> float | None:
    """Parse LX200 RA string to decimal hours."""
    raw = raw.strip().rstrip("#")
    # High precision  HH:MM:SS
    m = re.match(r"^(\d{1,2}):(\d{2}):(\d{2})$", raw)
    if m:
        return int(m.group(1)) + int(m.group(2)) / 60 + int(m.group(3)) / 3600
    # Low precision  HH:MM.T
    m = re.match(r"^(\d{1,2}):(\d{2})\.(\d)$", raw)
    if m:
        return int(m.group(1)) + (int(m.group(2)) + int(m.group(3)) / 10) / 60
    return None


def _parse_dms(raw: str) -> float | None:
    """Parse LX200 DEC / Alt / Az string to decimal degrees."""
    raw = raw.strip().rstrip("#")
    sign = -1 if raw.startswith("-") else 1
    raw = re.sub(r"^[+\-]", "", raw)
    raw = raw.replace("*", ":").replace("°", ":").replace("'", ":").replace('"', "")
    parts = raw.split(":")
    try:
        d  = int(parts[0])
        mn = int(parts[1]) if len(parts) > 1 else 0
        s  = float(parts[2]) if len(parts) > 2 else 0.0
        return sign * (d + mn / 60 + s / 3600)
    except (ValueError, IndexError):
        return None


def _parse_park_status(raw: str | None) -> str | None:
    """
    Return a human-readable park status from the :GU# response.

    OnStep flag characters:
      'I' = Parking in progress
      'F' = Park failed
      'P' = Parked
      'p' = Not parked
    """
    if not raw:
        return None
    s = raw.strip()
    if "I" in s:
        return "Parking"
    if "F" in s:
        return "Park failed"
    if "P" in s and "p" not in s:
        return "Parked"
    if "p" in s:
        return "Not parked"
    return None


def _parse_parked(raw: str | None) -> bool | None:
    """
    Determine park state (boolean) from the :GU# response.
    Derived from _parse_park_status — True only when fully parked.
    """
    status = _parse_park_status(raw)
    if status == "Parked":
        return True
    if status in ("Not parked", "Park failed", "Parking"):
        return False
    return None


def _parse_guiding(raw: str | None) -> bool | None:
    """
    Determine guiding/tracking state from the :GU# response.

    OnStep uses 'G' to indicate guiding (tracking corrections) in progress.
    Returns True when guiding, False when not, None when unknown.
    """
    if not raw:
        return None
    return "G" in raw.strip()


# Nominal LX200 tracking rates and midpoint classification thresholds (Hz)
_SIDEREAL_HZ = 60.164
_LUNAR_HZ    = 57.900
_SOLAR_HZ    = 59.958
_LUNAR_SOLAR_THRESH    = (_LUNAR_HZ + _SOLAR_HZ) / 2      # ≈ 58.93
_SOLAR_SIDEREAL_THRESH = (_SOLAR_HZ + _SIDEREAL_HZ) / 2   # ≈ 60.06


def _parse_tracking_rate(raw: str | None) -> str | None:
    """
    Parse the :GT# response and classify the tracking rate.

    :GT# returns the tracking drive frequency in Hz.
    Nominal values: Sidereal ≈ 60.164, Solar ≈ 59.958, Lunar ≈ 57.900.
    Returns None when the response is missing or unparseable.
    """
    if not raw:
        return None
    try:
        hz = float(raw.strip())
    except ValueError:
        return None
    if hz <= 0.0:
        return "Off"
    if hz < _LUNAR_SOLAR_THRESH:
        return "Lunar"
    if hz < _SOLAR_SIDEREAL_THRESH:
        return "Solar"
    return "Sidereal"


def _parse_tracking(raw: str | None) -> bool | None:
    """
    The :GU# status response does not include a distinct tracking on/off flag.
    Tracking state is managed optimistically in the switch entity.
    Always returns None so the switch falls back to its optimistic state.
    """
    return None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _open(host: str, port: int):
    """Open a TCP connection, raising CannotConnect on failure."""
    try:
        return await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=CONNECT_TIMEOUT,
        )
    except (OSError, asyncio.TimeoutError) as exc:
        raise CannotConnect(f"Cannot connect to {host}:{port}: {exc}") from exc


async def _close(writer) -> None:
    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Public API — queries
# ---------------------------------------------------------------------------

async def query_mount(host: str, port: int) -> TelescopeData:
    """
    Open a TCP connection to an LX200-compatible mount, fetch all
    coordinates and status, and return a TelescopeData dataclass.

    Raises CannotConnect on network errors.
    """
    reader, writer = await _open(host, port)

    async def send(cmd: str, has_response: bool = True) -> str | None:
        writer.write(cmd.encode("ascii"))
        await writer.drain()
        if not has_response:
            return None
        try:
            data = await asyncio.wait_for(
                reader.readuntil(b"#"), timeout=CMD_TIMEOUT
            )
            return data.decode("ascii", errors="replace").rstrip("#").strip()
        except (asyncio.TimeoutError, asyncio.IncompleteReadError):
            return None

    try:
        # Ensure high-precision mode
        ra_raw = await send(":GR#")
        if ra_raw and ra_raw.count(":") < 2:
            await send(":U#", has_response=False)
            ra_raw = await send(":GR#")

        dec_raw        = await send(":GD#")
        alt_raw        = await send(":GA#")
        az_raw         = await send(":GZ#")
        lst_raw        = await send(":GS#")
        time_raw       = await send(":GL#")   # Local time HH:MM:SS
        tracking_raw   = await send(":GU#")   # OnStep status — includes park flags
        track_rate_raw = await send(":GT#")   # Tracking rate in Hz
    finally:
        await _close(writer)

    ra  = _parse_ra(ra_raw   or "")
    dec = _parse_dms(dec_raw  or "")
    alt = _parse_dms(alt_raw  or "")
    az  = _parse_dms(az_raw   or "")

    ra_rounded  = round(ra,  6) if ra  is not None else None
    dec_rounded = round(dec, 6) if dec is not None else None

    return TelescopeData(
        ra       = ra_rounded,
        dec      = dec_rounded,
        altitude = round(alt, 4) if alt is not None else None,
        azimuth  = round(az,  4) if az  is not None else None,
        lst      = lst_raw or None,
        tracking    = _parse_tracking(tracking_raw),
        parked      = _parse_parked(tracking_raw),
        park_status = _parse_park_status(tracking_raw),
        local_time  = time_raw or None,
        guiding        = _parse_guiding(tracking_raw),
        ra_hms         = _hours_to_hms(ra_rounded) if ra_rounded  is not None else None,
        dec_dms        = _deg_to_dms(dec_rounded)  if dec_rounded is not None else None,
        tracking_rate  = _parse_tracking_rate(track_rate_raw),
    )


# ---------------------------------------------------------------------------
# Public API — controls
# ---------------------------------------------------------------------------

async def sync_time(host: str, port: int, date_str: str, time_str: str) -> None:
    """
    Send date and time to the mount over a single TCP connection.

    date_str: MM/DD/YY  (e.g. "04/13/26")
    time_str: HH:MM:SS  (e.g. "21:30:00")
    Raises CannotConnect on network errors.
    """
    reader, writer = await _open(host, port)
    try:
        async def send_expect(cmd: str) -> str | None:
            writer.write(cmd.encode("ascii"))
            await writer.drain()
            try:
                data = await asyncio.wait_for(
                    reader.readuntil(b"#"), timeout=CMD_TIMEOUT
                )
                return data.decode("ascii", errors="replace").rstrip("#").strip()
            except (asyncio.TimeoutError, asyncio.IncompleteReadError):
                return None

        await send_expect(f":SC{date_str}#")
        await send_expect(f":SL{time_str}#")
    finally:
        await _close(writer)


async def send_control(host: str, port: int, cmd: str) -> str | None:
    """
    Send a single LX200 control command and return any response.

    Most motion / rate commands produce no response; this function waits
    briefly and returns whatever the mount sends back (or None).
    Raises CannotConnect on network errors.
    """
    reader, writer = await _open(host, port)
    try:
        writer.write(cmd.encode("ascii"))
        await writer.drain()
        try:
            data = await asyncio.wait_for(
                reader.readuntil(b"#"), timeout=CMD_TIMEOUT
            )
            return data.decode("ascii", errors="replace").rstrip("#").strip()
        except (asyncio.TimeoutError, asyncio.IncompleteReadError):
            return None
    finally:
        await _close(writer)
