from pathlib import Path

# Absolute project root (the folder that contains main.py). Using this instead
# of os.getcwd() means the app finds its files no matter which directory
# `streamlit run` is launched from.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

STATIC_DIR = PROJECT_ROOT / "static"
MODEL_PATH = PROJECT_ROOT / "ml_models" / "pose_landmarker_full.task"
DB_PATH = PROJECT_ROOT / "data.db"
