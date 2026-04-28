from pathlib import Path
from typing import BinaryIO, Protocol
from uuid import UUID


class Storage(Protocol):
    def inspection_dir(self, inspection_id: UUID) -> Path: ...
    def save_upload(
        self,
        inspection_id: UUID,
        kind: str,
        filename: str,
        fileobj: BinaryIO,
    ) -> Path: ...
    def report_path(self, inspection_id: UUID) -> Path: ...
