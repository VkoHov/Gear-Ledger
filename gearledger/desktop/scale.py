import re, time
import serial
from typing import Optional

# very generic line parser: "1.234 kg" or "1234 g" or just "1.234"
PAT = re.compile(
    r"([-+]?\d+(?:[.,]\d+)?)\s*(kg|g|lb|oz)?",
    re.I,
)


def parse_weight(line: str) -> Optional[str]:
    m = PAT.search(line)
    if not m:
        return None
    val, unit = m.group(1), m.group(2) or ""
    val = val.replace(",", ".")  # normalize comma → dot
    unit = unit.lower()
    return f"{val} {unit}".strip()


def read_weight_once(port: str, baudrate=9600, timeout=10.0) -> Optional[str]:
    """
    Opens the serial port, reads for up to `timeout` seconds,
    returns the last parsed weight line. Closes the port before returning.
    """
    try:
        with serial.Serial(port=port, baudrate=baudrate, timeout=0.2) as ser:
            return _read_weight_loop(ser, timeout)
    except Exception:
        return None


def open_and_read_weight_once(port: str, baudrate=9600, timeout=10.0):
    """
    Opens the serial port and reads for up to `timeout` seconds, like
    read_weight_once, but leaves the connection OPEN and returns it instead
    of closing it — so the same connection used for this initial test can
    go straight into continuous monitoring, with no close-then-reopen step
    in between. Some USB-serial adapters fail to reconfigure reliably when
    reopened immediately after being closed, so avoiding that step entirely
    is more robust than closing and retrying.

    Returns (weight_str_or_None, serial.Serial_or_None). If the port itself
    can't be opened, returns (None, None) — there's nothing for the caller
    to hold onto or close in that case.
    """
    try:
        ser = serial.Serial(port=port, baudrate=baudrate, timeout=0.2)
    except Exception:
        return None, None

    try:
        return _read_weight_loop(ser, timeout), ser
    except Exception:
        # Port opened fine but something went wrong while reading — still
        # hand back the open connection, since it's usable for monitoring.
        return None, ser


def _read_weight_loop(ser, timeout: float) -> Optional[str]:
    end_time = time.time() + timeout
    last = None
    while time.time() < end_time:
        raw = ser.readline().decode(errors="ignore").strip()
        print(f"Scale raw: {raw}")

        if not raw:
            continue
        if "/" in raw:
            continue

        w = parse_weight(raw)
        if not w:
            continue

        val_str = w.split()[0]
        try:
            val = float(val_str)
        except ValueError:
            val = None

        if val is None:
            continue

        # Prefer non-zero values, but keep last non-zero if current is zero
        if val != 0.0:
            last = w
        elif last is None:
            # Only use zero if we haven't seen any value yet
            last = w
    return last
