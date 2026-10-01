# Container used by Hugging Face Spaces (Docker SDK). Hugging Face retired its
# built-in Streamlit SDK in 2025, so Streamlit apps now ship their own image.
FROM python:3.11-slim-bookworm

# System libraries needed on a headless Linux server (same list as
# packages.txt, which Streamlit Community Cloud uses instead):
#   libgl1, libglib2.0-0, libsm6, libxext6 -> OpenCV
#   libegl1, libgles2                      -> MediaPipe 1.x's native library
#                                             (it fails to load without them)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libsm6 libxext6 libegl1 libgles2 curl \
    && rm -rf /var/lib/apt/lists/*

# Spaces run containers as user ID 1000.
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1
WORKDIR $HOME/app

# Install dependencies first so code-only changes rebuild quickly.
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY --chown=user . .

# Bake the pose model into the image so the first visitor doesn't wait for it.
RUN python -c "from services.paths import MODEL_PATH; from services.vision.model_loader import ensure_pose_model; ensure_pose_model(MODEL_PATH)"

EXPOSE 8501
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# enableXsrfProtection=false is required on Spaces: the app is shown inside an
# iframe on huggingface.co, where browsers block Streamlit's XSRF cookie.
CMD ["streamlit", "run", "main.py", \
     "--server.port=8501", "--server.address=0.0.0.0", \
     "--server.enableXsrfProtection=false", "--browser.gatherUsageStats=false"]
