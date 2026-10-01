import math
import sys
from pathlib import Path

import pytest

# Make `import core...`, `import services...` work when running `pytest` from
# the project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class FakeLandmark:
    """Stands in for a MediaPipe landmark: normalised x, y and a visibility score."""

    def __init__(self, x=0.5, y=0.5, visibility=1.0):
        self.x = x
        self.y = y
        self.visibility = visibility


def blank_pose(visibility=1.0):
    """33 landmarks, all in the middle of the frame and fully visible."""
    return [FakeLandmark(0.5, 0.5, visibility) for _ in range(33)]


def place_joint(lm, a_idx, b_idx, c_idx, angle_deg, b_pos, length=0.15, base_dir=(0.0, -1.0)):
    """
    Positions three landmarks so that the angle a-b-c (at vertex b) equals
    angle_deg exactly. Point a sits `length` away from b along base_dir and
    point c sits `length` away along base_dir rotated by angle_deg.
    """
    bx, by = b_pos
    dx, dy = base_dir
    theta = math.radians(angle_deg)
    rx = dx * math.cos(theta) - dy * math.sin(theta)
    ry = dx * math.sin(theta) + dy * math.cos(theta)
    lm[b_idx].x, lm[b_idx].y = bx, by
    lm[a_idx].x, lm[a_idx].y = bx + dx * length, by + dy * length
    lm[c_idx].x, lm[c_idx].y = bx + rx * length, by + ry * length
    return lm


@pytest.fixture
def fake_pose():
    return blank_pose
