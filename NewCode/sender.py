# make_grid_handshake.py
import time, serial, numpy as np

PORT = "COM3"
BAUD = 115200

x0, y0    = 0.0, 0.0
xmax, ymax = 450.0, 440.0
nx, ny    = 10, 9           # points per axis (includes endpoints)

travel_F  = 8000
power_S   = 100              # 0..$30 (we set $30=1000 below)
dwell_s   = 0.07              # seconds
HOME_FIRST = True
DRY_RUN = True              # True = just move, no burn (useful to test counts)

def send(ser, line):
    ser.write((line + "\r\n").encode())
    ser.flush()
    # Read until we see an 'ok' (or 'error') from GRBL
    while True:
        resp = ser.readline()
        if not resp:
            # some firmwares are quiet; tiny pause avoids busy-loop
            time.sleep(0.001)
            continue
        if b"ok" in resp or b"error" in resp:
            break

def main():
    ser = serial.Serial(PORT, baudrate=BAUD, timeout=0.2, write_timeout=0.2)
    time.sleep(0.2)

    send(ser, "M5")         # laser off
    send(ser, "$X")         # unlock
    if HOME_FIRST:
        send(ser, "$H")     # home
    send(ser, "$32=0")      # laser mode OFF (allow dwell burns)
    send(ser, "$30=1000")   # power scale 0..1000
    send(ser, "G21")        # mm
    send(ser, "G90")        # absolute
    send(ser, "S0")

    xs = np.linspace(x0,   xmax, nx)
    ys = np.linspace(y0,   ymax, ny)

    idx = 0
    for j, Y in enumerate(ys):
        for i, X in enumerate(xs):
            idx += 1
            # move there with laser OFF
            send(ser, f"G0 X{X:.3f} Y{Y:.3f} F{travel_F}")
            if not DRY_RUN:
                send(ser, f"M3 S{power_S}")
                send(ser, f"G4 P{dwell_s:.3f}")
                send(ser, "M5")
            time.sleep(0.1)  # small delay to ensure command processing

    send(ser, f"G0 X{x0:.3f} Y{y0:.3f}")
    send(ser, "M5")
    ser.close()
    print(f"Done. Burned {idx} points ({nx} x {ny}).")

if __name__ == "__main__":
    main()
