import pytest

from core.base_exercise import BaseExercise
from tests.conftest import blank_pose, place_joint


class _Dummy(BaseExercise):
    def process(self, landmarks):
        return {}

    def reset(self):
        pass


@pytest.fixture
def ex():
    return _Dummy()


def test_right_angle(ex):
    assert ex.calculate_angle((0, 1), (0, 0), (1, 0)) == pytest.approx(90.0)


def test_straight_line_is_180(ex):
    assert ex.calculate_angle((0, -1), (0, 0), (0, 1)) == pytest.approx(180.0)


def test_same_direction_is_0(ex):
    assert ex.calculate_angle((1, 0), (0, 0), (2, 0)) == pytest.approx(0.0, abs=1e-6)


def test_zero_length_vector_returns_0_instead_of_crashing(ex):
    assert ex.calculate_angle((0, 0), (0, 0), (1, 0)) == 0.0


def test_floating_point_drift_is_clamped(ex):
    # Nearly-collinear points can push cos(theta) a hair past 1.0; must not raise.
    angle = ex.calculate_angle((1e-12, 1.0), (0, 0), (0, 1.0))
    assert 0.0 <= angle < 1e-3


@pytest.mark.parametrize("target", [30, 45, 90, 100, 135, 160, 179])
def test_place_joint_helper_produces_requested_angle(ex, target):
    lm = place_joint(blank_pose(), 23, 25, 27, target, b_pos=(0.5, 0.6))
    a, b, c = ex.get_point(lm, 23), ex.get_point(lm, 25), ex.get_point(lm, 27)
    assert ex.calculate_angle(a, b, c) == pytest.approx(target, abs=1e-6)
