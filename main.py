import cv2
import pyautogui
from hand_tracker import HandTracker

# Webcam
cap = cv2.VideoCapture(0)

# Hand detector
detector = HandTracker(detectionCon=0.8)

# Screen size
screen_width, screen_height = pyautogui.size()

while True:
    success, img = cap.read()

    if not success:
        break

    # Flip image for mirror view
    img = cv2.flip(img, 1)

    # Detect hand
    img = detector.findHands(img)
    lmList = detector.findPosition(img)

    if len(lmList) != 0:

        # Index fingertip (Landmark 8)
        x, y = lmList[8][1], lmList[8][2]

        # Camera size
        h, w, _ = img.shape

        # Convert camera coordinates to screen coordinates
        mouse_x = screen_width * x / w
        mouse_y = screen_height * y / h

        # Move mouse
        pyautogui.moveTo(mouse_x, mouse_y)

        # Thumb tip (4)
        thumb_x, thumb_y = lmList[4][1], lmList[4][2]

        # Distance between thumb and index
        distance = ((x - thumb_x) ** 2 + (y - thumb_y) ** 2) ** 0.5

        # Left click
        if distance < 35:
            pyautogui.click()
            cv2.putText(img, "LEFT CLICK", (10, 50),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1, (0, 255, 0), 2)

    cv2.imshow("AI Virtual Mouse", img)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()