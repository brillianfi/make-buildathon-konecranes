"""GPT-only smoke test (skips Whisper).

    PYTHONPATH=. uv run python scripts/smoke_gpt.py
"""

from app.clients.azure_openai import get_gpt_client
from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    print(f"Endpoint   : {settings.azure_openai_gpt_endpoint}")
    print(f"GPT        : {settings.azure_openai_gpt_deployment}")
    print(f"API ver    : {settings.azure_openai_gpt_api_version}")

    client = get_gpt_client()
    response = client.chat.completions.create(
        model=settings.azure_openai_gpt_deployment,
        messages=[
            {"role": "system", "content": "You answer in one short sentence."},
            {
                "role": "user",
                "content": (
                    "Name three components you would inspect on an industrial overhead crane."
                ),
            },
        ],
        max_completion_tokens=200,
    )
    print("\n--- GPT response ---")
    print(response.choices[0].message.content)
    print(f"\nUsage: {response.usage}")


if __name__ == "__main__":
    main()
