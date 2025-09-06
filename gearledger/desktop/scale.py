import re, time
import serial

# very generic line parser: "1.234 kg" or "1234 g" or just "1.234"
PAT = re.compile(r"([-+]?\d+(?:\.\d+)?)\s*(kg|g|lb|oz)?", re.I)


def parse_weight(line: str) -> str | None:
    m = PAT.search(line)
    if not m:
        return None
    val, unit = m.group(1), m.group(2) or ""
    unit = unit.lower()
    return f"{val} {unit}".strip()


def read_weight_once(port: str, baudrate=9600, timeout=2.0) -> str | None:
    """
    Opens the serial port, reads for up to `timeout` seconds,
    returns the last parsed weight line.
    """
    try:
        with serial.Serial(port=port, baudrate=baudrate, timeout=0.2) as ser:
            end_time = time.time() + timeout
            last = None
            while time.time() < end_time:
                raw = ser.readline().decode(errors="ignore").strip()
                if not raw:
                    continue
                w = parse_weight(raw)
                if w:
                    last = w
            return last
    except Exception:
        return None
