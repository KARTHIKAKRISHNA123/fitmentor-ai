from types import SimpleNamespace

import pytest

from services.coaching import voice_pipeline as vp_module
from services.coaching.llm import LLMCoach
from services.coaching.voice_pipeline import VoicePipeline


class FakeLLM:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def give_feedback(self, event, issue):
        self.calls.append((event, issue))
        if self.fail:
            raise ConnectionError("no internet")
        return f"cue for {event}"


class FakeTTS:
    def __init__(self, fail=False):
        self.fail = fail

    def speak(self, text):
        if self.fail:
            raise RuntimeError("gTTS down")
        return b"mp3-bytes"


@pytest.fixture
def clock(monkeypatch):
    now = {"t": 1000.0}
    monkeypatch.setattr(vp_module.time, "time", lambda: now["t"])
    return now


def test_major_events_always_speak(clock):
    vp = VoicePipeline(FakeLLM(), FakeTTS())
    for event in ["workout_started", "set_completed", "workout_completed"]:
        assert vp.process_event(event, "Squats", {}) == (b"mp3-bytes", f"cue for {event}")


def test_good_form_stays_quiet(clock):
    vp = VoicePipeline(FakeLLM(), FakeTTS())
    good = {"depth_status": "GOOD DEPTH", "back_angle": 170}
    assert vp.process_event("ongoing_form_check", "Squats", good) is None


def test_form_issue_speaks_then_cools_down(clock):
    llm = FakeLLM()
    vp = VoicePipeline(llm, FakeTTS())
    bad = {"depth_status": "TOO HIGH"}

    assert vp.process_event("ongoing_form_check", "Squats", bad) is not None
    clock["t"] += 2   # within the 5 s cooldown
    assert vp.process_event("ongoing_form_check", "Squats", bad) is None
    clock["t"] += 4   # 6 s later
    assert vp.process_event("ongoing_form_check", "Squats", bad) is not None
    assert len(llm.calls) == 2


def test_llm_failure_never_raises_and_backs_off(clock):
    llm = FakeLLM(fail=True)
    vp = VoicePipeline(llm, FakeTTS())
    assert vp.process_event("ongoing_form_check", "Push-ups", {"hip_status": "SAGGING"}) is None
    # immediately again -> suppressed by cooldown, so we don't hammer a dead API
    assert vp.process_event("ongoing_form_check", "Push-ups", {"hip_status": "SAGGING"}) is None
    assert len(llm.calls) == 1


def test_tts_failure_still_returns_text(clock):
    vp = VoicePipeline(FakeLLM(), FakeTTS(fail=True))
    assert vp.process_event("set_completed", "Lunges", {}) == (None, "cue for set_completed")


@pytest.mark.parametrize("exercise,metrics,needle", [
    ("Squats", {"depth_status": "TOO HIGH"}, "not deep enough"),
    ("Squats", {"depth_status": "GOOD DEPTH", "back_angle": 110}, "leaning"),
    ("Push-ups", {"body_alignment": "Poor Form"}, "not straight"),
    ("Push-ups", {"hip_status": "SAGGING"}, "sagging"),
    ("Push-ups", {"hip_status": "PIKED UP"}, "too high"),
    ("Biceps Curls (Dumbbell)", {"swing_status": "SWINGING"}, "swinging"),
    ("Biceps Curls (Dumbbell)", {"shoulder_status": "ELBOW DRIFTING"}, "elbow"),
    ("Shoulder Press", {"back_arch_status": "Excessive Arch"}, "arching"),
    ("Lunges", {"balance_status": "OFF BALANCE"}, "balance"),
])
def test_form_issue_mapping(exercise, metrics, needle):
    issue = VoicePipeline(FakeLLM(), FakeTTS())._find_form_issue(exercise, metrics)
    assert issue and needle in issue.lower()


def test_explicit_issue_wins():
    vp = VoicePipeline(FakeLLM(), FakeTTS())
    assert vp._find_form_issue("Squats", {"issue": "No pose detected!"}) == "No pose detected!"


# ------------------------------------------------------------------ LLMCoach
class FakeGroq:
    def __init__(self):
        self.requests = []
        completions = SimpleNamespace(create=self._create)
        self.chat = SimpleNamespace(completions=completions)

    def _create(self, **kwargs):
        self.requests.append(kwargs)
        msg = SimpleNamespace(content="  Drive through your heels!  ")
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def test_llm_coach_builds_prompt_and_trims_history(monkeypatch):
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    client = FakeGroq()
    coach = LLMCoach(client)

    for _ in range(12):
        text = coach.give_feedback("ongoing_form_check", "knees caving in")

    assert text == "Drive through your heels!"
    last = client.requests[-1]
    assert last["model"] == "llama-3.3-70b-versatile"
    assert last["messages"][0]["role"] == "system"
    assert last["messages"][-1]["content"] == "Event: ongoing_form_check Form Issue: knees caving in"
    assert len(coach.history) <= LLMCoach.MAX_HISTORY_MESSAGES


def test_llm_model_can_be_overridden(monkeypatch):
    monkeypatch.setenv("GROQ_MODEL", "some-other-model")
    client = FakeGroq()
    LLMCoach(client).give_feedback("workout_started", None)
    assert client.requests[-1]["model"] == "some-other-model"
