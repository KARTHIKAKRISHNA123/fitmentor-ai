import os
import urllib.request

import streamlit as st

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_full/float16/latest/pose_landmarker_full.task"
)


def ensure_pose_model(model_path: str) -> str:
    """
    Makes sure the MediaPipe Pose Landmarker model file exists at
    model_path, downloading it from Google's official model store on first
    run if it's missing. This keeps the ~30 MB binary out of git while still
    working out of the box both locally and on Streamlit Community Cloud.
    """
    if os.path.exists(model_path):
        return model_path

    os.makedirs(os.path.dirname(model_path), exist_ok=True)

    with st.spinner("First-time setup: downloading the pose-detection model (~30 MB)..."):
        urllib.request.urlretrieve(MODEL_URL, model_path)

    return model_path
