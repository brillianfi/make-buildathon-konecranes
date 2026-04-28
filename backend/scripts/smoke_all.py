"""Comprehensive Azure smoke test — exercises every model path the pipeline uses.

    PYTHONPATH=. uv run python scripts/smoke_all.py

Tests:
  1. Settings load + endpoint reachability for both deployments.
  2. Whisper: transcribe() service on a small demo audio file.
  3. GPT plain text: round-trip a single chat completion.
  4. GPT vision + structured output: analyse_image() on a demo JPG (covers
     the multimodal path AND the JSON-schema response_format used by the
     real pipeline).

The synthesize_workbook() call in report_builder.py uses the same GPT client
and the same structured-output mechanism, so a passing analyse_image() implies
the synthesis call will also work.
"""

from __future__ import annotations

import sys
from pathlib import Path

from app.clients.azure_openai import get_gpt_client
from app.core.config import get_settings
from app.services.transcription import transcribe
from app.services.vision import analyse_image

AUDIO_FILE = Path(
    "../data/2 Inspection Audios/R&I Kyllikki Hall Inspection Demo Audio/"
    "R&I Kyllikki Hall Inspection Finnish.m4a"
)
IMAGE_DIR = Path("../data/1 Inspection Pictures/R&I Kyllikki Hall Inspection Demo Pictures")


def _hr(label: str) -> None:
    print(f"\n{'=' * 8} {label} {'=' * 8}")


def check_settings() -> None:
    _hr("1. Settings")
    s = get_settings()
    print(f"  Whisper  : {s.azure_openai_whisper_endpoint}  [{s.azure_openai_whisper_deployment}]")
    print(f"  GPT      : {s.azure_openai_gpt_endpoint}  [{s.azure_openai_gpt_deployment}]")
    print(f"  Templates: {s.templates_dir}")
    print(f"  Storage  : {s.storage_dir}")
    print("  OK")


def check_whisper() -> None:
    _hr("2. Whisper transcription")
    if not AUDIO_FILE.exists():
        raise SystemExit(f"  MISSING: {AUDIO_FILE.resolve()}")
    size_mb = AUDIO_FILE.stat().st_size / 1024 / 1024
    print(f"  File   : {AUDIO_FILE.name} ({size_mb:.2f} MB)")
    transcript = transcribe(AUDIO_FILE)
    print(f"  Lang   : {transcript.language}")
    print(f"  Dur    : {transcript.duration:.1f}s")
    print(f"  Segs   : {len(transcript.segments)}")
    print(f"  Excerpt: {transcript.text[:160]}...")
    if not transcript.text.strip():
        raise SystemExit("  FAIL: empty transcript")
    print("  OK")


def check_gpt_text() -> None:
    _hr("3. GPT plain text")
    s = get_settings()
    client = get_gpt_client()
    response = client.chat.completions.create(
        model=s.azure_openai_gpt_deployment,
        messages=[
            {"role": "system", "content": "Answer in one short sentence."},
            {"role": "user", "content": "What is a hoist on an industrial crane?"},
        ],
        max_completion_tokens=120,
    )
    text = response.choices[0].message.content or ""
    print(f"  Reply: {text}")
    usage = response.usage
    print(f"  Usage: prompt={usage.prompt_tokens} completion={usage.completion_tokens}")
    if not text.strip():
        raise SystemExit("  FAIL: empty completion")
    print("  OK")


def check_gpt_vision() -> None:
    _hr("4. GPT vision + JSON schema (analyse_image)")
    if not IMAGE_DIR.exists():
        raise SystemExit(f"  MISSING dir: {IMAGE_DIR.resolve()}")
    images = sorted(IMAGE_DIR.glob("*.JPG")) + sorted(IMAGE_DIR.glob("*.jpg"))
    if not images:
        raise SystemExit(f"  No JPGs found in {IMAGE_DIR}")
    img = images[0]
    print(f"  Image: {img.name} ({img.stat().st_size / 1024:.0f} KB)")
    finding = analyse_image(
        img,
        operator_commentary="Test commentary: inspection of pillar 10 area.",
        location="Hall A, Pillar 10",
        glossary_excerpt="",
    )
    print(f"  Component   : {finding.component}")
    print(f"  Condition   : {finding.condition}")
    print(f"  Severity    : {finding.severity}")
    print(f"  Observation : {finding.observation[:160]}")
    print(f"  Recommend.  : {(finding.recommendation or '')[:160]}")
    print("  OK")


def main() -> int:
    try:
        check_settings()
        check_whisper()
        check_gpt_text()
        check_gpt_vision()
    except SystemExit as exc:
        print(f"\nFAILED: {exc}")
        return 1
    except Exception as exc:
        print(f"\nFAILED with exception: {type(exc).__name__}: {exc}")
        raise
    print("\n" + "=" * 30)
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
