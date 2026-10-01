"""
End-to-end UI flow using Streamlit's built-in AppTest runner (no browser
needed): login -> plan -> start workout -> end workout -> history -> logout.
"""
from types import SimpleNamespace

import pytest
import streamlit_webrtc
from streamlit.testing.v1 import AppTest

from tests.conftest import PROJECT_ROOT


@pytest.fixture
def app(tmp_path, monkeypatch):
    # No network calls to Groq from tests, and a throwaway database.
    monkeypatch.setenv("GROQ_API_KEY", "")
    from services.persistence import exercise_repository as repo
    monkeypatch.setattr(repo, "_DB_PATH", str(tmp_path / "ui.db"))
    at = AppTest.from_file(str(PROJECT_ROOT / "main.py"), default_timeout=60)
    at.run()
    yield at
    repo._open_connection.clear()


def login(at, name="karthika"):
    at.text_input[0].input(name)
    at.button[0].click()  # the form's "Start Session" submit button
    at.run()


def test_login_wall_is_shown_first(app):
    assert not app.exception
    assert app.title[0].value == "Welcome to FitMentor AI"


def test_empty_name_is_rejected(app):
    app.button[0].click()
    app.run()
    assert any("cannot be empty" in e.value for e in app.error)


def test_login_shows_workout_planner(app):
    login(app)
    assert not app.exception
    assert app.session_state["username"] == "karthika"
    options = app.sidebar.selectbox[0].options
    assert options == ["Squats", "Push-ups", "Biceps Curls (Dumbbell)", "Shoulder Press", "Lunges"]
    assert any("No workout history" in i.value for i in app.info)


def test_start_and_end_workout(app, monkeypatch):
    # AppTest has no real browser/server, and the WebRTC widget needs both.
    # Swap it for a stand-in that reports "camera not started yet" - the
    # real widget is exercised by booting the actual server (see README).
    started = {}

    def fake_webrtc_streamer(**kwargs):
        started.update(kwargs)
        return SimpleNamespace(state=SimpleNamespace(playing=False), video_processor=None)

    monkeypatch.setattr(streamlit_webrtc, "webrtc_streamer", fake_webrtc_streamer)

    login(app)
    app.sidebar.selectbox[0].select("Push-ups")
    app.sidebar.number_input(key="plan_sets").set_value(2)
    app.sidebar.number_input(key="plan_reps").set_value(5)
    app.sidebar.button(key="start_session_button").click()
    app.run()

    assert not app.exception, app.exception
    assert app.session_state["workout_started"] is True
    assert app.session_state["exercise_type"] == "Push-ups"
    assert app.session_state["target_sets"] == 2
    assert app.session_state["reps_per_set"] == 5
    sidebar_metric_labels = [m.label for m in app.sidebar.metric]
    assert "Elbow Angle" in sidebar_metric_labels
    assert "Hip Position" in sidebar_metric_labels
    # camera widget was created with our processor and no hard-coded ICE config
    assert started["key"] == "exercise-analysis"
    assert "rtc_configuration" not in started

    app.sidebar.button(key="end_session_button").click()
    app.run()
    assert not app.exception
    assert app.session_state["workout_started"] is False


def test_logout_returns_to_login(app):
    login(app)
    app.sidebar.button(key="logout_button").click()
    app.run()
    assert not app.exception
    assert app.title[0].value == "Welcome to FitMentor AI"
