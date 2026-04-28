from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    start: float = Field(ge=0.0, description="Seconds from audio start")
    end: float = Field(ge=0.0)
    text: str


class Transcript(BaseModel):
    language: str | None = None
    duration: float | None = None
    text: str
    segments: list[TranscriptSegment] = Field(default_factory=list)
