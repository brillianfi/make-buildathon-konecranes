"""End-to-end smoke test: Whisper transcription + GPT summary.

    PYTHONPATH=. uv run python scripts/smoke_azure.py
"""

from __future__ import annotations

from pathlib import Path

from app.clients.azure_openai import get_gpt_client
from app.core.config import get_settings
from app.services.transcription import transcribe

AUDIO_FILE = Path(
    "../data/2 Inspection Audios/R&I Kyllikki Hall Inspection Demo Audio/"
    "R&I Kyllikki Hall Inspection Finnish.m4a"
)


def main() -> None:
    settings = get_settings()
    print(f"Whisper endpoint  : {settings.azure_openai_whisper_endpoint}")
    print(f"Whisper deployment: {settings.azure_openai_whisper_deployment}")
    print(f"GPT endpoint      : {settings.azure_openai_gpt_endpoint}")
    print(f"GPT deployment    : {settings.azure_openai_gpt_deployment}")

    if not AUDIO_FILE.exists():
        raise SystemExit(f"Audio file not found: {AUDIO_FILE.resolve()}")
    size_mb = AUDIO_FILE.stat().st_size / 1024 / 1024
    print(f"\nAudio file        : {AUDIO_FILE.name} ({size_mb:.2f} MB)")

    print("\n--- Whisper ---")
    transcript = transcribe(AUDIO_FILE)
    print(f"Language : {transcript.language}")
    print(f"Duration : {transcript.duration}s")
    print(f"Segments : {len(transcript.segments)}")
    print(f"Excerpt  : {transcript.text[:300]}...")

    print("\n--- GPT (single-sentence summary) ---")
    client = get_gpt_client()
    response = client.chat.completions.create(
        model=settings.azure_openai_gpt_deployment,
        messages=[
            {"role": "system", "content": "You answer in one short sentence."},
            {
                "role": "user",
                "content": (
                    "Summarise this transcript of a crane inspection in one sentence:\n\n"
                    f"{transcript.text}"
                ),
            },
        ],
        max_completion_tokens=200,
    )
    print(response.choices[0].message.content)
    print(f"\nUsage: {response.usage}")


if __name__ == "__main__":
    main()
