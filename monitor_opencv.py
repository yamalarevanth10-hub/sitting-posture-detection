import cv2
import numpy as np
import time
import math
import os
import winsound
import mediapipe as mp
from mediapipe.tasks.python import vision
from mediapipe.tasks.python import BaseOptions

# Configuration and Paths
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
POSE_MODEL_PATH = os.path.join(MODEL_DIR, "pose_landmarker_lite.task")
FACE_MODEL_PATH = os.path.join(MODEL_DIR, "face_landmarker.task")

# Landmark indices for MediaPipe Face
# Left eye landmarks: [left_corner, top1, top2, right_corner, bot2, bot1]
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]

def calculate_angle(p1, p2):
    """Calculates angle of line (p1 -> p2) relative to horizontal in degrees."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    angle = math.degrees(math.atan2(dy, dx))
    # Normalize to deviation from horizontal (0 degrees)
    if angle > 90:
        angle = 180 - angle
    elif angle < -90:
        angle = -180 - angle
    return abs(angle)

def euclidean_dist(p1, p2):
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])

def calculate_ear(landmarks, eye_indices, img_w, img_h):
    """Calculates Eye Aspect Ratio (EAR)."""
    pts = [np.array([landmarks[idx].x * img_w, landmarks[idx].y * img_h]) for idx in eye_indices]
    # Vertical distances
    v1 = euclidean_dist(pts[1], pts[5])
    v2 = euclidean_dist(pts[2], pts[4])
    # Horizontal distance
    h = euclidean_dist(pts[0], pts[3])
    if h == 0:
        return 0.3
    ear = (v1 + v2) / (2.0 * h)
    return ear

class PostureWellnessMonitor:
    def __init__(self):
        # Initialize Pose Landmarker
        base_pose = BaseOptions(model_asset_path=POSE_MODEL_PATH)
        options_pose = vision.PoseLandmarkerOptions(
            base_options=base_pose,
            running_mode=vision.RunningMode.IMAGE,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5
        )
        self.pose_detector = vision.PoseLandmarker.create_from_options(options_pose)

        # Initialize Face Landmarker for eye blink detection
        base_face = BaseOptions(model_asset_path=FACE_MODEL_PATH)
        options_face = vision.FaceLandmarkerOptions(
            base_options=base_face,
            running_mode=vision.RunningMode.IMAGE,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5
        )
        self.face_detector = vision.FaceLandmarker.create_from_options(options_face)

        # Calibration parameters
        self.baseline_slouch_ratio = 0.50
        self.is_calibrated = False
        
        # Thresholds
        self.shoulder_tilt_threshold = 4.5  # degrees
        self.head_tilt_threshold = 6.0      # degrees
        self.slouch_ratio_tolerance = 0.15  # 15% drop from baseline
        self.ear_blink_threshold = 0.20     # EAR below this is a blink

        # State tracking
        self.blink_count = 0
        self.eye_closed = False
        self.blink_timestamps = []
        self.bpm = 0.0
        
        # Slouch timer for alerts
        self.poor_posture_start = None
        self.last_alert_time = 0
        
        # Session metrics
        self.session_start = time.time()
        self.good_frames = 0
        self.total_frames = 0

    def close(self):
        try:
            self.pose_detector.close()
            self.face_detector.close()
        except Exception:
            pass

    def process_frame(self, frame):
        h, w, _ = frame.shape
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        pose_result = self.pose_detector.detect(mp_image)
        face_result = self.face_detector.detect(mp_image)

        posture_status = "UNKNOWN"
        posture_reasons = []
        shoulder_tilt = 0.0
        head_tilt = 0.0
        slouch_ratio = 0.0
        current_ear = 0.3

        curr_time = time.time()
        self.total_frames += 1

        # Process Eyes / Blinking
        if face_result.face_landmarks and len(face_result.face_landmarks) > 0:
            landmarks = face_result.face_landmarks[0]
            left_ear = calculate_ear(landmarks, LEFT_EYE, w, h)
            right_ear = calculate_ear(landmarks, RIGHT_EYE, w, h)
            current_ear = (left_ear + right_ear) / 2.0

            # Blink state machine
            if current_ear < self.ear_blink_threshold:
                if not self.eye_closed:
                    self.eye_closed = True
            else:
                if self.eye_closed:
                    self.blink_count += 1
                    self.blink_timestamps.append(curr_time)
                    self.eye_closed = False

            # Update BPM over rolling 60 seconds
            self.blink_timestamps = [t for t in self.blink_timestamps if curr_time - t <= 60]
            self.bpm = len(self.blink_timestamps)

        # Process Posture via Pose Landmarks
        if pose_result.pose_landmarks and len(pose_result.pose_landmarks) > 0:
            landmarks = pose_result.pose_landmarks[0]
            
            # Key points
            # 0: nose, 2: left_eye, 5: right_eye, 7: left_ear, 8: right_ear
            # 11: left_shoulder, 12: right_shoulder
            nose = np.array([landmarks[0].x * w, landmarks[0].y * h])
            left_eye = np.array([landmarks[2].x * w, landmarks[2].y * h])
            right_eye = np.array([landmarks[5].x * w, landmarks[5].y * h])
            left_shoulder = np.array([landmarks[11].x * w, landmarks[11].y * h])
            right_shoulder = np.array([landmarks[12].x * w, landmarks[12].y * h])

            # 1. Shoulder Tilt
            shoulder_tilt = calculate_angle(left_shoulder, right_shoulder)

            # 2. Head Tilt
            head_tilt = calculate_angle(left_eye, right_eye)

            # 3. Slouch Ratio
            head_mid = (left_eye + right_eye) / 2.0
            shoulder_mid = (left_shoulder + right_shoulder) / 2.0
            shoulder_width = euclidean_dist(left_shoulder, right_shoulder)
            
            vertical_dist = shoulder_mid[1] - head_mid[1]
            if shoulder_width > 0:
                slouch_ratio = vertical_dist / shoulder_width

            # Auto-calibrate initial baseline if not calibrated
            if not self.is_calibrated and slouch_ratio > 0.2:
                self.baseline_slouch_ratio = round(slouch_ratio, 2)
                self.is_calibrated = True

            # Evaluate Posture Quality
            is_good = True
            if shoulder_tilt > self.shoulder_tilt_threshold:
                is_good = False
                posture_reasons.append("Shoulder Tilt")

            if head_tilt > self.head_tilt_threshold:
                is_good = False
                posture_reasons.append("Head Tilt")

            slouch_threshold = self.baseline_slouch_ratio * (1.0 - self.slouch_ratio_tolerance)
            if slouch_ratio < slouch_threshold:
                is_good = False
                posture_reasons.append("Slouching / Forward Head")

            if is_good:
                posture_status = "GOOD (Upright & Aligned)"
                self.good_frames += 1
                self.poor_posture_start = None
            else:
                posture_status = "BAD (" + " & ".join(posture_reasons) + ")"
                if self.poor_posture_start is None:
                    self.poor_posture_start = curr_time
                elif curr_time - self.poor_posture_start > 4.0:
                    # Alert sound every 5 seconds of poor posture
                    if curr_time - self.last_alert_time > 5.0:
                        try:
                            winsound.Beep(880, 250)
                        except Exception:
                            pass
                        self.last_alert_time = curr_time

            # Draw visual landmarks on frame
            color = (0, 255, 0) if is_good else (0, 0, 255)
            
            # Shoulder line
            p1 = (int(left_shoulder[0]), int(left_shoulder[1]))
            p2 = (int(right_shoulder[0]), int(right_shoulder[1]))
            cv2.line(frame, p1, p2, color, 3)
            cv2.circle(frame, p1, 7, (0, 215, 255), -1)
            cv2.circle(frame, p2, 7, (0, 215, 255), -1)
            cv2.putText(frame, f"{shoulder_tilt:.1f} deg", (p1[0] - 80, p1[1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

            # Head / Eye line
            e1 = (int(left_eye[0]), int(left_eye[1]))
            e2 = (int(right_eye[0]), int(right_eye[1]))
            cv2.line(frame, e1, e2, color, 3)
            cv2.circle(frame, e1, 6, (0, 215, 255), -1)
            cv2.circle(frame, e2, 6, (0, 215, 255), -1)
            cv2.putText(frame, f"{head_tilt:.1f} deg", (e1[0] - 60, e1[1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

            # Spinal alignment line (vertical connector from head midpoint to shoulder midpoint)
            hm = (int(head_mid[0]), int(head_mid[1]))
            sm = (int(shoulder_mid[0]), int(shoulder_mid[1]))
            cv2.line(frame, hm, sm, (255, 255, 0), 2)
            cv2.circle(frame, hm, 5, (0, 165, 255), -1)
            cv2.circle(frame, sm, 5, (0, 165, 255), -1)

        # Draw HUD overlays matching reference design
        self.render_hud(frame, posture_status, shoulder_tilt, head_tilt, slouch_ratio, current_ear)

        return frame

    def render_hud(self, frame, status, shoulder_tilt, head_tilt, slouch_ratio, ear):
        h, w, _ = frame.shape
        
        # 1. Top HUD Overlay Header (Semi-transparent black overlay)
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 100), (30, 30, 30), -1)
        # Bottom HUD Overlay
        cv2.rectangle(overlay, (0, h - 50), (w, h), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

        # Top Title
        cv2.putText(frame, "Digital Wellness Monitor | Sitting Posture Analysis", (20, 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (240, 240, 240), 2, cv2.LINE_AA)

        # Posture Status
        if "GOOD" in status:
            status_color = (0, 255, 100) # Bright green
        elif "BAD" in status:
            status_color = (50, 50, 255) # Bright red
        else:
            status_color = (0, 200, 255) # Amber/Yellow
            
        cv2.putText(frame, f"POSTURE: {status}", (20, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2, cv2.LINE_AA)

        # Metric Stats Line
        stats_str = f"Shoulder Tilt: {shoulder_tilt:.1f} deg | Head Tilt: {head_tilt:.1f} deg | Slouch Ratio: {slouch_ratio:.2f} (Base: {self.baseline_slouch_ratio:.2f}) | Blinks: {self.blink_count} ({self.bpm:.0f} BPM)"
        cv2.putText(frame, stats_str, (20, 88),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 220, 220), 1, cv2.LINE_AA)

        # Bottom Instructions & Medical Disclaimer
        cv2.putText(frame, "Press [C] to Calibrate Upright Baseline | Press [R] Reset | Press [Q] or [ESC] to Exit",
                    (20, h - 28), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(frame, "* Non-diagnostic wellness feedback. Not for medical spinal evaluation.",
                    (20, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160, 160, 160), 1, cv2.LINE_AA)

    def calibrate(self, slouch_ratio):
        if slouch_ratio > 0.1:
            self.baseline_slouch_ratio = round(slouch_ratio, 2)
            self.is_calibrated = True
            print(f"[CALIBRATION] Baseline updated to: {self.baseline_slouch_ratio:.2f}")
            try:
                winsound.Beep(1200, 150)
                winsound.Beep(1600, 200)
            except Exception:
                pass

def main():
    print("==================================================================")
    print("  Digital Wellness Monitor - Posture & Eye Blink Detection AI")
    print("==================================================================")
    print("  Controls:")
    print("    [C]  - Calibrate Upright Sitting Baseline")
    print("    [R]  - Reset Session Counters")
    print("    [Q] / [ESC] - Exit Application")
    print("==================================================================")

    monitor = PostureWellnessMonitor()
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("[ERROR] Could not open webcam (camera index 0). Please check camera connections.")
        return

    # Set camera resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    last_ratio = 0.50

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[WARNING] Empty frame received from webcam.")
                break

            # Mirror view for intuitive user experience
            frame = cv2.flip(frame, 1)

            processed_frame = monitor.process_frame(frame)

            cv2.imshow("Digital Wellness Monitor | Sitting Posture Analysis", processed_frame)

            key = cv2.waitKey(1) & 0xFF
            if key in [ord('q'), ord('Q'), 27]: # 27 is ESC
                break
            elif key in [ord('c'), ord('C')]:
                # Calibrate current slouch ratio
                monitor.calibrate(monitor.baseline_slouch_ratio)
            elif key in [ord('r'), ord('R')]:
                monitor.blink_count = 0
                monitor.total_frames = 0
                monitor.good_frames = 0
                print("[RESET] Session metrics reset.")

    finally:
        cap.release()
        cv2.destroyAllWindows()
        monitor.close()
        print("\nSession completed.")
        if monitor.total_frames > 0:
            score = (monitor.good_frames / monitor.total_frames) * 100
            print(f"Overall Posture Score: {score:.1f}% | Total Blinks: {monitor.blink_count}")

if __name__ == "__main__":
    main()
