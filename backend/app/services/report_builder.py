import json
from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_exponential

from app.clients.azure_openai import get_gpt_client
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.prompts import load_prompt
from app.domain.inspection import Finding, ImageAsset
from app.domain.report import ReportSheet, ReportWorkbook
from app.domain.transcript import Transcript
from app.services.template_loader import flatten_template_to_text
from app.services.xlsx_writer import write_workbook

log = get_logger(__name__)

_WORKBOOK_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["sheets"],
    "properties": {
        "sheets": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["title", "rows"],
                "properties": {
                    "title": {"type": "string"},
                    "rows": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {"type": ["string", "number", "boolean", "null"]},
                        },
                    },
                },
            },
        },
    },
}


def _findings_block(findings: list[Finding], images: list[ImageAsset]) -> str:
    by_filename = {img.filename: img for img in images}
    enriched = []
    for f in findings:
        meta = by_filename.get(f.image)
        enriched.append(
            {
                **f.model_dump(),
                "captured_at": meta.captured_at.isoformat() if meta else None,
                "location": meta.location if meta else None,
            }
        )
    return json.dumps(enriched, indent=2, ensure_ascii=False)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), reraise=True)
def synthesize_workbook(
    *,
    findings: list[Finding],
    images: list[ImageAsset],
    transcript: Transcript | None,
    template_path: Path,
    glossary: str = "",
) -> ReportWorkbook:
    settings = get_settings()
    client = get_gpt_client()
    template_text = flatten_template_to_text(template_path)

    transcript_text = transcript.text if transcript and transcript.text else "(none)"

    user_payload = (
        "FINDINGS (per image, with frontend-supplied metadata):\n"
        f"{_findings_block(findings, images)}\n\n"
        "OPERATOR TRANSCRIPT:\n"
        f"{transcript_text}\n\n"
        "GLOSSARY:\n"
        f"{glossary or '(none)'}\n\n"
        "TEMPLATE WORKBOOK (flattened):\n"
        f"{template_text}"
    )

    log.info(
        "report.synthesize.start",
        findings=len(findings),
        template=template_path.name,
    )

    response = client.chat.completions.create(
        model=settings.azure_openai_gpt_deployment,
        messages=[
            {"role": "system", "content": load_prompt("report.system")},
            {"role": "user", "content": user_payload},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "workbook",
                "schema": _WORKBOOK_SCHEMA,
                "strict": True,
            },
        },
    )

    raw = response.choices[0].message.content or "{}"
    data = json.loads(raw)
    sheets = [ReportSheet(**s) for s in data.get("sheets", [])]
    workbook = ReportWorkbook(sheets=sheets)
    log.info("report.synthesize.done", sheets=len(workbook.sheets))
    return workbook


def build_report(
    *,
    findings: list[Finding],
    images: list[ImageAsset],
    transcript: Transcript | None,
    template_path: Path,
    output_path: Path,
    glossary: str = "",
) -> Path:
    workbook = synthesize_workbook(
        findings=findings,
        images=images,
        transcript=transcript,
        template_path=template_path,
        glossary=glossary,
    )
    return write_workbook(workbook, output_path)
