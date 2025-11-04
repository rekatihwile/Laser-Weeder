# click_crosshair.py
import cv2
# Change this if you want a different camera (0, 1, 2, ...)
CAMERA_ID = 1
# mutable container so mouse callback can update it without `global`
last_click = []
# Make the instructions in the window explicit about LEFT-clicking in the image
WINDOW_NAME = "Camera - LEFT-CLICK the image to place crosshair (q or ESC to quit)"
def mouse_callback(event, x, y, flags, param):
    # left mouse button click: update coordinate and print (explicit instruction)
    if event == cv2.EVENT_LBUTTONDOWN:
        last_click.clear()
        last_click.append((x, y))
        print(f"Left-click at image pixel: ({x}, {y}) — crosshair placed")
def draw_crosshair(img, center, size=20, thickness=1):
    x, y = center
    # horizontal
    cv2.line(img, (x - size, y), (x + size, y), (0, 255, 0), thickness)
    # vertical
    cv2.line(img, (x, y - size), (x, y + size), (0, 255, 0), thickness)
    # small center circle
    cv2.circle(img, (x, y), 2, (0, 255, 0), -1)
    # optional coordinate text
    cv2.putText(img, f"{x},{y}", (x + 10, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
def main():
    cap = cv2.VideoCapture(CAMERA_ID)
    if not cap.isOpened():
        print(f"ERROR: Could not open camera with ID {CAMERA_ID}")
        return
    cv2.namedWindow(WINDOW_NAME)
    cv2.setMouseCallback(WINDOW_NAME, mouse_callback)
    while True:
        ret, frame = cap.read()
        if not ret:
            print("ERROR: Failed to read frame from camera.")
            break
        display = frame.copy()
        if last_click:
            draw_crosshair(display, last_click[0], size=20, thickness=2)
        cv2.imshow(WINDOW_NAME, display)
        # press 'q' or ESC to quit
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            break
    cap.release()
    cv2.destroyAllWindows()
if __name__ == "__main__":
    main()
