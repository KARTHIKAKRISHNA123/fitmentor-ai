import pytest

from services.persistence import exercise_repository as repo


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(repo, "_DB_PATH", str(tmp_path / "test.db"))
    repo.init_db()
    yield
    repo._open_connection.clear()


def test_init_db_is_idempotent(temp_db):
    repo.init_db()
    repo.init_db()


def test_get_or_create_user_returns_same_id(temp_db):
    first = repo.get_or_create_user("karthika")
    again = repo.get_or_create_user("karthika")
    other = repo.get_or_create_user("someone_else")
    assert first["id"] == again["id"]
    assert other["id"] != first["id"]


def test_same_exercise_same_day_is_aggregated(temp_db):
    uid = repo.get_or_create_user("karthika")["id"]
    repo.add_exercise(uid, "Squats", reps=10, sets=1, time=30)
    repo.add_exercise(uid, "Squats", reps=10, sets=1, time=25)
    repo.add_exercise(uid, "Lunges", reps=8, sets=1, time=40)

    rows = {r["exercise_name"]: r for r in repo.get_users_exercises(uid)}
    assert len(rows) == 2
    assert rows["Squats"]["reps"] == 20
    assert rows["Squats"]["sets"] == 2
    assert rows["Squats"]["time"] == 55
    assert rows["Lunges"]["reps"] == 8


def test_history_is_per_user(temp_db):
    a = repo.get_or_create_user("a")["id"]
    b = repo.get_or_create_user("b")["id"]
    repo.add_exercise(a, "Squats", 10, 1, 30)
    assert len(repo.get_users_exercises(a)) == 1
    assert len(repo.get_users_exercises(b)) == 0
