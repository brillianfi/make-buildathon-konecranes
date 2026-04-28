import base64
import json
from pathlib import Path

from tenacity import retry, stop_after_attempt, wait_exponential

from app.clients.azure_openai import get_azure_client
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.prompts import load_prompt
from app.domain.inspection import Finding

log = get_logger(__name__)

_FINDING_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["component", "condition", "severity", "observation", "recommendation"],
    "properties": {
        "component": {"type": "string"},
        "condition": {"type": "string"},
        "severity": {"type": "string", "enum": ["ok", "minor", "major", "critical", "unknown"]},
        "observation": {"type": "string"},
        "recommendation": {"type": "string"},
    },
}


def _encode_image(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".") or "jpeg"
    if suffix == "jpg":
        suffix = "jpeg"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/{suffix};base64,{data}"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), reraise=True)
def analyse_image(
    image_path: Path,
    *,
    operator_commentary: str = "",
    location: str | None = None,
    glossary_excerpt: str = "",
) -> Finding:
    settings = get_settings()
    client = get_azure_client()

    user_text_parts: list[str] = []
    if location:
        user_text_parts.append(f"Location: {location}")
    if operator_commentary:
        user_text_parts.append(f"Operator commentary near this photo:\n{operator_commentary}")
    if glossary_excerpt:
        user_text_parts.append(f"Glossary (terminology reference):\n{glossary_excerpt}")
    if not user_text_parts:
        user_text_parts.append("No operator commentary available; describe what is visible.")

    response = client.chat.completions.create(
        model=settings.azure_openai_gpt_deployment,
        messages=[
            {"role": "system", "content": load_prompt("vision.system")},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "\n\n".join(user_text_parts)},
                    {"type": "image_url", "image_url": {"url": _encode_image(image_path)}},
                ],
            },
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "finding",
                "schema": _FINDING_SCHEMA,
                "strict": True,
            },
        },
    )

    payload = response.choices[0].message.content or "{}"
    data = json.loads(payload)
    finding = Finding(image=image_path.name, **data)
    log.info("vision.done", image=image_path.name, severity=finding.severity)
    return finding
