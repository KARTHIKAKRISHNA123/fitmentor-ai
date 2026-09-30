from core.base_exercise import BaseExercise


class ShoulderPressDetector(BaseExercise):
    UP_THRESHOLD = 160
    DOWN_THRESHOLD = 90
    MIN_VISIBILITY = 0.7

    LEFT_SHOULDER, LEFT_ELBOW, LEFT_WRIST = 11, 13, 15
    RIGHT_SHOULDER, RIGHT_ELBOW, RIGHT_WRIST = 12, 14, 16
    LEFT_HIP, RIGHT_HIP = 23, 24
    LEFT_KNEE, RIGHT_KNEE = 25, 26

    def __init__(self):
        super().__init__()

    def reset(self):
        self.reps = 0
        self.stage = None

    def process(self, landmarks):
        left_vis = landmarks[self.LEFT_ELBOW].visibility
        right_vis = landmarks[self.RIGHT_ELBOW].visibility

        if left_vis >= right_vis:
            shoulder_idx, elbow_idx, wrist_idx = self.LEFT_SHOULDER, self.LEFT_ELBOW, self.LEFT_WRIST
            hip_idx, knee_idx = self.LEFT_HIP, self.LEFT_KNEE
        else:
            shoulder_idx, elbow_idx, wrist_idx = self.RIGHT_SHOULDER, self.RIGHT_ELBOW, self.RIGHT_WRIST
            hip_idx, knee_idx = self.RIGHT_HIP, self.RIGHT_KNEE

        elbow_angle = self.calculate_angle(
            self.get_point(landmarks, shoulder_idx),
            self.get_point(landmarks, elbow_idx),
            self.get_point(landmarks, wrist_idx),
        )

        key_landmarks_visible = (
            landmarks[shoulder_idx].visibility > self.MIN_VISIBILITY and
            landmarks[elbow_idx].visibility > self.MIN_VISIBILITY and
            landmarks[wrist_idx].visibility > self.MIN_VISIBILITY
        )

        if key_landmarks_visible:
            if elbow_angle > self.UP_THRESHOLD:
                self.stage = "up"
            if elbow_angle < self.DOWN_THRESHOLD and self.stage == "up":
                self.stage = "down"
                self.reps += 1

        if elbow_angle >= self.UP_THRESHOLD:
            extension_status = "FULL EXTENSION"
        elif elbow_angle >= 130:
            extension_status = "NEARLY EXTENDED"
        elif elbow_angle >= self.DOWN_THRESHOLD:
            extension_status = "PRESSING"
        else:
            extension_status = "START POSITION"

        back_angle = self.calculate_angle(
            self.get_point(landmarks, shoulder_idx),
            self.get_point(landmarks, hip_idx),
            self.get_point(landmarks, knee_idx),
        )

        if back_angle >= 160:
            back_arch_status = "Neutral"
        elif back_angle >= 140:
            back_arch_status = "Slight Arch"
        else:
            back_arch_status = "Excessive Arch"

        return {
            "reps": self.reps,
            "elbow_angle": int(elbow_angle),
            "extension_status": extension_status,
            "back_arch_status": back_arch_status,
        }
