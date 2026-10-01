import os

from services.config.workout_config import PROMPT

# Overridable via an environment variable / secret, so if Groq ever retires
# this model you can switch without touching code.
DEFAULT_MODEL = "llama-3.3-70b-versatile"


class LLMCoach:
    """Wraps the Groq chat-completions client to generate short coaching cues."""

    MAX_HISTORY_MESSAGES = 10

    def __init__(self, groq_client, model=None):
        self.client = groq_client
        self.model = model or os.environ.get("GROQ_MODEL", DEFAULT_MODEL)
        self.history = []
        self.system_prompt = PROMPT

    def give_feedback(self, event, issue):
        prompt = f"Event: {event}"
        if issue:
            prompt += f" Form Issue: {issue}"

        messages = [
            {"role": "system", "content": self.system_prompt},
            *self.history[-self.MAX_HISTORY_MESSAGES:],
            {"role": "user", "content": prompt},
        ]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.4,
            max_tokens=60,
        )

        text = response.choices[0].message.content.strip()

        # Keep user + assistant turns together so the model sees real
        # conversation context (and doesn't repeat the same cue twice).
        self.history.append({"role": "user", "content": prompt})
        self.history.append({"role": "assistant", "content": text})
        self.history = self.history[-self.MAX_HISTORY_MESSAGES:]

        return text
