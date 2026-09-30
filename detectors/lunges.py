from core.base_exercise import BaseExercise


class LungesDetector(BaseExercise):
    DOWN_THRESHOLD = 100
    UP_THRESHOLD = 160
    MIN_VISIBILITY = 0.7
    BALANCE_TOLERANCE = 0.10

    LEFT_HIP, LEFT_KNEE, LEFT_ANKLE = 23, 25, 27
    RIGHT_HIP, RIGHT_KNEE, RIGHT_ANKLE = 24, 26, 28
    LEFT_SHOULDER, RIGHT_SHOULDER = 11, 12

    def __init__(self):
        super().__init__()

    def reset(self):
        self.reps = 0
        self.stage = None

    def process(self, landmarks):
        left_knee_angle = self.calculate_angle(
            self.get_point(landmarks, self.LEFT_HIP),
            self.get_point(landmarks, self.LEFT_KNEE),
            self.get_point(landmarks, self.LEFT_ANKLE),
        )
        right_knee_angle = self.calculate_angle(
            self.get_point(landmarks, self.RIGHT_HIP),
            self.get_point(landmarks, self.RIGHT_KNEE),
            self.get_point(landmarks, self.RIGHT_ANKLE),
        )

        if left_knee_angle <= right_knee_angle:
            front_knee_angle = left_knee_angle
            front_hip_idx, front_knee_idx, front_ankle_idx = self.LEFT_HIP, self.LEFT_KNEE, self.LEFT_ANKLE
            shoulder_idx_for_torso = self.LEFT_SHOULDER
        else:
            front_knee_angle = right_knee_angle
            front_hip_idx, front_knee_idx, front_ankle_idx = self.RIGHT_HIP, self.RIGHT_KNEE, self.RIGHT_ANKLE
            shoulder_idx_for_torso = self.RIGHT_SHOULDER

        key_landmarks_visible = (
            landmarks[front_hip_idx].visibility > self.MIN_VISIBILITY and
            landmarks[front_knee_idx].visibility > self.MIN_VISIBILITY and
            landmarks[front_ankle_idx].visibility > self.MIN_VISIBILITY
        )

        if key_landmarks_visible:
            if front_knee_angle < self.DOWN_THRESHOLD:
                self.stage = "down"
            if front_knee_angle > self.UP_THRESHOLD and self.stage == "down":
                self.stage = "up"
                self.reps += 1

        torso_angle = self.calculate_angle(
            self.get_point(landmarks, shoulder_idx_for_torso),
            self.get_point(landmarks, front_hip_idx),
            self.get_point(landmarks, front_knee_idx),
        )

        shoulder_mid_x = (landmarks[self.LEFT_SHOULDER].x + landmarks[self.RIGHT_SHOULDER].x) / 2
        hip_mid_x = (landmarks[self.LEFT_HIP].x + landmarks[self.RIGHT_HIP].x) / 2
        lateral_offset = abs(shoulder_mid_x - hip_mid_x)
        balance_status = "BALANCED" if lateral_offset <= self.BALANCE_TOLERANCE else "OFF BALANCE"

        return {
            "reps": self.reps,
            "front_knee_angle": int(front_knee_angle),
            "torso_angle": int(torso_angle),
            "balance_status": balance_status,
        }
