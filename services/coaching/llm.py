import logging
import os
import re

from services.config.workout_config import PROMPT

LOGGER = logging.getLogger(__name__)

# Groq retires models from time to time (llama-3.3-70b-versatile was removed),
# so instead of hard-coding one name the coach picks the first model from this
# list that the account can actually use. Set GROQ_MODEL to force a specific one.
PREFERRED_MODELS = [
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile",
]

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL)


def _is_reasoning_model(model: str) -> bool:
    # gpt-oss models "think" before answering; those thinking tokens count
    # against max_tokens, so they need a larger budget and low effort.
    return model.startswith("openai/gpt-oss")


class LLMCoach:
    """Wraps the Groq chat-completions client to generate short coaching cues."""

    MAX_HISTORY_MESSAGES = 10

    def __init__(self, groq_client, model=None):
        self.client = groq_client
        self.model = model or os.environ.get("GROQ_MODEL") or None
        self.history = []
        self.system_prompt = PROMPT

    def _resolve_model(self, exclude=()):
        """Returns the first preferred model this Groq account can use."""
        candidates = [m for m in PREFERRED_MODELS if m not in exclude]
        try:
            available = {m.id for m in self.client.models.list().data}
            for model in candidates:
                if model in available:
                    return model
        except Exception as e:
            LOGGER.warning("Could not list Groq models (%s); using default order.", e)
        return candidates[0] if candidates else PREFERRED_MODELS[0]

    def _complete(self, model, messages):
        kwargs = {"model": model, "messages": messages, "temperature": 0.4}
        if _is_reasoning_model(model):
            kwargs.update(reasoning_effort="low", max_tokens=300)
        else:
            kwargs.update(max_tokens=60)
        response = self.client.chat.completions.create(**kwargs)
        text = response.choices[0].message.content or ""
        text = _THINK_BLOCK.sub("", text).strip()
        if not text:
            raise ValueError(f"Model {model} returned an empty reply")
        return text

    def give_feedback(self, event, issue):
        prompt = f"Event: {event}"
        if issue:
            prompt += f" Form Issue: {issue}"

        messages = [
            {"role": "system", "content": self.system_prompt},
            *self.history[-self.MAX_HISTORY_MESSAGES:],
            {"role": "user", "content": prompt},
        ]

        if self.model is None:
            self.model = self._resolve_model()

        try:
            text = self._complete(self.model, messages)
        except Exception as e:
            # Model retired / not available on this account -> switch once.
            if "model_not_found" in str(e) or "does not exist" in str(e):
                failed = self.model
                self.model = self._resolve_model(exclude={failed})
                LOGGER.warning("Groq model %s unavailable, switching to %s", failed, self.model)
                text = self._complete(self.model, messages)
            else:
                raise

        # Keep user + assistant turns together so the model sees real
        # conversation context (and doesn't repeat the same cue twice).
        self.history.append({"role": "user", "content": prompt})
        self.history.append({"role": "assistant", "content": text})
        self.history = self.history[-self.MAX_HISTORY_MESSAGES:]

        return text
