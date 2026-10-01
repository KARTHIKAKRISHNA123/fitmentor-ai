import os
import time

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from groq import Groq
from streamlit_webrtc import WebRtcMode, webrtc_streamer

from services.auth.login_wall import render_login_wall
from services.coaching.llm import LLMCoach
from services.coaching.tts import TextToSpeech
from services.coaching.voice_pipeline import VoicePipeline, autoplay_audio
from services.config.workout_config import EXERCISE_OPTIONS
from services.paths import MODEL_PATH, STATIC_DIR
from services.persistence.exercise_repository import get_users_exercises, init_db
from services.state.session_defaults import initial_session_defaults
from services.tracking.metrics import sync_metrics_update
from services.ui.style_loader import inject_local_font, inject_webrtc_styles, load_css
from services.vision.exercise_video_processor import VideoProcessorClass
from services.vision.model_loader import ensure_pose_model, is_model_ready

# Load GROQ_API_KEY / HF_TOKEN from a local .env file when running on your own
# machine. On Hugging Face / Streamlit Cloud the same names come from the
# platform's secrets settings instead, and this is simply a no-op.
load_dotenv()


def _get_secret(name):
    """Reads a setting from the environment (.env locally, Space secrets on
    Hugging Face) and falls back to Streamlit's secrets.toml if present."""
    value = os.environ.get(name, "")
    if value:
        return value
    try:
        return st.secrets.get(name, "")
    except Exception:
        # No secrets.toml at all - perfectly normal when using .env instead.
        return ""


def _init_voice_pipeline():
    """Builds the LLM + TTS coaching pipeline once per session. If no Groq
    API key is configured, voice coaching is silently disabled - rep
    counting and form detection keep working either way."""
    if "voice_pipeline" in st.session_state:
        return

    try:
        api_key = _get_secret("GROQ_API_KEY")

        if not api_key:
            st.session_state.voice_pipeline = None
            return

        groq_client = Groq(api_key=api_key)
        llm_coach = LLMCoach(groq_client)
        tts = TextToSpeech()
        st.session_state.voice_pipeline = VoicePipeline(llm_coach, tts)
    except Exception:
        st.session_state.voice_pipeline = None


def _ensure_model_ready():
    """Downloads the pose model on the main thread (where a spinner and a
    friendly error can be shown) before the camera worker needs it."""
    if is_model_ready(MODEL_PATH):
        return True
    try:
        with st.spinner("First-time setup: downloading the pose-detection model (~9 MB)..."):
            ensure_pose_model(MODEL_PATH)
        return True
    except Exception as e:
        st.error(
            f"Couldn't download the pose-detection model ({e}). "
            "Check your internet connection and reload the page."
        )
        return False


def _logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def _render_sidebar_plan():
    plan_exercise = st.selectbox("Exercise", options=EXERCISE_OPTIONS, key="plan_exercise")
    plan_sets = st.number_input("Sets", min_value=0, max_value=50, key="plan_sets", step=1)
    plan_reps = st.number_input("Reps per Set", min_value=0, max_value=50, key="plan_reps", step=1)

    st.markdown("")
    start_session_button = st.button("Start Workout", width="stretch", key="start_session_button")

    if start_session_button:
        st.session_state.exercise_type = plan_exercise
        st.session_state.target_sets = int(plan_sets)
        st.session_state.reps_per_set = int(plan_reps)
        st.session_state.reps = 0
        st.session_state.sets_completed = 0
        st.session_state.current_set_reps = 0
        st.session_state.workout_completed = False
        st.session_state.audio_to_play = None
        st.session_state.coach_feedback = None
        st.session_state.workout_started = True
        st.session_state.set_cycle_started_at = time.time()
        st.session_state.last_saved_sets_completed = 0
        st.session_state.last_notified_workout_complete = False

        if st.session_state.get("voice_pipeline"):
            result = st.session_state.voice_pipeline.process_event(
                event="workout_started", exercise=plan_exercise, metrics={}
            )
            if result:
                st.session_state.audio_to_play, st.session_state.coach_feedback = result

        st.rerun()


def _render_sidebar_active():
    exercise = st.session_state.get("exercise_type")
    sets = st.session_state.get("target_sets")
    reps = st.session_state.get("reps_per_set")

    st.info(f"**{exercise}** -- {sets} Sets / {reps} Reps")

    end_session_button = st.button("End Workout", key="end_session_button", width="stretch")

    if end_session_button:
        st.session_state.workout_started = False
        if st.session_state.get("voice_pipeline"):
            result = st.session_state.voice_pipeline.process_event(
                event="workout_completed", exercise=exercise, metrics={}
            )
            if result:
                st.session_state.audio_to_play, st.session_state.coach_feedback = result
        st.rerun()

    st.divider()
    st.subheader("Progress")
    st.metric("Total Reps", f"{st.session_state.get('reps')}")
    st.metric("Current Set Reps", f"{st.session_state.get('current_set_reps')} / {reps}")
    st.metric("Sets Completed", f"{st.session_state.get('sets_completed')} / {sets}")

    st.divider()

    if exercise == "Squats":
        st.subheader("Squat Metrics")
        st.metric("Knee Angle", f"{st.session_state.knee_angle}°")
        st.metric("Back Angle", f"{st.session_state.back_angle}°")
        st.metric("Depth Status", st.session_state.depth_status)
    elif exercise == "Push-ups":
        st.subheader("Push-up Metrics")
        st.metric("Elbow Angle", f"{st.session_state.elbow_angle}°")
        st.metric("Body Alignment", st.session_state.body_alignment)
        st.metric("Hip Position", st.session_state.hip_status)
    elif exercise == "Biceps Curls (Dumbbell)":
        st.subheader("Curl Metrics")
        st.metric("Elbow Angle", f"{st.session_state.elbow_angle}°")
        st.metric("Shoulder Stability", st.session_state.shoulder_status)
        st.metric("Swing Detection", st.session_state.swing_status)
    elif exercise == "Shoulder Press":
        st.subheader("Shoulder Press Metrics")
        st.metric("Elbow Angle", f"{st.session_state.elbow_angle}°")
        st.metric("Arm Extension", st.session_state.extension_status)
        st.metric("Back Arch", st.session_state.back_arch_status)
    elif exercise == "Lunges":
        st.subheader("Lunge Metrics")
        st.metric("Front Knee Angle", f"{st.session_state.front_knee_angle}°")
        st.metric("Torso Angle", f"{st.session_state.torso_angle}°")
        st.metric("Balance Status", st.session_state.balance_status)


def _render_history():
    st.divider()
    st.markdown("#### Workout History")

    user_id = st.session_state.get("user_id", 0)
    history_rows = get_users_exercises(user_id)

    arr = [
        {
            "Exercise": row["exercise_name"],
            "Reps": row["reps"],
            "Sets": row["sets"],
            "Time (sec)": row["time"],
            "Date": row["created_at"],
        }
        for row in history_rows
    ]
    df = pd.DataFrame(arr)

    if not df.empty:
        df["Date"] = pd.to_datetime(df["Date"]).dt.date
        agg_df = (
            df.groupby(["Exercise", "Date"])
            .agg({"Reps": "sum", "Sets": "sum", "Time (sec)": "sum"})
            .reset_index()
        )
        agg_df.index += 1
        st.table(agg_df)
    else:
        st.info("No workout history found yet - finish a set to see it here.")


def main():
    st.set_page_config(
        page_icon="🏋️‍♀️",
        page_title="FitMentor AI",
        initial_sidebar_state="expanded",
        layout="centered",
    )

    load_css(str(STATIC_DIR / "style.css"))
    inject_local_font(str(STATIC_DIR / "AdobeClean.otf"), "AdobeClean")

    init_db()

    if not render_login_wall():
        return

    initial_session_defaults()
    _init_voice_pipeline()

    workout_started = st.session_state.get("workout_started", False)

    with st.sidebar:
        st.title("🏋️‍♂️ FitMentor AI Coach")
        if st.session_state.get("username"):
            st.caption(f"👤 Logged in as {st.session_state['username']}")

        st.divider()
        st.subheader("Workout Plan")

        if not workout_started:
            _render_sidebar_plan()
            st.divider()
            st.button("Log out", key="logout_button", width="stretch", on_click=_logout)
        else:
            _render_sidebar_active()

    st.title("FitMentor AI")
    st.markdown("#### Real-time pose detection with proactive AI voice coaching")

    if st.session_state.get("audio_to_play"):
        autoplay_audio(st.session_state.audio_to_play)

    if st.session_state.get("coach_feedback"):
        st.markdown("")
        st.success(f"🤖 **Coach:** {st.session_state.coach_feedback}")

    if not workout_started:
        st.markdown(
            """
            <div style="
                border: 10px dashed #444;
                border-radius: 0px;
                padding: 48px 32px;
                text-align: center;
                color: #888;
                margin-top: 32px;
                margin-bottom: 32px;
            ">
                <h2 style="color:#ccc; margin-bottom:8px;">👈 Set your workout plan</h2>
                <p style="font-size:1.05rem;">
                    Choose your exercise, sets and reps in the sidebar,<br>
                    then click <strong>Start Workout</strong> to activate the camera and AI coach.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif _ensure_model_ready():
        # No rtc_configuration on purpose: streamlit-webrtc then picks the ICE
        # servers itself - a TURN relay if HF_TOKEN (or Twilio credentials)
        # is set in the environment, otherwise Google's public STUN server.
        # A TURN relay is what makes the webcam connect reliably when the app
        # is hosted in the cloud (Hugging Face / Streamlit Cloud).
        st.caption(
            "Press **START** below and allow camera access. Stand back so your "
            "whole body is in frame (side-on works best for push-ups)."
        )
        context = webrtc_streamer(
            key="exercise-analysis",
            mode=WebRtcMode.SENDRECV,
            video_processor_factory=VideoProcessorClass,
            media_stream_constraints={"video": True, "audio": False},
            async_processing=True,
        )

        sync_metrics_update(context)

        if context.state.playing:
            time.sleep(0.25)
            st.rerun()

        inject_webrtc_styles()

    _render_history()


if __name__ == "__main__":
    main()
