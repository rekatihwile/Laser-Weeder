from time import sleep
import serial
import cv2, numpy as np

# ---------- open serial ONCE, reuse the same handle ----------
ser = None

def open_serial(port="COM5", baud=115200):
    global ser
    if ser is None or not ser.is_open:
        ser = serial.Serial(port, baudrate=baud, timeout=0.1, write_timeout=0.1)
        ser.write(b"M5\n")    # laser hard-off always
        ser.write(b"G90\n")  
        ser.write(b"G21\n")  
    return ser

open_serial("COM5") 
ser.write(b"$H\n")
ser.write(b"M5\n")       # laser off
ser.write(b"$X\n")       # unlock if alarmed
ser.write(b"$32=0\n")    # laser mode OFF
ser.write(b"$30=1000\n") # S-scale: 0..1000 (match your sender habit)
ser.write(b"G21 G90\n")  # mm, absolute
ser.write(b"S0\n")       # explicit zero power


def move_abs(x=None, y=None, z=None, feed=3000, rapid=True):
    global ser
    if ser is None or not ser.is_open:
        open_serial("COM5")                 # Reopen serial port if needed
    parts = []
    if x is not None: parts.append(f"X{x:.3f}")
    if y is not None: parts.append(f"Y{y:.3f}")
    if z is not None: parts.append(f"Z{z:.3f}")
    if not parts: return
    ser.write(b"M5\n")
    cmd = ("G0 " if rapid else f"G1 F{feed} ") + " ".join(parts) + "\n"
    ser.write(cmd.encode())


# ---------- 2) HOMOGRAPHY: pixels -> bed-mm ----------
BED_W, BED_H = 400.0, 400.0
bed_pts = np.array([[0,0],[BED_W,0],[BED_W,BED_H],[0,BED_H]], np.float64)
img_pts = []
H = None

def img_to_bed(u, v):
    p = np.array([[[u, v]]], np.float64)
    q = cv2.perspectiveTransform(p, H)[0,0]
    return float(q[0]), float(q[1])

# ---------- 3) CAMERA preview + mouse callback ----------
cap = cv2.VideoCapture(1)
cv2.namedWindow("cam")

def on_mouse(event, x, y, *_):
    global H, img_pts
    if event == cv2.EVENT_LBUTTONDOWN:
        if H is None:
            img_pts.append([x, y])
            if len(img_pts) == 4:   
                H, _ = cv2.findHomography(np.array(img_pts, np.float64), bed_pts, 0)
        else:
            X, Y = img_to_bed(x, y)
            move_abs(X, Y, rapid=True)



def burn(duration_s=0.15, power=100):
    ser.write(f"M3 S{power}\r\n".encode())
    ser.write(f"G4 P{duration_s}\r\n".encode())
    ser.write(b"M5\r\n")





cv2.setMouseCallback("cam", on_mouse)
ser.write(b"G0 X200 Y200\n")
while True:
    ok, frame = cap.read()
    if not ok: break
    if len(img_pts) > 0:
        for i, (u,v) in enumerate(img_pts):
            cv2.circle(frame, (int(u),int(v)), 5, (255,255,255), -1)
            cv2.putText(frame, f"{i}", (int(u)+6,int(v)-6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 1)
    cv2.imshow("cam", frame)

    key = cv2.waitKey(1) & 0xFF
    if key in (27, ord('q')):   # q to quit
            break
    elif key == ord('r'):       # r to recalibrate
            H = None
            img_pts = []
            print("Homography reset — click 4 new calibration points.")

    elif key == ord('f'): # f to fire
        print('FIRE!')
        # burn(duration_s=0.15, power=700) <-- only uncomment to fire laser

            

if ser and ser.is_open:
    ser.write(b"M5\n")
    ser.close()
cap.release()
cv2.destroyAllWindows()
