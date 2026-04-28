"""One-shot smoke test for Azure Whisper + Azure GPT.

Run from the backend dir:
    uv run python scripts/smoke_azure.py

Uses the smallest audio file in data/ to minimise API cost, and sends a single
short GPT prompt referencing the transcript.
"""

from __future__ import annotations

from pathlib import Path

from app.clients.azure_openai import get_azure_client
from app.core.config import get_settings
from app.services.transcription import transcribe

AUDIO_FILE = Path(
    "../data/2 Inspection Audios/R&I Kyllikki Hall Inspection Demo Audio/"
    "R&I Kyllikki Hall Inspection Finnish.m4a"
)


def main() -> None:
    settings = get_settings()
    print(f"Endpoint   : {settings.azure_openai_endpoint}")
    print(f"Whisper    : {settings.azure_openai_whisper_deployment}")
    print(f"GPT        : {settings.azure_openai_gpt_deployment}")
    print(f"API ver    : {settings.azure_openai_api_version}")
    print()

    if not AUDIO_FILE.exists():
        raise SystemExit(f"Audio file not found: {AUDIO_FILE.resolve()}")
    size_mb = AUDIO_FILE.stat().st_size / 1024 / 1024
    print(f"Audio file : {AUDIO_FILE.name} ({size_mb:.2f} MB)")

    print("\n--- Whisper ---")
    transcript = transcribe(AUDIO_FILE)
    print(f"Language   : {transcript.language}")
    print(f"Duration   : {transcript.duration}s")
    print(f"Segments   : {len(transcript.segments)}")
    print(f"Excerpt    : {transcript.text[:300]}...")

    print("\n--- GPT ---")
    client = get_azure_client()
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
        temperature=0.2,
        max_tokens=120,
    )
    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()
