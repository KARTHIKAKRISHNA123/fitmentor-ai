import threading

import av
import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from streamlit_webrtc import VideoProcessorBase

from detectors.squat import SquatDetector
from detectors.pushup import PushUpDetector
from detectors.biceps_curl import BicepsCurlDetector
from detectors.shoulder_press import ShoulderPressDetector
from detectors.lunges import LungesDetector
from services.config.workout_config import POSE_CONNECTIONS
from services.paths import MODEL_PATH
from services.vision.model_loader import ensure_pose_model


class VideoProcessorClass(VideoProcessorBase):
    """
    Bridges the streamlit-webrtc video callback (its own thread) with the
    MediaPipe pose pipeline and the active exercise detector. Every piece of
    state shared with the main Streamlit thread is guarded by a lock.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._latest_metrics = None
        self._exercise_type = "Squats"

        # main.py already downloads the model on the main thread before the
        # camera starts; this is just a safety net.
        model_path = ensure_pose_model(MODEL_PATH)
        base_option = python.BaseOptions(model_asset_path=model_path)

        options = vision.PoseLandmarkerOptions(
            base_options=base_option,
            running_mode=vision.RunningMode.VIDEO,
            min_pose_detection_confidence=0.7,
            min_pose_presence_confidence=0.7,
            min_tracking_confidence=0.7,
            output_segmentation_masks=False,
        )
        self._landmarker = vision.PoseLandmarker.create_from_options(options)

        self._detectors = {
            "Squats": SquatDetector(),
            "Push-ups": PushUpDetector(),
            "Biceps Curls (Dumbbell)": BicepsCurlDetector(),
            "Shoulder Press": ShoulderPressDetector(),
            "Lunges": LungesDetector(),
        }

        self._frame_timestamps_ms = 0

    def on_ended(self):
        """Called by streamlit-webrtc when the camera stream stops (End
        Workout, Stop button, closed tab). Frees the native MediaPipe
        resources right away instead of waiting for garbage collection -
        matters on small cloud machines where many sessions come and go."""
        try:
            self._landmarker.close()
        except Exception:
            pass

    def set_latest_metrics(self, metrics):
        with self._lock:
            self._latest_metrics = metrics.copy()

    def get_latest_metrics(self):
        with self._lock:
            return None if self._latest_metrics is None else self._latest_metrics.copy()

    def set_exercise(self, exercise_type):
        with self._lock:
            self._exercise_type = exercise_type

    def get_exercise(self):
        with self._lock:
            return self._exercise_type

    def _draw_skeleton(self, img, landmarks):
        h, w = img.shape[:2]
        for start_idx, end_idx in POSE_CONNECTIONS:
            p1, p2 = landmarks[start_idx], landmarks[end_idx]
            if p1.visibility > 0.7 and p2.visibility > 0.7:
                cv2.line(
                    img,
                    (int(p1.x * w), int(p1.y * h)),
                    (int(p2.x * w), int(p2.y * h)),
                    (0, 255, 0), 8,
                )
        for lm in landmarks:
            if lm.visibility > 0.7:
                cv2.circle(img, (int(lm.x * w), int(lm.y * h)), 8, (255, 0, 0), -1)

    def _draw_no_pose_warnings(self, img):
        cv2.putText(img, "NO POSE DETECTED", (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)
        cv2.putText(img, "PLEASE FACE THE CAMERA", (30, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)

    def _draw_overlays(self, img, metrics, ex_type):
        h, _ = img.shape[:2]
        if ex_type == "Squats":
            text = f"DEPTH: {metrics['depth_status']}"
        elif ex_type == "Push-ups":
            text = f"BODY: {metrics['body_alignment']} | HIP: {metrics['hip_status']}"
        elif ex_type == "Biceps Curls (Dumbbell)":
            text = f"SWING: {metrics['swing_status']}"
        elif ex_type == "Shoulder Press":
            text = f"EXT: {metrics['extension_status']} | BACK: {metrics['back_arch_status']}"
        elif ex_type == "Lunges":
            text = f"BALANCE: {metrics['balance_status']}"
        else:
            return
        cv2.putText(img, text, (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    def recv(self, frame):
        # Mirror the frame so the user sees themselves like in a mirror.
        image = np.ascontiguousarray(cv2.flip(frame.to_ndarray(format="bgr24"), 1), dtype=np.uint8)

        # OpenCV frames are BGR; MediaPipe expects RGB.
        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=cv2.cvtColor(image, cv2.COLOR_BGR2RGB),
        )

        self._frame_timestamps_ms += 30
        result = self._landmarker.detect_for_video(mp_image, self._frame_timestamps_ms)

        if result.pose_landmarks:
            landmarks = result.pose_landmarks[0]
            self._draw_skeleton(image, landmarks)

            ex_type = self.get_exercise()
            detector = self._detectors.get(ex_type)

            if detector:
                metrics = detector.process(landmarks)
                metrics["pose_detected"] = True
                self._draw_overlays(image, metrics, ex_type)
                self.set_latest_metrics(metrics)
        else:
            self._draw_no_pose_warnings(image)
            with self._lock:
                if self._latest_metrics is not None:
                    self._latest_metrics["pose_detected"] = False
                else:
                    self._latest_metrics = {"pose_detected": False}

        return av.VideoFrame.from_ndarray(image, format="bgr24")
