# FitMentor AI - context for Claude Code

Owner: Karthika Krishna M (KK), B.E. CSE, Anna University Regional Campus Tirunelveli.
Academic project; she presents/demos it to her professor (15 min) - keep things demo-safe.
She is learning: explain changes simply, she will rebuild the project herself later.

## What it is
Streamlit web app: webcam -> streamlit-webrtc -> MediaPipe Pose Landmarker (33 landmarks)
-> rule-based detectors (joint angles + 2-threshold FSM) count reps and flag form faults
-> Groq LLM turns the fault into a short cue -> gTTS speaks it -> SQLite stores history.
Rules decide WHAT is wrong; the LLM only words it. Architecture adapted from
github.com/shradha-khapra/ai-gym-coach (credited in README).

## Layout
- main.py - UI, workout loop (0.25 s rerun while camera plays), webrtc_streamer (NO rtc_configuration on purpose: streamlit-webrtc picks TURN via HF_TOKEN / Twilio env vars automatically)
- core/base_exercise.py - calculate_angle(), abstract detector
- detectors/ - squat, pushup, biceps_curl, shoulder_press, lunges
- services/vision/exercise_video_processor.py - VideoProcessorClass (worker thread, lock-guarded metrics, on_ended closes landmarker); model_loader.py (atomic download of pose_landmarker_full.task into ml_models/, gitignored)
- services/tracking/metrics.py - sync_metrics_update(): worker metrics -> session_state, sets, persistence, voice events
- services/coaching/ - voice_pipeline.py (5 s cooldown, never raises), llm.py (auto-selects a Groq model, see below), tts.py
- services/persistence/exercise_repository.py - SQLite users/exercises (same-day aggregation); services/paths.py - absolute paths
- tests/ - 65 pytest tests (pytest -q). Real-photo test skips without scikit-image.
- Dockerfile/.dockerignore/deploy_hf.sh - HF Spaces path; NOT used now (HF free tier can't run Docker/CPU for her account)

## Environment
- Local: Windows 11, Git Bash UCRT64, uv venv at .venv (Python 3.13), mediapipe 1.0.1, streamlit 1.54.0
- Run: `source .venv/Scripts/activate && streamlit run main.py`
- .env (gitignored): GROQ_API_KEY=..., optional HF_TOKEN=..., optional GROQ_MODEL=...
- Remotes: origin = github.com/KARTHIKAKRISHNA123/fitmentor-ai ; `space` = old HF Space (abandoned; can `git remote remove space`)
- Writing files from some sandboxes fails on delete/rename (sed -i leaves temp files) - prefer direct edits.

## Recent changes (uncommitted at handoff - commit them)
1. services/coaching/llm.py: Groq retired llama-3.3-70b-versatile (404 model_not_found). Coach now picks the first available of PREFERRED_MODELS = [qwen/qwen3.8-27b, openai/gpt-oss-20b, openai/gpt-oss-120b, llama-3.3-70b-versatile] via client.models.list(); on model_not_found it switches once. gpt-oss needs reasoning_effort="low" + max_tokens 300 (else empty reply). <think> blocks stripped. Verified live: qwen/qwen3.8-27b, ~0.2 s, good cues.
2. main.py: sidebar warning when voice coach is off (no GROQ_API_KEY); history time rounded to int.
3. services/tracking/metrics.py: time saved as whole seconds; tests updated.
4. Tests: 64 passed, 1 skipped on her machine after these changes.
Commit: `git add -A && git commit -m "fix: auto-select available Groq model, voice-off warning, whole-second times" && git push origin main`
Also update README mentions of "Llama 3.3 70B" -> "Groq-hosted LLM (auto-selected, currently Qwen3)".

## OPEN ISSUE: Streamlit Community Cloud deploy fails
App: fitmentor-ai-joy3gkwc2dcyqjxvafcbg2.streamlit.app (Debian trixie, Python 3.14.7 was chosen at deploy).
Error at `import cv2` in services/vision/exercise_video_processor.py (message redacted; full text in Manage app -> logs - GET IT FIRST).
Already checked: opencv-contrib-python 5.0.0.93 (pulled by mediapipe 1.0.1) only needs system libs libGL, libglib/libgthread, libSM, libICE, libX11, libXext, libxcb - all installed by packages.txt (libgl1, libglib2.0-0t64, libsm6, libxext6, libegl1, libgles2). So likely not a missing apt lib; suspects: Python 3.14 compatibility of the wheel / numpy, or something in the full traceback.
Recommended next steps:
1. Read full log line after the traceback.
2. Delete the app and redeploy with Advanced settings -> Python 3.11 (version can only be chosen at deploy), secrets GROQ_API_KEY + HF_TOKEN.
3. If still failing, try adding `opencv-python-headless` (same 5.0.x line) or pinning mediapipe/opencv versions with cp311 wheels, and test with `uv pip compile --python-version 3.11`.
Pandas is `pandas>=2.2.3` so Python 3.14 gets a wheel (2.2.3 had none -> slow source build).

## Demo plan (for tomorrow) - run on localhost, not the cloud
Exercise: Biceps Curls (water bottle), 1 set x 3-5 reps, front-facing, upper body in frame.
Show: clean reps -> counter; torso swing -> "SWINGING" + spoken cue; set completed cue; history table.
Explain: angle formula, two-threshold FSM (curl: <50 up, >160 down), two threads + lock, LLM only words the cue, 5 s cooldown, fails safe.
Keep a screen recording as backup. README has architecture/UML/DFD for slides.

## Not done yet
- Live demo GIF for README (docs/images/04_live_demo.gif) - she must record it.
- Project report .docx (40 pages, OHS352 format) generator exists in the Cowork outputs folder, not in this repo.
- LICENSE file (MIT suggested).
