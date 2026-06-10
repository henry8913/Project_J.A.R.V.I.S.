from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class AttachmentType(str, Enum):
    AUDIO = "audio"
    IMAGE = "image"
    PDF = "pdf"
    CSV = "csv"
    DOCUMENT = "document"


@dataclass(slots=True)
class Attachment:
    kind: AttachmentType
    local_path: Path
    mime_type: str | None = None
    original_name: str | None = None


@dataclass(slots=True)
class IncomingMessage:
    chat_id: int
    user_id: int
    text: str = ""
    attachments: list[Attachment] = field(default_factory=list)
    audio_transcript: str | None = None


@dataclass(slots=True)
class PendingArtifact:
    local_path: Path
    caption: str = ""


@dataclass(slots=True)
class PreparedAgentInput:
    prompt: str
    images: list[Any] = field(default_factory=list)
    csv_paths: list[Path] = field(default_factory=list)
    histogram_data: list[tuple[str, float]] = field(default_factory=list)
    infographic_descriptions: list[str] = field(default_factory=list)
