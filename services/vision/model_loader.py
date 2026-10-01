import logging
import os
import urllib.request
from pathlib import Path

LOGGER = logging.getLogger(__name__)

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_full/float16/latest/pose_landmarker_full.task"
)

# The real file is ~9 MB. Anything far smaller is a failed / partial download.
_MIN_VALID_BYTES = 1_000_000


def is_model_ready(model_path) -> bool:
    path = Path(model_path)
    return path.exists() and path.stat().st_size >= _MIN_VALID_BYTES


def ensure_pose_model(model_path) -> str:
    """
    Makes sure the MediaPipe Pose Landmarker model exists at model_path,
    downloading it from Google's official model store if it's missing.

    The download goes to a temporary file first and is only renamed into
    place once complete, so an interrupted download can never leave a
    half-written file that MediaPipe would later choke on.

    Deliberately has no Streamlit calls in it: it may be called from the
    WebRTC worker thread, where st.* functions don't work.
    """
    path = Path(model_path)
    if is_model_ready(path):
        return str(path)

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".part")

    LOGGER.info("Downloading pose model to %s", path)
    try:
        urllib.request.urlretrieve(MODEL_URL, tmp_path)
        if tmp_path.stat().st_size < _MIN_VALID_BYTES:
            raise RuntimeError("Downloaded pose model is unexpectedly small.")
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

    return str(path)
