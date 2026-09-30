import math
from abc import ABC, abstractmethod


class BaseExercise(ABC):
    """
    Shared base class for every exercise detector.

    Holds the two pieces of state every detector needs (rep count and the
    current finite-state-machine stage), plus the one geometry primitive
    every detector relies on: turning three landmarks into a joint angle.
    """

    def __init__(self):
        self.reps = 0
        self.stage = None

    def calculate_angle(self, a, b, c):
        """
        Returns the angle ABC (in degrees) at vertex b, formed by points a-b-c.
        Uses basic vector dot-product trigonometry:
            cos(theta) = (BA . BC) / (|BA| * |BC|)
        """
        ax, ay = a[0] - b[0], a[1] - b[1]
        cx, cy = c[0] - b[0], c[1] - b[1]

        dot = ax * cx + ay * cy

        mag_a = math.sqrt(ax ** 2 + ay ** 2)
        mag_c = math.sqrt(cx ** 2 + cy ** 2)

        if mag_a * mag_c == 0:
            return 0.0

        # Clamp to [-1, 1] to guard against floating-point drift pushing the
        # ratio fractionally outside the valid domain of arccos.
        cos_angle = max(-1.0, min(1.0, dot / (mag_a * mag_c)))

        return math.degrees(math.acos(cos_angle))

    def get_point(self, landmarks, idx):
        """Returns the normalised (x, y) coordinate of a landmark by index."""
        p = landmarks[idx]
        return (p.x, p.y)

    @abstractmethod
    def process(self, landmarks):
        """Given a frame's pose landmarks, return a metrics dict for this exercise."""
        pass

    @abstractmethod
    def reset(self):
        """Reset rep count and stage, e.g. when a new workout starts."""
        pass
