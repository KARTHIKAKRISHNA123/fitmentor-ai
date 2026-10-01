"""
Each detector is driven through synthetic poses whose joint angles are set
exactly, so rep counting and form checks can be tested without a camera.
"""
from detectors.biceps_curl import BicepsCurlDetector
from detectors.lunges import LungesDetector
from detectors.pushup import PushUpDetector
from detectors.shoulder_press import ShoulderPressDetector
from detectors.squat import SquatDetector
from tests.conftest import blank_pose, place_joint


# ---------------------------------------------------------------- Squats
def squat_pose(knee_angle, lean=False, visibility=1.0):
    lm = blank_pose(visibility)
    # hip(23) - knee(25) - ankle(27), hip straight above the knee
    place_joint(lm, 23, 25, 27, knee_angle, b_pos=(0.5, 0.6))
    # shoulder(11) above the hip -> upright back (~180 deg) unless leaning
    lm[11].x, lm[11].y = (0.5 + 0.25, 0.45 + 0.05) if lean else (0.5, 0.2)
    lm[25].visibility = visibility
    return lm


def test_squat_counts_one_rep_per_full_cycle():
    d = SquatDetector()
    for angle in [175, 90, 175, 85, 170, 95, 165]:
        out = d.process(squat_pose(angle))
    assert out["reps"] == 3


def test_squat_half_rep_is_not_counted():
    d = SquatDetector()
    for angle in [175, 120, 175, 110, 175]:  # never below 100
        out = d.process(squat_pose(angle))
    assert out["reps"] == 0


def test_squat_jitter_near_threshold_counts_once():
    d = SquatDetector()
    for angle in [175, 95, 105, 98, 102, 99, 170, 158, 162]:
        out = d.process(squat_pose(angle))
    assert out["reps"] == 1


def test_squat_depth_status():
    d = SquatDetector()
    assert d.process(squat_pose(90))["depth_status"] == "GOOD DEPTH"
    # still in the down stage but rising above 100 -> not deep any more
    assert d.process(squat_pose(130))["depth_status"] == "TOO HIGH"
    assert d.process(squat_pose(170))["depth_status"] == "STANDING"


def test_squat_low_visibility_frames_do_not_count():
    d = SquatDetector()
    for angle in [175, 90, 175]:
        out = d.process(squat_pose(angle, visibility=0.3))
    assert out["reps"] == 0


def test_squat_reports_forward_lean():
    d = SquatDetector()
    assert d.process(squat_pose(90))["back_angle"] > 150
    assert d.process(squat_pose(90, lean=True))["back_angle"] < 130


def test_reset_clears_reps():
    d = SquatDetector()
    for angle in [175, 90, 175]:
        d.process(squat_pose(angle))
    d.reset()
    assert d.reps == 0 and d.stage is None


# ---------------------------------------------------------------- Push-ups
def pushup_pose(elbow_angle, hip_y=0.5):
    lm = blank_pose()
    lm[11].x, lm[11].y = 0.3, 0.5   # shoulder
    lm[23].x, lm[23].y = 0.5, hip_y  # hip
    lm[27].x, lm[27].y = 0.7, 0.5   # ankle
    # shoulder(11) - elbow(13) - wrist(15); keep the shoulder where it is
    place_joint(lm, 11, 13, 15, elbow_angle, b_pos=(0.3, 0.6), length=0.1)
    lm[11].x, lm[11].y = 0.3, 0.5
    return lm


def test_pushup_counts_reps():
    d = PushUpDetector()
    for angle in [170, 80, 170, 85, 165]:
        out = d.process(pushup_pose(angle))
    assert out["reps"] == 2


def test_pushup_level_body():
    out = PushUpDetector().process(pushup_pose(170))
    assert out["hip_status"] == "LEVEL"
    assert out["body_alignment"] == "Straight"


def test_pushup_sagging_hips():
    out = PushUpDetector().process(pushup_pose(170, hip_y=0.62))
    assert out["hip_status"] == "SAGGING"


def test_pushup_piked_hips():
    out = PushUpDetector().process(pushup_pose(170, hip_y=0.38))
    assert out["hip_status"] == "PIKED UP"


# ---------------------------------------------------------------- Biceps curl
def curl_pose(elbow_angle, swing=False, elbow_x=0.45):
    lm = blank_pose()
    shift = 0.15 if swing else 0.0
    lm[11].x, lm[11].y = 0.45 + shift, 0.3   # left shoulder
    lm[12].x, lm[12].y = 0.55 + shift, 0.3   # right shoulder
    lm[23].x, lm[23].y = 0.45, 0.6           # left hip
    lm[24].x, lm[24].y = 0.55, 0.6           # right hip
    place_joint(lm, 11, 13, 15, elbow_angle, b_pos=(elbow_x, 0.45), length=0.1)
    lm[11].x, lm[11].y = 0.45 + shift, 0.3
    return lm


def test_curl_counts_reps():
    d = BicepsCurlDetector()
    for angle in [170, 40, 170, 35, 165]:
        out = d.process(curl_pose(angle))
    assert out["reps"] == 2


def test_curl_stable_vs_swinging():
    d = BicepsCurlDetector()
    assert d.process(curl_pose(90))["swing_status"] == "NO SWING"
    assert d.process(curl_pose(90, swing=True))["swing_status"] == "SWINGING"


def test_curl_elbow_drift():
    d = BicepsCurlDetector()
    assert d.process(curl_pose(90))["shoulder_status"] == "STABLE"
    assert d.process(curl_pose(90, elbow_x=0.60))["shoulder_status"] == "ELBOW DRIFTING"


# ---------------------------------------------------------------- Shoulder press
def press_pose(elbow_angle, back_angle=180):
    lm = blank_pose()
    # shoulder(11) - hip(23) - knee(25): back angle at the hip
    place_joint(lm, 11, 23, 25, back_angle, b_pos=(0.5, 0.6), length=0.25)
    sx, sy = lm[11].x, lm[11].y
    # elbow angle at elbow(13), measured from the shoulder
    place_joint(lm, 11, 13, 15, elbow_angle, b_pos=(sx + 0.1, sy), length=0.1, base_dir=(-1.0, 0.0))
    return lm


def test_press_counts_reps():
    d = ShoulderPressDetector()
    for angle in [80, 170, 80, 165, 85]:
        out = d.process(press_pose(angle))
    assert out["reps"] == 2


def test_press_extension_bands():
    d = ShoulderPressDetector()
    assert d.process(press_pose(170))["extension_status"] == "FULL EXTENSION"
    assert d.process(press_pose(140))["extension_status"] == "NEARLY EXTENDED"
    assert d.process(press_pose(100))["extension_status"] == "PRESSING"
    assert d.process(press_pose(70))["extension_status"] == "START POSITION"


def test_press_back_arch():
    d = ShoulderPressDetector()
    assert d.process(press_pose(120, back_angle=175))["back_arch_status"] == "Neutral"
    assert d.process(press_pose(120, back_angle=150))["back_arch_status"] == "Slight Arch"
    assert d.process(press_pose(120, back_angle=120))["back_arch_status"] == "Excessive Arch"


# ---------------------------------------------------------------- Lunges
def lunge_pose(front_knee_angle, off_balance=False):
    lm = blank_pose()
    place_joint(lm, 23, 25, 27, front_knee_angle, b_pos=(0.45, 0.65))  # left (front) leg
    place_joint(lm, 24, 26, 28, 178, b_pos=(0.55, 0.65))               # right (back) leg straight
    shift = 0.2 if off_balance else 0.0
    lm[11].x, lm[11].y = 0.45 + shift, 0.2
    lm[12].x, lm[12].y = 0.55 + shift, 0.2
    return lm


def test_lunge_counts_reps_on_front_leg():
    d = LungesDetector()
    for angle in [175, 90, 175, 95, 170]:
        out = d.process(lunge_pose(angle))
    assert out["reps"] == 2
    assert abs(out["front_knee_angle"] - 170) <= 1


def test_lunge_balance():
    d = LungesDetector()
    assert d.process(lunge_pose(90))["balance_status"] == "BALANCED"
    assert d.process(lunge_pose(90, off_balance=True))["balance_status"] == "OFF BALANCE"


# ---------------------------------------------------------------- shared contract
def test_every_detector_returns_the_fields_the_ui_expects():
    from services.config.workout_config import METRICS_FIELDS
    detectors = {
        "Squats": (SquatDetector(), squat_pose(120)),
        "Push-ups": (PushUpDetector(), pushup_pose(120)),
        "Biceps Curls (Dumbbell)": (BicepsCurlDetector(), curl_pose(120)),
        "Shoulder Press": (ShoulderPressDetector(), press_pose(120)),
        "Lunges": (LungesDetector(), lunge_pose(120)),
    }
    for name, (det, pose) in detectors.items():
        out = det.process(pose)
        assert "reps" in out, name
        for field in METRICS_FIELDS[name]:
            assert field in out, f"{name} missing {field}"
