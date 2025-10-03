import sys, time
import serial
import keyboard
import threading

# Usage: python sender.py COM5
# (Assumes 115200 baud; change if your controller uses something else.)

if len(sys.argv) < 2:
    print("Usage: python sender.py COMx")
    sys.exit(1)

port = sys.argv[1]
print(f"Connected to {port}")

# Open serial, no handshake, no reads.
ser = serial.Serial(port, baudrate=115200, timeout=0.1)

# OPTIONAL: unlock if you *know* you need it (comment out if unsure)
# ser.write(b"$X\n")
# time.sleep(0.1)

# Set up coordinate system
ser.write(b"G90\n")  # Absolute positioning
ser.write(b"G21\n")  # Millimeter units
time.sleep(0.1)

# Movement settings
STEP_SIZE = 1.0  # mm per arrow key press
FEED_RATE = 1000  # mm/min

# Track current position and key states
current_x = 0.0
current_y = 0.0
current_z = 0.0
last_key_time = {}

# NEW: mode: "local" = arrow keys, "global" = manual G-code input
mode = "local"
# NEW: entering GLOBAL via Enter can produce an immediate blank line; ignore it once
ignore_next_input = False

# Serial reading thread
def serial_reader():
    """Continuously read from serial port and print incoming data"""
    while True:
        try:
            if ser.in_waiting > 0:
                data = ser.readline().decode('utf-8', errors='ignore').strip()
                if data:
                    # Print serial messages cleanly and flush so they don't interleave badly with input()
                    print(f"\n<< {data}", flush=True)
                    # Helpful hint if the controller is in alarm state
                    if "ALARM" in data.upper():
                        print("<< Detected ALARM state from controller. In GLOBAL mode you can send '$X' to unlock (type 'unlock').", flush=True)
        except Exception as e:
            if ser.is_open:
                print(f"Serial read error: {e}", flush=True)
        time.sleep(0.01)

# Start serial reading thread
reader_thread = threading.Thread(target=serial_reader, daemon=True)
reader_thread.start()

print("Enter G-code commands (press Enter to switch to GLOBAL/manual mode, type '~' alone to return to LOCAL/arrow-key mode):")
print("Arrow keys: Move X/Y axis (LOCAL mode)")
print("Page Up/Down: Move Z axis up/down (LOCAL mode)")
print("+ / -: Increase/decrease step size")
print(f"Current step size: {STEP_SIZE}mm")
print("Serial responses will appear with << prefix")
print("In GLOBAL mode, type 'exit' or 'quit' to stop the program.")

def send_movement(command):
    """Send movement command to the controller"""
    full_command = f"G1 {command} F{FEED_RATE}"
    print(f"Sending: {full_command}")
    ser.write((full_command + "\n").encode("ascii", "ignore"))
    time.sleep(0.01)

def handle_arrow_keys():
    """Handle arrow key movement with debounce (relative movement using G91)"""
    global STEP_SIZE, last_key_time

    current_time = time.time()
    debounce_delay = 0.001  # 100ms debounce

    def send_relative_movement(command):
        """Send a relative movement command using G91/G90 switching"""
        ser.write(b"G91\n")  # Switch to relative positioning
        send_movement(command)
        ser.write(b"G90\n")  # Switch back to absolute positioning
      

    if keyboard.is_pressed('up') and current_time - last_key_time.get('up', 0) > debounce_delay:
        send_relative_movement(f"Y{STEP_SIZE}")
        last_key_time['up'] = current_time
    elif keyboard.is_pressed('down') and current_time - last_key_time.get('down', 0) > debounce_delay:
        send_relative_movement(f"Y{-STEP_SIZE}")
        last_key_time['down'] = current_time
    elif keyboard.is_pressed('left') and current_time - last_key_time.get('left', 0) > debounce_delay:
        send_relative_movement(f"X{-STEP_SIZE}")
        last_key_time['left'] = current_time
    elif keyboard.is_pressed('right') and current_time - last_key_time.get('right', 0) > debounce_delay:
        send_relative_movement(f"X{STEP_SIZE}")
        last_key_time['right'] = current_time
    elif keyboard.is_pressed('page up') and current_time - last_key_time.get('page_up', 0) > debounce_delay:
        send_relative_movement(f"Z{STEP_SIZE}")
        last_key_time['page_up'] = current_time
    elif keyboard.is_pressed('page down') and current_time - last_key_time.get('page_down', 0) > debounce_delay:
        send_relative_movement(f"Z{-STEP_SIZE}")
        last_key_time['page_down'] = current_time
    elif keyboard.is_pressed('+') or keyboard.is_pressed('='):
        if current_time - last_key_time.get('plus', 0) > 0.2:
            STEP_SIZE = min(STEP_SIZE + 1.0, 100.0)
            print(f"Step size: {STEP_SIZE:.1f}mm")
            last_key_time['plus'] = current_time
    elif keyboard.is_pressed('-'):
        if current_time - last_key_time.get('minus', 0) > 0.2:
            STEP_SIZE = max(STEP_SIZE - 1.0, 0.1)
            print(f"Step size: {STEP_SIZE:.1f}mm")
            last_key_time['minus'] = current_time

try:
    # Start keyboard monitoring in background
    keyboard.start_recording()
    
    while True:
        if mode == "local":
            # Arrow key handling only in local mode
            handle_arrow_keys()
            time.sleep(0.01)  # Small delay to allow key state changes
            # Detect Enter to switch to global/manual mode (debounced)
            current_time = time.time()
            if keyboard.is_pressed('enter') and current_time - last_key_time.get('enter', 0) > .01:
                mode = "global"
                ignore_next_input = True     # avoid processing the Enter that triggered the switch as an empty command
                print("\nSwitched to GLOBAL mode: enter G-code lines. Enter '~' alone to return to LOCAL (arrow-key) mode.")
                last_key_time['enter'] = current_time

        else:  # mode == "global"
            # In global mode, block on input() for manual commands
            try:
                line = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                # If interrupted while typing, return to local mode
                mode = "local"
                print("\nReturning to LOCAL mode.")
                continue

            # If we just switched to GLOBAL mode from LOCAL, ignore the first empty line produced by that Enter press
            if ignore_next_input and line == "":
                ignore_next_input = False
                continue
            ignore_next_input = False

            if line == "~":
                mode = "local"
                print("Switched to LOCAL mode: arrow keys active.")
                continue

            # helper command to unlock a GRBL alarm conveniently
            if line.lower() == "unlock":
                ser.write(b"$X\n")
                time.sleep(0.05)
                continue

            if line.lower() in ['exit', 'quit']:
                break

            if not line or line.startswith("(") or line.startswith(";"):
                continue

            ser.write((line + "\n").encode("ascii", "ignore"))
            time.sleep(0.01)
        
        time.sleep(0.05)  # Small delay to prevent excessive CPU usage

except KeyboardInterrupt:
    print("\nInterrupted by user")

# Make sure laser is off at the end (belt-and-suspenders)
ser.write(b"M5\n")
ser.close()
print("Connection closed.")
