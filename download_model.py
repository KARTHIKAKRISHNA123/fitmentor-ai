"""
One-time setup script: downloads the MediaPipe BlazePose 'full' Pose
Landmarker model into ml_models/. Run this once after cloning the repo
and before starting the app:

    python download_model.py

The model file (~30 MB) is intentionally NOT committed to git (see
.gitignore) - it's a large binary asset that's better fetched fresh from
Google's official model store.
"""
import os
import urllib.request

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_full/float16/latest/pose_landmarker_full.task"
)
DEST_DIR = os.path.join(os.path.dirname(__file__), "ml_models")
DEST_PATH = os.path.join(DEST_DIR, "pose_landmarker_full.task")


def main():
    os.makedirs(DEST_DIR, exist_ok=True)

    if os.path.exists(DEST_PATH):
        print(f"Model already present at {DEST_PATH} - skipping download.")
        return

    print(f"Downloading MediaPipe Pose Landmarker (full) model to {DEST_PATH} ...")
    urllib.request.urlretrieve(MODEL_URL, DEST_PATH)
    size_mb = os.path.getsize(DEST_PATH) / (1024 * 1024)
    print(f"Done. Downloaded {size_mb:.1f} MB.")


if __name__ == "__main__":
    main()
