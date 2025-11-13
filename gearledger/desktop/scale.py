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
    returns the last parsed weight line.
    """
    try:
        with serial.Serial(port=port, baudrate=baudrate, timeout=0.2) as ser:
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

                # prefer non-zero
                val_str = w.split()[0]
                try:
                    val = float(val_str)
                except ValueError:
                    val = None

                if val is None:
                    continue

                if last is None or val != 0.0:
                    last = w
            return last
    except Exception:
        return None
