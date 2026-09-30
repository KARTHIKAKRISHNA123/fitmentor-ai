from io import BytesIO
from gtts import gTTS


class TextToSpeech:
    """Wraps gTTS to synthesise a short coaching sentence to in-memory MP3 bytes."""

    def speak(self, text, lang="en"):
        cleaned = (text or "").strip()
        if not cleaned:
            return None

        buffer = BytesIO()
        gTTS(text=cleaned, lang=lang).write_to_fp(buffer)
        buffer.seek(0)
        return buffer.read()
