import cv2
import mediapipe as mp
import pyautogui
import math
import time

# ============================================================
# AI VIRTUAL MOUSE FOR LINUX i3 / X11
# ============================================================

# -------------------- SETTINGS --------------------

CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480

# Cursor smoothing
SMOOTHING = 0.25

# Camera-to-screen mapping
FRAME_MARGIN = 80

# Gesture thresholds
PINCH_THRESHOLD = 0.055
CLICK_COOLDOWN = 0.45

# Drag settings
DRAG_HOLD_TIME = 0.45

# Scroll settings
SCROLL_THRESHOLD = 35
SCROLL_AMOUNT = 2

# ---------------------------------------------------

screen_width, screen_height = pyautogui.size()

pyautogui.PAUSE = 0.01
pyautogui.FAILSAFE = True


# ============================================================
# MEDIAPIPE
# ============================================================

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    model_complexity=1,
    min_detection_confidence=0.65,
    min_tracking_confidence=0.65
)


# ============================================================
# CAMERA
# ============================================================

cap = cv2.VideoCapture(0)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)

if not cap.isOpened():
    print("ERROR: Could not open webcam.")
    exit()


# ============================================================
# VARIABLES
# ============================================================

prev_mouse_x = screen_width // 2
prev_mouse_y = screen_height // 2

last_click_time = 0

pinch_start_time = None
dragging = False

prev_index_y = None

gesture_text = "Starting..."


# ============================================================
# FUNCTIONS
# ============================================================

def distance(p1, p2):
    """Calculate normalized distance between two landmarks."""
    return math.sqrt(
        (p1.x - p2.x) ** 2 +
        (p1.y - p2.y) ** 2
    )


def finger_up(landmarks, tip, pip):
    """Check whether a finger is extended."""
    return landmarks[tip].y < landmarks[pip].y


def get_finger_states(lm):
    """
    Returns:
        index, middle, ring, pinky
    """

    index = finger_up(lm, 8, 6)
    middle = finger_up(lm, 12, 10)
    ring = finger_up(lm, 16, 14)
    pinky = finger_up(lm, 20, 18)

    return index, middle, ring, pinky


def move_cursor(index_tip):
    global prev_mouse_x, prev_mouse_y

    x = index_tip.x * CAMERA_WIDTH
    y = index_tip.y * CAMERA_HEIGHT

    # Keep hand inside the controllable camera area
    x = max(
        FRAME_MARGIN,
        min(CAMERA_WIDTH - FRAME_MARGIN, x)
    )

    y = max(
        FRAME_MARGIN,
        min(CAMERA_HEIGHT - FRAME_MARGIN, y)
    )

    # Convert camera coordinates to screen coordinates
    mouse_x = (
        (x - FRAME_MARGIN)
        / (CAMERA_WIDTH - 2 * FRAME_MARGIN)
        * screen_width
    )

    mouse_y = (
        (y - FRAME_MARGIN)
        / (CAMERA_HEIGHT - 2 * FRAME_MARGIN)
        * screen_height
    )

    # Smooth cursor movement
    curr_x = (
        prev_mouse_x
        + (mouse_x - prev_mouse_x) * SMOOTHING
    )

    curr_y = (
        prev_mouse_y
        + (mouse_y - prev_mouse_y) * SMOOTHING
    )

    # Keep cursor within screen boundaries
    curr_x = max(0, min(screen_width - 1, curr_x))
    curr_y = max(0, min(screen_height - 1, curr_y))

    pyautogui.moveTo(
        int(curr_x),
        int(curr_y)
    )

    prev_mouse_x = curr_x
    prev_mouse_y = curr_y

# ============================================================
# MAIN LOOP
# ============================================================

print("---------------------------------------------")
print(" AI VIRTUAL MOUSE")
print("---------------------------------------------")
print("Index finger       -> Cursor movement")
print("Thumb + Index      -> Left click")
print("Index + Middle     -> Right click")
print("Open Palm          -> Stop cursor")
print("Index vertical     -> Scroll")
print("Pinch hold         -> Drag and drop")
print("---------------------------------------------")
print("Press Q to quit")
print("---------------------------------------------")


while True:

    success, frame = cap.read()

    if not success:
        print("Camera frame error.")
        continue

    # Mirror image
    frame = cv2.flip(frame, 1)

    # Convert BGR -> RGB
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # MediaPipe processing
    results = hands.process(rgb)

    current_time = time.time()

    gesture_text = "No hand detected"

    if results.multi_hand_landmarks:

        hand_landmarks = results.multi_hand_landmarks[0]

        lm = hand_landmarks.landmark

        # Draw landmarks
        mp_draw.draw_landmarks(
            frame,
            hand_landmarks,
            mp_hands.HAND_CONNECTIONS
        )

        # --------------------------------------------
        # LANDMARKS
        # --------------------------------------------

        thumb_tip = lm[4]
        index_tip = lm[8]
        middle_tip = lm[12]

        # --------------------------------------------
        # FINGER STATES
        # --------------------------------------------

        index_up, middle_up, ring_up, pinky_up = get_finger_states(lm)

        # --------------------------------------------
        # PINCH DETECTION
        # --------------------------------------------

        pinch_distance = distance(thumb_tip, index_tip)

        pinch = pinch_distance < PINCH_THRESHOLD

        # --------------------------------------------
        # OPEN PALM
        # --------------------------------------------

        open_palm = (
            index_up and
            middle_up and
            ring_up and
            pinky_up
        )

        # ====================================================
        # 1. OPEN PALM -> STOP CURSOR
        # ====================================================

        if open_palm:

            gesture_text = "STOP CURSOR"

            # If dragging, release mouse
            if dragging:
                pyautogui.mouseUp()
                dragging = False

            pinch_start_time = None
            prev_index_y = None

        # ====================================================
        # 2. RIGHT CLICK
        # INDEX + MIDDLE FINGERS
        # ====================================================

        elif index_up and middle_up and not ring_up and not pinky_up:

            gesture_text = "RIGHT CLICK"

            if (
                current_time - last_click_time
                > CLICK_COOLDOWN
            ):

                pyautogui.rightClick()

                last_click_time = current_time

            prev_index_y = None

        # ====================================================
        # 3. PINCH
        # THUMB + INDEX
        # ====================================================

        elif pinch:

            # Start pinch timer
            if pinch_start_time is None:
                pinch_start_time = current_time

            pinch_duration = current_time - pinch_start_time

            # --------------------------------------------
            # DRAG
            # --------------------------------------------

            if pinch_duration >= DRAG_HOLD_TIME:

                gesture_text = "DRAGGING"

                if not dragging:
                    pyautogui.mouseDown()
                    dragging = True

                move_cursor(index_tip)

            # --------------------------------------------
            # SHORT PINCH
            # LEFT CLICK
            # --------------------------------------------

            else:

                gesture_text = "LEFT CLICK"

        # ====================================================
        # PINCH RELEASE
        # SHORT PINCH = LEFT CLICK
        # ====================================================

        else:

            # If pinch was released
            if pinch_start_time is not None:

                pinch_duration = current_time - pinch_start_time

                # Short pinch -> left click
                if (
                    pinch_duration < DRAG_HOLD_TIME
                    and current_time - last_click_time
                    > CLICK_COOLDOWN
                ):

                    pyautogui.click()

                    last_click_time = current_time

                # Release drag
                if dragging:

                    pyautogui.mouseUp()
                    dragging = False

                pinch_start_time = None

            # =================================================
            # 4. INDEX FINGER
            # CURSOR / SCROLL
            # =================================================

            if index_up and not middle_up:

                current_y = index_tip.y * CAMERA_HEIGHT

                if prev_index_y is not None:

                    movement = current_y - prev_index_y

                    # Significant vertical movement
                    if abs(movement) > SCROLL_THRESHOLD:

                        # Downward movement
                        if movement > 0:

                            pyautogui.scroll(
                                -SCROLL_AMOUNT
                            )

                            gesture_text = "SCROLL DOWN"

                        # Upward movement
                        else:

                            pyautogui.scroll(
                                SCROLL_AMOUNT
                            )

                            gesture_text = "SCROLL UP"

                    else:

                        gesture_text = "CURSOR MOVEMENT"

                        move_cursor(index_tip)

                else:

                    gesture_text = "CURSOR MOVEMENT"

                    move_cursor(index_tip)

                prev_index_y = current_y

            else:

                prev_index_y = None

    # ========================================================
    # DISPLAY
    # ========================================================

    cv2.rectangle(
        frame,
        (10, 10),
        (350, 60),
        (0, 0, 0),
        -1
    )

    cv2.putText(
        frame,
        gesture_text,
        (20, 45),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (255, 255, 255),
        2
    )

    cv2.imshow(
        "AI Virtual Mouse - i3",
        frame
    )

    # Press Q to exit
    key = cv2.waitKey(1) & 0xFF

    if key == ord('q'):
        break


# ============================================================
# CLEANUP
# ============================================================

if dragging:
    pyautogui.mouseUp()

cap.release()
cv2.destroyAllWindows()
hands.close()

print("AI Virtual Mouse stopped.")
