from types import SimpleNamespace

import pytest

from services.tracking import metrics as metrics_module


class FakeSessionState(dict):
    """Behaves like st.session_state: both dict-style and attribute access."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as e:
            raise AttributeError(name) from e

    def __setattr__(self, name, value):
        self[name] = value


class FakeProcessor:
    def __init__(self, latest):
        self.latest = latest
        self.exercise = None

    def set_exercise(self, exercise):
        self.exercise = exercise

    def get_latest_metrics(self):
        return dict(self.latest)


class RecordingVoice:
    def __init__(self):
        self.events = []

    def process_event(self, event, exercise, metrics):
        self.events.append(event)
        return (b"audio", f"cue:{event}")


@pytest.fixture
def harness(monkeypatch):
    state = FakeSessionState(
        exercise_type="Squats", reps_per_set=3, target_sets=2, user_id=7,
        last_saved_sets_completed=0, set_cycle_started_at=0.0,
        last_notified_workout_complete=False,
    )
    saved = []
    voice = RecordingVoice()
    state.voice_pipeline = voice
    monkeypatch.setattr(metrics_module, "st", SimpleNamespace(session_state=state))
    monkeypatch.setattr(metrics_module, "add_exercise", lambda *a: saved.append(a))
    monkeypatch.setattr(metrics_module.time, "time", lambda: 100.0)
    return state, saved, voice


def ctx_with(latest):
    return SimpleNamespace(state=SimpleNamespace(playing=True), video_processor=FakeProcessor(latest))


def test_sets_are_derived_from_reps(harness):
    state, saved, voice = harness
    metrics_module.sync_metrics_update(ctx_with(
        {"reps": 4, "knee_angle": 120, "back_angle": 170, "depth_status": "TOO HIGH", "pose_detected": True}
    ))
    assert state.sets_completed == 1
    assert state.current_set_reps == 1
    assert state.knee_angle == 120
    assert saved == [(7, "Squats", 3, 1, 100)]
    assert "set_completed" in voice.events
    assert state.workout_completed is False


def test_workout_completion_fires_once(harness):
    state, saved, voice = harness
    ctx = ctx_with({"reps": 6, "depth_status": "STANDING", "pose_detected": True})
    metrics_module.sync_metrics_update(ctx)
    metrics_module.sync_metrics_update(ctx)
    assert state.workout_completed is True
    assert voice.events.count("workout_completed") == 1
    # both sets persisted in one go, and not double-saved on the next rerun
    assert saved == [(7, "Squats", 6, 2, 100)]


def test_no_pose_triggers_reposition_cue(harness):
    state, saved, voice = harness
    metrics_module.sync_metrics_update(ctx_with({"pose_detected": False}))
    assert "no_pose_detected" in voice.events


def test_nothing_happens_when_stream_not_playing(harness):
    state, saved, voice = harness
    ctx = SimpleNamespace(state=SimpleNamespace(playing=False), video_processor=FakeProcessor({"reps": 9}))
    metrics_module.sync_metrics_update(ctx)
    assert saved == [] and voice.events == []
