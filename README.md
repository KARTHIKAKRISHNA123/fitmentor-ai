---
title: FitMentor AI
emoji: 🏋️
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 8501
tags:
  - streamlit
  - computer-vision
  - mediapipe
pinned: false
short_description: "AI gym coach - live rep counting, form checks, voice cues"
---

# FitMentor AI

**An AI-powered, real-time gym coach that watches your webcam, counts your reps, checks your form, and speaks corrections back to you — live, while you're still mid-set.**

Built with Streamlit + WebRTC (video), Google MediaPipe BlazePose (pose estimation), five rule-based exercise detectors (Squats, Push-ups, Biceps Curls, Shoulder Press, Lunges), and a Groq-hosted Llama-3.3-70B model + gTTS for spoken coaching feedback.

This README is written as **explanation content, not just setup steps** — the goal is that you can read it top to bottom and understand *why* the code is structured the way it is, so that when you rebuild this yourself slowly later, you're not just retyping code, you know what each piece is for.

---

## 1. What the app actually does

1. You type a username and click **Start Session**.
2. You pick an exercise, a number of sets, and reps per set, then **Start Workout**.
3. Your webcam turns on inside the browser (via WebRTC).
4. Every frame is sent to MediaPipe's Pose Landmarker, which returns 33 body keypoints (shoulders, elbows, wrists, hips, knees, ankles, etc.) with (x, y) coordinates and a confidence/visibility score.
5. Those keypoints are turned into **joint angles** (e.g. the angle at your knee, formed by your hip–knee–ankle).
6. A small state machine watches that angle rise and fall and counts a rep every time you complete a full cycle (e.g. squat down past 100°, then back up past 160°).
7. At the same time, a second set of rules checks *how well* you did the rep (back too far forward? hips sagging? elbow drifting?).
8. If something's wrong, a short structured message ("Event: ongoing_form_check, Form Issue: hips sagging") is sent to an LLM (Llama 3.3 70B via Groq), which turns it into a short spoken coaching line.
9. That line is converted to speech (gTTS) and auto-played in your browser.
10. Completed sets are saved to a local SQLite database, so your workout history persists across sessions.

Nothing here is "trained" — there's no dataset, no model you fit yourself. It's **geometry + rules + a prompt-constrained LLM**, which is exactly why it's a good beginner-friendly project to rebuild: every piece is something you can reason about line by line.

---

## 2. Project structure

```
fitmentor-ai/
├── main.py                          # Streamlit entry point — UI + glue code
├── requirements.txt                 # Python dependencies (pinned versions)
├── requirements-dev.txt             # + pytest / scikit-image for the test suite
├── packages.txt                     # Linux system libs (used by Streamlit Community Cloud)
├── Dockerfile / .dockerignore       # Container recipe (used by Hugging Face Spaces)
├── deploy_hf.sh                     # One-command clean push to your Hugging Face Space
├── download_model.py                # Optional: manually pre-download the pose model
├── .env.example                     # Template for GROQ_API_KEY / HF_TOKEN
│
├── core/
│   └── base_exercise.py             # Shared angle-geometry math, used by every detector
│
├── detectors/                       # One file per exercise — the "brain" of rep counting
│   ├── squat.py
│   ├── pushup.py
│   ├── biceps_curl.py
│   ├── shoulder_press.py
│   └── lunges.py
│
├── services/
│   ├── paths.py                     # Absolute paths (project root, model, db, static)
│   ├── auth/login_wall.py           # Username-only session gate
│   ├── config/workout_config.py     # Exercise list, skeleton edges, LLM system prompt
│   ├── state/session_defaults.py    # Seeds Streamlit session_state on first load
│   ├── persistence/exercise_repository.py  # SQLite: users + exercises tables
│   ├── vision/
│   │   ├── exercise_video_processor.py     # Per-frame pose detection + overlay drawing
│   │   └── model_loader.py                 # Safe (atomic) download of the MediaPipe model
│   ├── coaching/
│   │   ├── llm.py                   # Groq chat-completion wrapper
│   │   ├── tts.py                   # gTTS wrapper
│   │   └── voice_pipeline.py        # Decides WHEN to speak + maps metrics -> issue text
│   ├── tracking/metrics.py          # Bridges video-thread metrics into session_state
│   └── ui/style_loader.py           # CSS / font injection helpers
│
├── tests/                           # 65 pytest tests (see Section 9)
├── static/style.css                 # Small visual polish
└── ml_models/                       # pose_landmarker_full.task lands here (gitignored)
```

**Why this shape?** Each folder is a layer, and each layer only talks to the layer directly below it:

`main.py` (UI) → `services/vision` (camera + pose) → `detectors/*` (exercise logic) → `core/base_exercise.py` (shared math)
                → `services/coaching/*` (LLM + speech)
                → `services/persistence` (database)

If you wanted to add a sixth exercise, you'd only ever touch `detectors/` and one line in `workout_config.py` — nothing else needs to change. That's the whole point of the layering.

---

## 3. The core idea: turning 3 points into an angle

Every single detector — squat, push-up, curl, press, lunge — ultimately does the same trick, implemented once in `core/base_exercise.py`:

```python
def calculate_angle(self, a, b, c):
    # a, b, c are (x, y) points; b is the joint vertex (e.g. the knee)
    ax, ay = a[0] - b[0], a[1] - b[1]      # vector from b to a
    cx, cy = c[0] - b[0], c[1] - b[1]      # vector from b to c
    dot = ax * cx + ay * cy
    mag_a = math.sqrt(ax**2 + ay**2)
    mag_c = math.sqrt(cx**2 + cy**2)
    cos_angle = max(-1.0, min(1.0, dot / (mag_a * mag_c)))
    return math.degrees(math.acos(cos_angle))
```

This is just the standard "angle between two vectors" formula: `cos(θ) = (A·B) / (|A||B|)`. For a squat, `a` = hip, `b` = knee, `c` = ankle — so this returns the angle *at the knee*. A straight leg is close to 180°; a deep squat pushes that down toward 90° or below.

**Why clamp to [-1, 1]?** Floating-point rounding can occasionally push the ratio to something like `1.0000000002`, which crashes `acos` (domain error). Clamping is a one-line defensive fix.

---

## 4. Counting reps: a 2-state machine, not a single threshold

A naive approach would be "if angle < 100°, count a rep." That double-counts constantly because of frame-to-frame noise near the threshold. Instead every detector uses **two** thresholds with hysteresis:

```python
if knee_angle < DOWN_THRESHOLD:        # e.g. 100°
    self.stage = "down"
if knee_angle >= UP_THRESHOLD and self.stage == "down":   # e.g. 160°
    self.stage = "up"
    self.reps += 1
```

A rep only counts on the **down → up transition**, and only once you've actually gone far enough down first. The gap between 100° and 160° acts as a buffer zone where nothing happens, which absorbs small jitter.

| Exercise | Primary angle | Down / Up thresholds |
|---|---|---|
| Squats | hip–knee–ankle | < 100° / ≥ 160° |
| Push-ups | shoulder–elbow–wrist | < 90° / > 160° |
| Biceps Curl | shoulder–elbow–wrist | < 50° (curled) / > 160° (extended) |
| Shoulder Press | shoulder–elbow–wrist | ≥ 160° (up) / < 90° (down) |
| Lunges | hip–knee–ankle (front leg) | < 100° / > 160° |

---

## 5. Form checking: a second signal on top of the first

Rep counting alone doesn't catch *bad* reps. Each detector also computes one or two extra signals:

- **Squats** — back angle (shoulder–hip–knee): too small means you're leaning too far forward.
- **Push-ups** — body-alignment angle (shoulder–hip–ankle) + hip height vs. the shoulder/ankle midpoint, to catch sagging or piked hips.
- **Biceps Curl** — horizontal elbow drift from the shoulder (cheating by swinging the upper arm), plus torso-lean angle (using `atan2` for a stable angle-from-vertical).
- **Shoulder Press** — 4-stage extension banding, plus back-arch angle.
- **Lunges** — torso lean + lateral balance offset between shoulder and hip midpoints.

All of this is still just coordinate geometry on the same 33 landmarks — no new data source, just more comparisons.

---

## 6. Threading: why there's a lock everywhere

`streamlit-webrtc` runs your video callback (`VideoProcessorClass.recv()`) on a **separate thread** from the one that renders your Streamlit page. Both threads touch the same "latest metrics" object, so `exercise_video_processor.py` guards every read/write with a `threading.Lock`:

```python
def set_latest_metrics(self, metrics):
    with self._lock:
        self._latest_metrics = metrics.copy()
```

`services/tracking/metrics.py` is the one place, once per Streamlit rerun, that safely pulls the latest numbers out of that locked object and pushes them into `st.session_state` — which is the only thing the UI code is allowed to read from.

---

## 7. The coaching pipeline: rules → LLM → speech

1. `voice_pipeline.py`'s `_find_form_issue()` looks at the detector's status fields (e.g. `depth_status == "TOO HIGH"`) and turns them into one plain-English sentence, or `None` if form looks fine.
2. That sentence, plus the current event (`workout_started`, `set_completed`, `ongoing_form_check`, etc.), is sent to `llm.py`, which calls Groq's `llama-3.3-70b-versatile` model under a **fixed system prompt** (`services/config/workout_config.py :: PROMPT`) that restricts the model to ~10–15 word, second-person, high-energy coaching lines.
3. The returned text goes to `tts.py` (gTTS), producing an MP3 in memory.
4. `main.py` auto-plays it via a hidden `st.audio(..., autoplay=True)`.
5. A 5-second cooldown (`voice_pipeline.py :: COOLDOWN_SECONDS`) stops non-critical feedback from firing every single frame — major events (start/set-complete/workout-complete) always speak regardless.

**If you don't set a `GROQ_API_KEY`, the app still works** — rep counting, form detection and the on-screen overlay all function normally; only the spoken coaching is silently disabled (`_init_voice_pipeline()` in `main.py` sets `voice_pipeline = None`).

---

## 8. The database

Two SQLite tables (`services/persistence/exercise_repository.py`):

- `users(id, username, created_at)` — one row per unique username, no password.
- `exercises(id, user_id, exercise_name, reps, sets, time, created_at)` — one row **per user, per exercise, per calendar day**. Finishing a second set of the same exercise on the same day updates the existing row instead of inserting a new one (`add_exercise()`'s same-day lookup).

The file lives at the project root as `data.db` and is gitignored — it's local, per-machine state, not something you commit.

---

## 9. Running it locally

```bash
cd /d/AIML/projects/fitmentor-ai
source .venv/Scripts/activate          # (PowerShell: .venv\Scripts\activate)
uv pip install -r requirements.txt
cp .env.example .env                   # then paste your free Groq key from https://console.groq.com
streamlit run main.py
```

`requirements.txt` pins `mediapipe==1.0.1` because it's the version that has wheels for **every** Python from 3.10 to 3.13 — your local venv is Python 3.13, the cloud image is Python 3.11, and 0.10.14 (what you first tried) stops at 3.12, which is exactly the error you hit at the very start.

The first time you press **Start Workout**, the app downloads the MediaPipe pose model (~9 MB) into `ml_models/` (`services/vision/model_loader.py`). It downloads to a temporary file and only renames it into place once complete, so an interrupted download can't leave a broken file behind. The model is gitignored — it's fetched, not committed.

`.env` is loaded automatically at startup (`load_dotenv()` in `main.py`). If you don't put a Groq key in it, the app still works — you just won't hear the voice coach.

### Running the tests

```bash
uv pip install -r requirements-dev.txt
pytest -q
```

65 tests cover: the angle maths, every detector's rep counting and form checks (driven by synthetic poses with exact joint angles), the coaching pipeline (cooldown, failure handling), the database, the metrics/sets logic, the full UI flow (login → plan → start → end → logout, via Streamlit's `AppTest`), and the real MediaPipe model on an actual photo. The real-photo test needs `scikit-image` (it's in `requirements-dev.txt`); everything else runs without it.

---

## 10. Pushing to GitHub

```bash
cd /d/AIML/projects/fitmentor-ai
rm -f .git/index.lock          # only if git complains the lock file exists
git rm -r -q --cached .        # untrack everything (your files stay on disk)...
git add -A                     # ...then re-track only what .gitignore allows
git commit -m "test: add test suite, cloud deploy config and robustness fixes"
git push origin main
```

The `git rm --cached` + `git add -A` pair matters: `.env` (while still empty) and a few `.pyc` files were committed early on. `.gitignore` only stops *new* files from being tracked, so without this step, the moment you paste your real Groq key into `.env` and run `git add .`, the key would be pushed to a public GitHub repo. `--cached` only untracks — it does not delete your local file.

The `LF will be replaced by CRLF` warnings you see on Windows are harmless — Git is just normalising line endings.

---

## 11. Deploying to Hugging Face Spaces (Docker)

Hugging Face retired its built-in Streamlit SDK in April 2025 — Streamlit apps on Spaces now run from a **Dockerfile**. This repo has one ready (`Dockerfile` + `.dockerignore`), and the YAML block at the top of this README tells the Space to use it (`sdk: docker`, `app_port: 8501`). Pushing this README is enough to switch a Space that was created as Gradio over to Docker.

What the Dockerfile does: Python 3.11 on Debian bookworm → installs the Linux libraries OpenCV and MediaPipe need (`libgl1 libglib2.0-0 libsm6 libxext6 libegl1 libgles2` — MediaPipe 1.x's native library refuses to load without the last two) → runs as user 1000 (a Spaces requirement) → installs `requirements.txt` → downloads the pose model *into the image* so the first visitor doesn't wait → starts Streamlit on port 8501 with XSRF protection off (required because Spaces show the app inside an iframe, where browsers block Streamlit's XSRF cookie).

**Step 1 — add two secrets** in your Space: *Settings → Variables and secrets → New secret*

| Name | Value | Why |
|---|---|---|
| `GROQ_API_KEY` | your Groq key | voice coaching |
| `HF_TOKEN` | a Hugging Face access token (*read* scope is enough) from huggingface.co/settings/tokens | lets `streamlit-webrtc` fetch a free **TURN relay** from Hugging Face. Without a TURN server the webcam stream usually hangs on "Connecting..." in the cloud, because the Space sits behind a proxy/NAT that plain STUN can't get through. |

That's why `main.py` no longer hard-codes `rtc_configuration`: when it's left out, `streamlit-webrtc` 0.64.5 looks for `HF_TOKEN` (or Twilio credentials) itself and falls back to Google's STUN server only if neither exists.

**Step 2 — push a clean snapshot.** Your Space already has a starter commit from Hugging Face, and Hugging Face also rejects pushes whose history contains binary files (the old `.pyc` files from your early commits). So instead of pushing your whole history, `deploy_hf.sh` pushes a fresh, history-free snapshot of your current commit:

```bash
cd /d/AIML/projects/fitmentor-ai
bash deploy_hf.sh
```

It refuses to run if you have uncommitted changes or if `.env` is still tracked (do Section 10 first), and it always switches you back to `main` afterwards — even if the push fails. Under the hood it's just: `git checkout --orphan hf-deploy` → `git rm -r --cached .` → `git add -A` → `git commit` → `git push space hf-deploy:main --force` → back to `main`.

When asked for a password, paste a Hugging Face token with **write** scope (not your account password). `--force` is safe here: it only overwrites the Space's auto-generated starter files, and your GitHub repo (`origin`) is untouched. Run `bash deploy_hf.sh` again whenever you want to redeploy.

**Step 3 — watch it build** on the Space page (*Logs* tab). The first build takes several minutes (MediaPipe is a big package). When it shows *Running*, open the app. If the camera prompt doesn't appear inside huggingface.co, use the ⋮ menu → *Embed this Space* and open the direct `https://karthikakrishna123-fitmentor-ai.hf.space` link — camera permissions are most reliable there.

Note: the free CPU Space has no persistent disk, so `data.db` (workout history) resets whenever the Space restarts or goes to sleep. That's fine for a demo; for permanent history you'd attach a storage bucket or an external database.

---

## 11a. Alternative: Streamlit Community Cloud

1. Push to GitHub (Section 10), go to **https://share.streamlit.io**, *New app* → your repo, branch `main`, main file `main.py`.
2. *App settings → Secrets*:
   ```toml
   GROQ_API_KEY = "your_groq_key"
   HF_TOKEN = "your_hf_read_token"
   ```
   Root-level secrets are also exposed as environment variables, so the TURN relay works here too.
3. Streamlit Cloud installs `requirements.txt` and the Linux packages in `packages.txt` automatically (it ignores the Dockerfile).

---

## 12. Rebuilding it yourself, slower — a suggested order

When you redo this project by hand, this is the order that makes each step buildable and testable on its own, rather than writing everything at once:

1. **`core/base_exercise.py`** — write `calculate_angle()` first, test it stand-alone with a few hand-picked coordinates where you know the answer (a right angle should give 90°).
2. **One detector (`detectors/squat.py`)** — get rep counting working against fake/mocked landmarks before touching a camera at all (see the test snippet below).
3. **`services/vision/exercise_video_processor.py`** — wire up MediaPipe + OpenCV to draw the skeleton, *without* the detector yet — just prove you can see landmarks on your own webcam.
4. **Connect steps 2 and 3** — feed real landmarks into the squat detector, watch the rep counter increment live.
5. **The other four detectors** — copy the squat detector's shape, change the landmark indices and thresholds.
6. **`services/persistence`** — SQLite tables, save a rep count after a set.
7. **`services/coaching`** — LLM + TTS last, once the numbers you're feeding it are already correct.

A quick way to test a detector without a webcam (used to verify this build):

```python
class FakeLandmark:
    def __init__(self, x, y, visibility=1.0):
        self.x, self.y, self.visibility = x, y, visibility

landmarks = [FakeLandmark(0, 0) for _ in range(33)]
landmarks[23] = FakeLandmark(0.5, 0.5)   # hip
landmarks[25] = FakeLandmark(0.5, 0.75)  # knee
landmarks[27] = FakeLandmark(0.5, 1.0)   # ankle -> straight leg, ~180°

from detectors.squat import SquatDetector
print(SquatDetector().process(landmarks))
```

---

## 13. Known limitations (be upfront about these if you present this)

- Thresholds are fixed constants tuned by eye, not calibrated per user.
- No dataset-based accuracy/precision numbers — verification was manual, exercise-by-exercise.
- Best results facing the camera front-on; some signals (e.g. push-up alignment) are more legible from the side.
- Username-only "auth" — fine for a personal/academic project, not for a real multi-user deployment.
- Requires network access for the coaching voice (Groq + gTTS); rep counting works fully offline. If Groq or gTTS fails mid-workout, the app logs a warning and keeps counting instead of crashing.
- On free cloud hosting, workout history (`data.db`) is not persistent across restarts.
- In the cloud, the webcam stream needs a TURN relay (`HF_TOKEN` secret) to connect reliably.

---

## 14. Credits

Architecture and implementation pattern adapted from the open-source reference project [`ai-gym-coach`](https://github.com/shradha-khapra/ai-gym-coach) by Shradha Khapra, rebuilt and extended here as **FitMentor AI**. Pose estimation via [Google MediaPipe](https://ai.google.dev/edge/mediapipe) BlazePose. Coaching language via [Groq](https://groq.com)-hosted Llama 3.3. Speech via [gTTS](https://github.com/pndurang/gTTS).
