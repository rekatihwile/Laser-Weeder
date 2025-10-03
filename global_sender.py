# file: laser_global_sender.py
import serial
from typing import Optional

# Barebones: one public function.
# coords can be a dict like {"x": 10.0, "y": 5.5} or {"x": 10, "z": -2}
# feed is mm/min
def send_global_move(
    port: str,
    coords: dict,
    feed: float = 2000.0,          # feed (used only with G1)
    baud: int = 115200,
    timeout: float = 0.0,         # non-blocking reads
    rapid: bool = True,           # default to G0 (fastest)
    wait_for_ok: bool = False,    # keep off by default (fastest)
    port_ser: Optional[serial.Serial] = None  # optional existing open serial port to use
):
    """
    Open serial, ensure absolute/mm, and send a single global move (G1).
    Example:
        send_global_move("COM5", {"x": 10, "y": 20}, feed=800)

    Parameters
    ----------
    port : str
        Serial port name (e.g., "COM5" on Windows or "/dev/ttyUSB0" on Linux).
    coords : dict
        Any subset of {"x","y","z"} with numeric values. (e.g., {"x": 10, "y": 20})
    feed : float
        Feed rate in mm/min.
    baud : int
        Baud rate for the controller.
    timeout : float
        Serial read timeout, seconds.
    """
    if not coords or not any(k in coords for k in ("x", "y", "z")):
        raise ValueError("coords must contain at least one of 'x', 'y', or 'z'.")

    # Build the G1 line using only provided axes, formatted nicely.
    axes = []
    if "x" in coords: axes.append(f"X{float(coords['x']):.3f}")
    if "y" in coords: axes.append(f"Y{float(coords['y']):.3f}")
    if "z" in coords: axes.append(f"Z{float(coords['z']):.3f}")
    g1_line = f"G1 {' '.join(axes)} F{float(feed):.3f}"

    ser = None
    close_ser = False
    try:
        # Use provided serial handle if given, otherwise open our own
        if port_ser is not None:
            ser = port_ser
        else:
            try:
                ser = serial.Serial(port, baudrate=baud, timeout=timeout, write_timeout=0.1)
            except PermissionError as e:
                raise PermissionError(f"Could not open port '{port}': {e}. If another program already has the port open, pass that Serial object into send_global_move as 'port_ser'.") from e
            close_ser = True

        # Put controller into absolute/mm (harmless if already set)
        try:
            ser.write(b"G90\n")
            ser.write(b"G21\n")
        except Exception:
            pass

        cmd = "G0" if rapid else "G1"
        full_line = f"{cmd} {' '.join(axes)}" + ("" if rapid else f" F{float(feed):.3f}")

        # If we opened the port ourselves, assert laser-off quickly before closing later.
        if close_ser:
            try:
                ser.write(b"M5\n")
            except Exception:
                pass

        # Send move
        ser.write((full_line + "\n").encode("ascii", "ignore"))

        # Optionally wait briefly for an 'ok' if requested
        if wait_for_ok:
            deadline = time.time() + 0.2
            while time.time() < deadline:
                try:
                    line = ser.readline().decode("utf-8", errors="ignore").strip()
                except Exception:
                    break
                if not line:
                    continue
                print(f"<< {line}")
                if line.lower().startswith("ok"):
                    break

    finally:
        # only close (and send M5) if we opened the serial ourselves
        if close_ser and ser and getattr(ser, "is_open", False):
            try:
                ser.write(b"M5\n")
            except Exception:
                pass
            try:
                ser.close()
            except Exception:
                pass


# Optional small CLI for ad-hoc testing:
#   python laser_global_sender.py COM5 10 20    -> X=10 Y=20
#   python laser_global_sender.py COM5 10 20 -2 -> X=10 Y=20 Z=-2
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 4:
        print("Usage: python laser_global_sender.py COMx X Y [Z]")
        sys.exit(1)

    port = sys.argv[1]
    x = float(sys.argv[2])
    y = float(sys.argv[3])
    z = float(sys.argv[4]) if len(sys.argv) > 4 else None

    coords = {"x": x, "y": y}
    if z is not None:
        coords["z"] = z

    # Example: use rapid=True for fastest travel or increase feed as needed
    send_global_move(port, coords)
    # Example: use rapid=True for fastest travel or increase feed as needed
    send_global_move(port, coords)
