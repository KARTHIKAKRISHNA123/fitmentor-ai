import logging
import time

import streamlit as st

LOGGER = logging.getLogger(__name__)


class VoicePipeline:
    """
    Turns detector metrics + workout events into a spoken coaching cue.

    Two responsibilities:
    1. _find_form_issue: maps exercise-specific status fields to a plain-
       English description of what is wrong (or None if form looks fine).
    2. process_event: decides *whether* to speak (major events always speak;
       minor form checks are throttled to one cue every 5 seconds so the
       coach doesn't talk over every single frame).
    """

    COOLDOWN_SECONDS = 5

    def __init__(self, llm, tts):
        self.llm = llm
        self.tts = tts
        self.last_spoken_at = 0

    def _find_form_issue(self, exercise, metrics):
        if "issue" in metrics:
            return metrics["issue"]

        if exercise == "Squats":
            depth = metrics.get("depth_status", "")
            back_angle = metrics.get("back_angle", 180)
            if depth == "TOO HIGH":
                return "The user's squat is not deep enough - knees are not bending sufficiently."
            if isinstance(back_angle, (int, float)) and back_angle < 130:
                return "The user is leaning too far forward during the squat."

        elif exercise == "Push-ups":
            alignment = metrics.get("body_alignment", "")
            hip_status = metrics.get("hip_status", "")
            if alignment == "Poor Form":
                return "The user's body is not straight during the push-up."
            if hip_status == "SAGGING":
                return "The user's hips are sagging down during the push-up."
            if hip_status == "PIKED UP":
                return "The user's hips are too high - lower them to form a straight line."

        elif exercise == "Biceps Curls (Dumbbell)":
            swing = metrics.get("swing_status", "")
            shoulder = metrics.get("shoulder_status", "")
            if swing == "SWINGING":
                return "The user is swinging their torso during the curl - keep the body still."
            if shoulder == "ELBOW DRIFTING":
                return "The user's elbow is drifting away from their side during the curl."

        elif exercise == "Shoulder Press":
            back_arch = metrics.get("back_arch_status", "")
            if back_arch == "Excessive Arch":
                return "The user is arching their lower back excessively during the press."
            if back_arch == "Slight Arch":
                return "Slight back arch detected - encourage the user to brace their core."

        elif exercise == "Lunges":
            balance = metrics.get("balance_status", "")
            if balance == "OFF BALANCE":
                return "The user is losing balance during the lunge - feet should be hip-width apart."

        return None

    def process_event(self, event, exercise, metrics):
        issue = self._find_form_issue(exercise, metrics)
        now = time.time()

        is_major_event = event in ("workout_started", "set_completed", "workout_completed")

        if not is_major_event:
            if not issue:
                return None
            if now - self.last_spoken_at < self.COOLDOWN_SECONDS:
                return None

        # Start the cooldown *before* the network calls, so that if Groq or
        # gTTS is down we back off for 5 s instead of retrying on every rerun.
        self.last_spoken_at = now

        try:
            text = self.llm.give_feedback(event, issue)
        except Exception as e:
            # A coaching failure (no internet, rate limit, bad key...) must
            # never crash the workout - rep counting keeps going regardless.
            LOGGER.warning("LLM coaching failed for event %s: %s", event, e)
            return None

        try:
            voice = self.tts.speak(text)
        except Exception as e:
            # Still show the text cue on screen even if speech synthesis fails.
            LOGGER.warning("Text-to-speech failed: %s", e)
            voice = None

        return voice, text


def autoplay_audio(audio_bytes):
    if not audio_bytes:
        return
    st.markdown("<style>[data-testid='stAudio'] {display: none;}</style>", unsafe_allow_html=True)
    st.audio(audio_bytes, format="audio/mp3", autoplay=True)
