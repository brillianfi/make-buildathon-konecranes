import shutil
from pathlib import Path
from typing import BinaryIO
from uuid import UUID


class LocalStorage:
    """Filesystem storage. Layout: <root>/inspections/<id>/{images,audio,report.xlsx}"""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def inspection_dir(self, inspection_id: UUID) -> Path:
        path = self.root / "inspections" / str(inspection_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_upload(self, inspection_id: UUID, kind: str, filename: str, fileobj: BinaryIO) -> Path:
        target_dir = self.inspection_dir(inspection_id) / kind
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / Path(filename).name
        with target.open("wb") as out:
            shutil.copyfileobj(fileobj, out)
        return target

    def report_path(self, inspection_id: UUID) -> Path:
        return self.inspection_dir(inspection_id) / "report.xlsx"
