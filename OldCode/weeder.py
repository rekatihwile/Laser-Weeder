from global_sender import send_global_move
import threading
import cv2
import sys
import serial
import keyboard
import time

# This script runs a camera preview and a background input thread.
# Input format examples:
#   100 200         -> X=100 Y=200
#   100 200 -5      -> X=100 Y=200 Z=-5
#   quit / exit / q -> stop preview and exit

CAMERA_ID = 0  # preferred start index; function will probe 0..3 if this fails
PORT = "COM3"   # change as needed

# Local movement settings (used for arrow-key control via G91)
STEP_SIZE = 0.5            # mm per interval (smaller step for smoother motion)
FEED_RATE = 1000           # mm/min for local moves
RELATIVE_SEND_INTERVAL = 0.04   # seconds between relative move packets (~25Hz)
RELATIVE_END_TIMEOUT = 0.18     # seconds of no keys before switching back to G90

# persistent relative-mode state to avoid repeated G91/G90 toggles
relative_active = False
last_relative_send = 0.0

# Tracked absolute coordinates (updated by global sends and local relative moves)
coords_lock = threading.Lock()
current_x = 0.0
current_y = 0.0
current_z = 0.0

# Local serial port used for G91/G90 relative moves (opened once)
local_ser = None
def open_local_serial(port_name=PORT, baud=115200):
    global local_ser
    try:
        local_ser = serial.Serial(port_name, baudrate=baud, timeout=0.1, write_timeout=0.1)
        # ensure absolute/mm at start, we will switch to G91 for local moves as needed
        try:
            local_ser.write(b"G90\n")
            local_ser.write(b"G21\n")
        except Exception:
            pass
        print(f"Local serial opened on {port_name}")
    except Exception as e:
        local_ser = None
        print(f"Warning: could not open local serial on {port_name}: {e}")

def safe_local_write(line: str):
    """Write raw line to the local serial if available."""
    if not local_ser:
        return False
    try:
        local_ser.write((line + "\n").encode("ascii", "ignore"))
        return True
    except Exception as e:
        print(f"Local serial write error: {e}")
        return False

def handle_arrow_keys():
    """Continuous (smoother) arrow-key handling: send relative moves at a steady rate while keys held."""
    global current_x, current_y, current_z, relative_active, last_relative_send
    now = time.time()
    # read current pressed keys (allow diagonals)
    up = keyboard.is_pressed("up")
    down = keyboard.is_pressed("down")
    left = keyboard.is_pressed("left")
    right = keyboard.is_pressed("right")
    pageup = keyboard.is_pressed("page up")
    pagedown = keyboard.is_pressed("page down")

    dx = dy = dz = 0.0
    if up and not down:
        dy += STEP_SIZE
    if down and not up:
        dy -= STEP_SIZE
    if right and not left:
        dx += STEP_SIZE
    if left and not right:
        dx -= STEP_SIZE
    if pageup and not pagedown:
        dz += STEP_SIZE
    if pagedown and not pageup:
        dz -= STEP_SIZE

    any_key = (dx != 0.0) or (dy != 0.0) or (dz != 0.0)

    if any_key:
        # enter relative mode once
        if not relative_active:
            if local_ser:
                safe_local_write("G91")
            relative_active = True
            # force immediate send
            last_relative_send = 0.0

        # send at configured interval
        if now - last_relative_send >= RELATIVE_SEND_INTERVAL:
            last_relative_send = now
            if local_ser:
                # send one relative step (G1)
                safe_local_write(f"G1 X{dx:.3f} Y{dy:.3f} Z{dz:.3f} F{FEED_RATE}")
            else:
                # fallback to absolute global send (slower)
                with coords_lock:
                    px, py, pz = current_x, current_y, current_z
                try:
                    send_global_move(PORT, {"x": px + dx, "y": py + dy, "z": pz + dz}, rapid=True, wait_for_ok=False)
                except Exception as e:
                    print(f"Error (fallback) sending move: {e}")
            # update tracked absolute coords
            with coords_lock:
                current_x += dx
                current_y += dy
                current_z += dz
            return True
    else:
        # no key pressed; if currently in relative mode and idle time passed, switch back to absolute
        if relative_active and (now - last_relative_send) >= RELATIVE_END_TIMEOUT:
            if local_ser:
                safe_local_write("G90")
            relative_active = False
        return False

stop_event = threading.Event()

# Helper used by main to print coordinates when they change
def print_coords_once(prev):
    """Return new prev tuple after printing when coords changed."""
    with coords_lock:
        cur = (current_x, current_y, current_z)
    if cur != prev:
        print(f"Position -> X:{cur[0]:.3f} Y:{cur[1]:.3f} Z:{cur[2]:.3f}")
    return cur

def input_loop():
    """Background thread: read coordinates from terminal and call send_global_move."""
    # allow updating the tracked absolute coordinates
    global current_x, current_y, current_z, local_ser
    print("Enter moves as: X Y [Z]   (e.g. 120 200  or  120 200 -5). Type 'quit' to exit.")
    while not stop_event.is_set():
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            stop_event.set()
            break

        if not line:
            continue

        if line.lower() in ("quit", "exit", "q"):
            stop_event.set()
            break

        parts = line.replace(",", " ").split()
        try:
            if len(parts) < 2:
                print("Need at least X and Y. Format: X Y [Z]")
                continue
            x = float(parts[0]) 
            y = float(parts[1])
            coords = {"x": x, "y": y}
            if len(parts) >= 3:
                coords["z"] = float(parts[2])
            # Non-blocking send (send_global_move opens port, sends, returns)
            try:
                # If we already have local_ser open, reuse it to avoid PermissionError on COM port
                if local_ser:
                    send_global_move(PORT, coords, rapid=True, wait_for_ok=False, port_ser=local_ser)
                else:
                    send_global_move(PORT, coords, rapid=True, wait_for_ok=False)
                # update tracked absolute coords to what we commanded
                with coords_lock:
                    current_x = coords.get("x", current_x)
                    current_y = coords.get("y", current_y)
                    current_z = coords.get("z", current_z)
                print(f"Sent move to {coords}")
            except Exception as e:
                print(f"Error sending move: {e}")
        except ValueError:
            print("Could not parse numbers. Use: X Y [Z]")

def main():
    # Start input thread
    open_local_serial(PORT)    # attempt to open local serial for G91 moves
    try:
        keyboard.start_recording() # allow is_pressed checks
    except Exception:
        # keyboard library may require elevated privileges on some platforms; continue anyway
        pass
    t = threading.Thread(target=input_loop, daemon=True)
    t.start()
    # Try to open a working camera. Probe a few indices and (on Windows) DirectShow backend.
    def open_camera(preferred=CAMERA_ID, max_index_probe=4):
        backends = []
        if sys.platform.startswith("win"):
            # DirectShow often works better on Windows for many webcams
            backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF]
        # probe preferred first, then 0..max_index_probe-1
        indices = [preferred] + [i for i in range(0, max_index_probe) if i != preferred]
        for idx in indices:
            for backend in backends + [None]:
                try:
                    if backend is None:
                        cap = cv2.VideoCapture(idx)
                    else:
                        cap = cv2.VideoCapture(idx, backend)
                    if cap is None:
                        continue
                    if cap.isOpened():
                        print(f"Opened camera index {idx} (backend={backend})")
                        return cap, idx, backend
                    cap.release()
                except Exception:
                    # ignore and try next
                    try:
                        cap.release()
                    except Exception:
                        pass
        return None, None, None

    cap, used_idx, used_backend = open_camera()
    if cap is None or not cap.isOpened():
        print("ERROR: Could not open any camera (tried indices 0..3).")
        stop_event.set()
        t.join()
        return

    window = "Camera Preview - press q or ESC to quit"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)

    prev_coords = (None, None, None)
    while not stop_event.is_set():
        # camera frame
        ret, frame = cap.read()
        if not ret:
            print("ERROR: camera read failed")
            break

        cv2.imshow(window, frame)

        # handle arrow keys (non-blocking)
        moved = handle_arrow_keys()
        if moved:
            prev_coords = print_coords_once(prev_coords)

        # update coords print even if no recent move (when global sends happen)
        prev_coords = print_coords_once(prev_coords)

        key = cv2.waitKey(30) & 0xFF
        if key == ord('q') or key == 27:
            stop_event.set()
            break

    cap.release()
    cv2.destroyAllWindows()
    t.join()
    # cleanup local serial
    try:
        if local_ser and local_ser.is_open:
            local_ser.write(b"M5\n")
            local_ser.close()
    except Exception:
        pass

if __name__ == "__main__":
    main()
