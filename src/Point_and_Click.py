import cv2
import numpy as np

# Load your homography matrix (from np.save earlier)

H = np.load("homography_matrix.npy")
print("Loaded Homography:\n", H)

# Open camera
cap = cv2.VideoCapture(1)  # adjust if not your camera index
if not cap.isOpened():
    raise SystemExit("Camera not found")

# Click callback
def on_mouse(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        pixel_pt = np.array([[x, y, 1]], dtype=np.float32).T  # homogeneous coordinates
        world_pt = H @ pixel_pt
        world_pt /= world_pt[2]  # normalize
        X, Y = world_pt[0][0], world_pt[1][0]
        print(f"Pixel ({x:.1f}, {y:.1f})  →  Task-space (X={X:.2f} mm, Y={Y:.2f} mm)")





# Set up OpenCV window
cv2.namedWindow("Camera View")
cv2.setMouseCallback("Camera View", on_mouse)

print("Click on the image to get task-space coordinates (press 'q' to quit)")

while True:
    ok, frame = cap.read()
    if not ok:
        break

    cv2.imshow("Camera View", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
