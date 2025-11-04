# step2_roi_threshold.py
import cv2
import numpy as np

CAM_INDEX   = 1  # adjust as needed                         
KERNEL_SIZE = 1 # was 3 - 3x3 opening removes tiny dots; 1 makes opening a no-op
MIN_AREA = 1# keep as you had it
MAX_AREA = 5     # raise this so small dots are not excluded; tune as needed
MIN_BLACK = 175
HOMOGRAPHY_CALC_NEEDED = True


cap = cv2.VideoCapture(CAM_INDEX)
Showing = cap.isOpened()
while not Showing:
    print(f"Camera Index {CAM_INDEX} is not opened, trying {CAM_INDEX+1}")
    CAM_INDEX += 1
    cap = cv2.VideoCapture(CAM_INDEX)
cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)

cap.set(cv2.CAP_PROP_EXPOSURE, -6)   
cap.set(cv2.CAP_PROP_BRIGHTNESS, -1)
cap.set(cv2.CAP_PROP_CONTRAST, 100)

# --- pick ROI once ---
ok, frame = cap.read()
if not ok:
    raise SystemExit("Camera failed")

# Drag a box with the mouse, press ENTER or SPACE to accept, 'c' to cancel
roi = cv2.selectROI("Select ROI (press ENTER)", frame, fromCenter=False, showCrosshair=True)
cv2.destroyWindow("Select ROI (press ENTER)")
x, y, w, h = map(int, roi)
if w == 0 or h == 0:
    raise SystemExit("No ROI selected")




while True:

    ok, frame = cap.read()
    if not ok:
        break

    crop = frame[y:y+h, x:x+w]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    _, bw = cv2.threshold(gray, MIN_BLACK, 255, cv2.THRESH_BINARY_INV)
    kernel = np.ones((3, 3), np.uint8)
    opened = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel)
    closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)
    cc_input = bw
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(cc_input, connectivity=8)

    

    n_rows, n_cols = 5, 6  # expected grid size
    if num_labels > 1:
        areas = stats[1:, cv2.CC_STAT_AREA]
        print(f"Number of areas: {len(areas)}")
        valid_labels = np.where((areas >= MIN_AREA) & (areas <= MAX_AREA))[0] + 1
    else:
        valid_labels = np.array([], dtype=np.int32)

    centroids_valid = centroids[valid_labels] 
    centroids_valid = centroids[valid_labels]
    

    
    if(len(valid_labels))== (n_rows * n_cols):
        HOMOGRAPHY_CALC_NEEDED = True
        print(f" True because there are {len(valid_labels)} points")
    else:
        HOMOGRAPHY_CALC_NEEDED = False


    # Convert ROI-relative to full-frame coordinates
    centroids_valid[:, 0] += x
    centroids_valid[:, 1] += y

    sorted_idx = np.lexsort((centroids_valid[:, 0], centroids_valid[:, 1]))
    sorted_by_y = centroids_valid[np.argsort(centroids_valid[:, 1])]

    # Cluster points into rows by proximity in Y
    rows = []
    if len(sorted_by_y) == 0:
        # Always show windows for debugging before skipping
        cv2.imshow("0: ROI (color)", crop)
        cv2.imshow("1: ROI Grayscale", gray)
        cv2.imshow("2: ROI Binary", bw)
        cv2.imshow("3: ROI After Morphology", closed)
        cv2.waitKey(1)
        continue

    current_row = [sorted_by_y[0]]
    y_threshold = 10  # tolerance for what counts as “same row” — tune this

    for pt in sorted_by_y[1:]:
        if abs(pt[1] - current_row[-1][1]) < y_threshold:
            current_row.append(pt)
        else:
            rows.append(np.array(current_row))
            current_row = [pt]
    rows.append(np.array(current_row))

    rows_sorted = [row[np.argsort(row[:, 0])] for row in rows]
    rows_sorted.reverse() 
    
    sorted_pts = np.vstack(rows_sorted)

    if HOMOGRAPHY_CALC_NEEDED:
        print(f"Computing Homography with  {len(valid_labels)} points")
        img_points = sorted_pts.reshape(n_rows, n_cols, 2)
        x_vals = np.linspace(350, 100, n_cols)
        y_vals = np.linspace(330,110, n_rows) 


        img_points_flat = img_points.reshape(-1, 2).astype(np.float32)
        print("img_points:\n", img_points_flat)

        real_points = np.array([[x, y] for y in y_vals for x in x_vals], dtype=np.float32)
        print("real_points:\n", real_points)
        H, mask = cv2.findHomography(img_points_flat, real_points, cv2.RANSAC)
        np.save("homography_matrix.npy", H)
        print("Saved Homography:\n", H)
        HOMOGRAPHY_CALC_NEEDED = False
    

    mask = np.isin(labels, valid_labels).astype(np.uint8) * 255

    filtered_color = cv2.bitwise_and(crop, crop, mask=mask)

    for lbl in valid_labels:
        lx = int(stats[lbl, cv2.CC_STAT_LEFT])
        ly = int(stats[lbl, cv2.CC_STAT_TOP])
        lw = int(stats[lbl, cv2.CC_STAT_WIDTH])
        lh = int(stats[lbl, cv2.CC_STAT_HEIGHT])
        cv2.rectangle(filtered_color, (lx, ly), (lx + lw, ly + lh), (0, 255, 0), 2)





    cv2.imshow("0: ROI (color)", crop)
    cv2.imshow("1: ROI Grayscale", gray)
    cv2.imshow("2: ROI Binary", bw)
    cv2.imshow("3: ROI After Morphology", opened)
    cv2.imshow("4: Filtered Mask (area filter)", mask)
    cv2.imshow("5: Filtered Overlay", filtered_color)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
