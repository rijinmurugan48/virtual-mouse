#!/usr/bin/env python3
"""
AI VIRTUAL MOUSE FOR LINUX i3 / X11 (Ubuntu 20.04)
===================================================

Control your mouse with hand gestures via webcam + MediaPipe.

Gestures:
  Index finger only   -> Move cursor
  Thumb + Index pinch (short)  -> Left click
  Thumb + Index pinch (held)   -> Drag and drop
  Index + Middle up   -> Right click
  Open palm           -> Freeze cursor / pause
  Index moved fast vertically -> Scroll up/down

Press 'q' with the preview window focused to quit,
or Ctrl+C in the terminal.

Setup (Ubuntu 20.04, X11/i3):
    sudo apt update
    sudo apt install -y python3-venv python3-dev libgl1 scrot xdotool
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install opencv-python mediapipe==0.10.9 pyautogui

Run:
    python3 ai_virtual_mouse.py
    python3 ai_virtual_mouse.py --no-preview     # lower CPU, no camera window
    python3 ai_virtual_mouse.py --camera 1       # pick a different webcam
"""

import argparse
import math
import sys
import time

# ---- Friendly import checks -------------------------------------------
missing = []
try:
    import cv2
except ImportError:
    missing.append("opencv-python")
try:
    import mediapipe as mp
except ImportError:
    missing.append("mediapipe")
try:
    import pyautogui
except ImportError:
    missing.append("pyautogui")

if missing:
    print("Missing required packages: " + ", ".join(missing))
    print("Install them with:")
    print(f"    pip install {' '.join(missing)}")
    sys.exit(1)


# ============================================================
# CLI ARGS
# ============================================================

parser = argparse.ArgumentParser(description="AI Virtual Mouse")
parser.add_argument("--camera", type=int, default=0, help="Camera index (default 0)")
parser.add_argument("--width", type=int, default=640, help="Capture width")
parser.add_argument("--height", type=int, default=480, help="Capture height")
parser.add_argument(
    "--no-preview",
    action="store_true",
    help="Run without the OpenCV preview window (lower CPU, no visual feedback)",
)
parser.add_argument(
    "--flip/--no-flip",
    dest="flip",
    action="store_true",
    default=True,
    help="Mirror the camera image (default on)",
)
args = parser.parse_args()


# ============================================================
# SETTINGS
# ============================================================

CAMERA_WIDTH = args.width
CAMERA_HEIGHT = args.height
SHOW_PREVIEW = not args.no_preview

SMOOTHING = 0.35          # higher = snappier, lower = smoother/laggier
FRAME_MARGIN = 80         # inner camera frame mapped to full screen

PINCH_THRESHOLD = 0.045   # normalized distance; slightly stricter than original
CLICK_COOLDOWN = 0.35
DRAG_HOLD_TIME = 0.35

SCROLL_THRESHOLD = 30
SCROLL_AMOUNT = 2

TARGET_FPS = 30
FRAME_TIME = 1.0 / TARGET_FPS

pyautogui.PAUSE = 0.0      # we control pacing ourselves via FRAME_TIME
pyautogui.FAILSAFE = True  # move mouse to a screen corner to abort


# ============================================================
# MEDIAPIPE
# ============================================================

mp_hands = mp.solutions.hands
mp_draw = mp.solutions.drawing_utils

hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    model_complexity=0,          # 0 = fastest, good enough for mouse control
    min_detection_confidence=0.6,
    min_tracking_confidence=0.6,
)


# ============================================================
# CAMERA
# ============================================================

def open_camera(index):
    # CAP_V4L2 opens faster and more reliably on Linux than the default backend
    cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
    if not cap.isOpened():
        cap = cv2.VideoCapture(index)
    return cap


cap = open_camera(args.camera)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAMERA_WIDTH)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAMERA_HEIGHT)
cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
# Small buffer = less lag between hand movement and cursor movement
try:
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
except Exception:
    pass

if not cap.isOpened():
    print(f"ERROR: Could not open webcam at index {args.camera}.")
    print("Try a different index with --camera 1, --camera 2, etc.")
    print("List available cameras with: ls /dev/video*")
    sys.exit(1)

screen_width, screen_height = pyautogui.size()


# ============================================================
# STATE
# ============================================================

prev_mouse_x = screen_width // 2
prev_mouse_y = screen_height // 2

last_click_time = 0.0
pinch_start_time = None
dragging = False
prev_index_y = None
gesture_text = "Starting..."
consecutive_frame_failures = 0


# ============================================================
# HELPERS
# ============================================================

def distance(p1, p2):
    return math.hypot(p1.x - p2.x, p1.y - p2.y)


def finger_up(lm, tip, pip):
    return lm[tip].y < lm[pip].y


def get_finger_states(lm):
    return (
        finger_up(lm, 8, 6),    # index
        finger_up(lm, 12, 10),  # middle
        finger_up(lm, 16, 14),  # ring
        finger_up(lm, 20, 18),  # pinky
    )


def move_cursor(index_tip):
    global prev_mouse_x, prev_mouse_y

    x = index_tip.x * CAMERA_WIDTH
    y = index_tip.y * CAMERA_HEIGHT

    x = max(FRAME_MARGIN, min(CAMERA_WIDTH - FRAME_MARGIN, x))
    y = max(FRAME_MARGIN, min(CAMERA_HEIGHT - FRAME_MARGIN, y))

    mouse_x = (x - FRAME_MARGIN) / (CAMERA_WIDTH - 2 * FRAME_MARGIN) * screen_width
    mouse_y = (y - FRAME_MARGIN) / (CAMERA_HEIGHT - 2 * FRAME_MARGIN) * screen_height

    curr_x = prev_mouse_x + (mouse_x - prev_mouse_x) * SMOOTHING
    curr_y = prev_mouse_y + (mouse_y - prev_mouse_y) * SMOOTHING

    curr_x = max(0, min(screen_width - 1, curr_x))
    curr_y = max(0, min(screen_height - 1, curr_y))

    try:
        pyautogui.moveTo(int(curr_x), int(curr_y), _pause=False)
    except pyautogui.FailSafeException:
        # user yanked the mouse to a corner - stop cleanly
        cleanup_and_exit()

    prev_mouse_x = curr_x
    prev_mouse_y = curr_y


def cleanup_and_exit():
    global dragging
    if dragging:
        pyautogui.mouseUp()
        dragging = False
    cap.release()
    if SHOW_PREVIEW:
        cv2.destroyAllWindows()
    hands.close()
    print("\nAI Virtual Mouse stopped.")
    sys.exit(0)


# ============================================================
# MAIN LOOP
# ============================================================

print("---------------------------------------------")
print(" AI VIRTUAL MOUSE")
print("---------------------------------------------")
print("Index finger        -> Cursor movement")
print("Thumb + Index (tap)  -> Left click")
print("Thumb + Index (hold) -> Drag and drop")
print("Index + Middle       -> Right click")
print("Open palm            -> Freeze cursor")
print("Index fast vertical  -> Scroll")
print("---------------------------------------------")
print("Ctrl+C in terminal to quit" + (", or press Q in the preview window" if SHOW_PREVIEW else ""))
print("Fling the mouse to a screen corner to force-stop (fail-safe).")
print("---------------------------------------------")

try:
    while True:
        loop_start = time.time()

        success, frame = cap.read()

        if not success or frame is None:
            consecutive_frame_failures += 1
            if consecutive_frame_failures > 60:
                print("ERROR: Camera stopped responding. Exiting.")
                break
            time.sleep(0.01)
            continue
        consecutive_frame_failures = 0

        if args.flip:
            frame = cv2.flip(frame, 1)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = hands.process(rgb)

        current_time = time.time()
        gesture_text = "No hand detected"

        if results.multi_hand_landmarks:
            hand_landmarks = results.multi_hand_landmarks[0]
            lm = hand_landmarks.landmark

            if SHOW_PREVIEW:
                mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            thumb_tip = lm[4]
            index_tip = lm[8]

            index_up, middle_up, ring_up, pinky_up = get_finger_states(lm)
            pinch = distance(thumb_tip, index_tip) < PINCH_THRESHOLD
            open_palm = index_up and middle_up and ring_up and pinky_up

            # ---- Open palm: freeze / cancel state ----
            if open_palm:
                gesture_text = "PAUSED (open palm)"
                if dragging:
                    pyautogui.mouseUp()
                    dragging = False
                pinch_start_time = None
                prev_index_y = None

            # ---- Right click ----
            elif index_up and middle_up and not ring_up and not pinky_up:
                gesture_text = "RIGHT CLICK"
                if current_time - last_click_time > CLICK_COOLDOWN:
                    pyautogui.click(button="right")
                    last_click_time = current_time
                prev_index_y = None

            # ---- Pinch (click or drag) ----
            elif pinch:
                if pinch_start_time is None:
                    pinch_start_time = current_time
                pinch_duration = current_time - pinch_start_time

                if pinch_duration >= DRAG_HOLD_TIME:
                    gesture_text = "DRAGGING"
                    if not dragging:
                        pyautogui.mouseDown()
                        dragging = True
                    move_cursor(index_tip)
                else:
                    gesture_text = "LEFT CLICK (hold to drag)"

            # ---- Pinch released / index tracking ----
            else:
                if pinch_start_time is not None:
                    pinch_duration = current_time - pinch_start_time
                    if (
                        pinch_duration < DRAG_HOLD_TIME
                        and current_time - last_click_time > CLICK_COOLDOWN
                    ):
                        pyautogui.click(button="left")
                        last_click_time = current_time
                    if dragging:
                        pyautogui.mouseUp()
                        dragging = False
                    pinch_start_time = None

                if index_up and not middle_up:
                    current_y = index_tip.y * CAMERA_HEIGHT

                    if prev_index_y is not None:
                        movement = current_y - prev_index_y
                        if abs(movement) > SCROLL_THRESHOLD:
                            if movement > 0:
                                pyautogui.scroll(-SCROLL_AMOUNT)
                                gesture_text = "SCROLL DOWN"
                            else:
                                pyautogui.scroll(SCROLL_AMOUNT)
                                gesture_text = "SCROLL UP"
                        else:
                            gesture_text = "MOVING CURSOR"
                            move_cursor(index_tip)
                    else:
                        gesture_text = "MOVING CURSOR"
                        move_cursor(index_tip)

                    prev_index_y = current_y
                else:
                    prev_index_y = None
        else:
            # No hand: don't leave a click/drag hanging
            if dragging:
                pyautogui.mouseUp()
                dragging = False
            pinch_start_time = None
            prev_index_y = None

        if SHOW_PREVIEW:
            cv2.rectangle(frame, (10, 10), (400, 60), (0, 0, 0), -1)
            cv2.putText(
                frame, gesture_text, (20, 45),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2,
            )
            cv2.imshow("AI Virtual Mouse - i3", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break

        # Pace the loop so we don't peg a CPU core
        elapsed = time.time() - loop_start
        sleep_time = FRAME_TIME - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)

except KeyboardInterrupt:
    pass
finally:
    cleanup_and_exit()