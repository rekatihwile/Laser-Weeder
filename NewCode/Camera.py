# camera_view.py
import cv2

# Open the first connected camera (0 = default)
cap = cv2.VideoCapture(1)

if not cap.isOpened():
    print("❌ Could not open camera.")
    exit()

while True:
    ret, frame = cap.read()
    if not ret:
        print("❌ Failed to grab frame.")
        break

    # Display the frame
    cv2.imshow("Camera View (press 'q' to quit)", frame)

    # Wait 1 ms for a key press; exit if 'q' is pressed
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release camera and close the window
cap.release()
cv2.destroyAllWindows()
