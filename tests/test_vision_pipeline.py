"""
Runs the real MediaPipe model through VideoProcessorClass.recv(), exactly
like a webcam frame would. Skipped automatically if the model file hasn't
been downloaded yet (run the app once, or `python download_model.py`).
"""
import numpy as np
import pytest

from services.paths import MODEL_PATH
from services.vision.model_loader import is_model_ready

pytestmark = pytest.mark.skipif(not is_model_ready(MODEL_PATH), reason="pose model not downloaded")


def _frame(img_bgr):
    import av
    return av.VideoFrame.from_ndarray(np.ascontiguousarray(img_bgr), format="bgr24")


@pytest.fixture
def processor():
    from services.vision.exercise_video_processor import VideoProcessorClass
    return VideoProcessorClass()


def test_empty_frame_reports_no_pose(processor):
    out = processor.recv(_frame(np.zeros((480, 640, 3), dtype=np.uint8)))
    assert out.width == 640 and out.height == 480
    assert processor.get_latest_metrics() == {"pose_detected": False}


def test_timestamps_keep_increasing_across_frames(processor):
    blank = _frame(np.zeros((240, 320, 3), dtype=np.uint8))
    for _ in range(5):
        processor.recv(blank)  # MediaPipe VIDEO mode raises if timestamps go backwards


def test_real_person_is_detected():
    skimage_data = pytest.importorskip("skimage.data")
    import cv2
    from services.vision.exercise_video_processor import VideoProcessorClass

    rgb = skimage_data.astronaut()  # public-domain NASA portrait, ships with scikit-image
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    for exercise in ["Squats", "Push-ups", "Biceps Curls (Dumbbell)", "Shoulder Press", "Lunges"]:
        proc = VideoProcessorClass()
        proc.set_exercise(exercise)
        for _ in range(3):
            proc.recv(_frame(bgr))
        metrics = proc.get_latest_metrics()
        assert metrics["pose_detected"] is True, exercise
        assert "reps" in metrics, exercise
