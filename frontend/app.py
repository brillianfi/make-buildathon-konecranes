"""Drone Inspection Reporting — desktop frontend.

Drop one audio file + image folders, pick a backend template, generate the
Excel report. The pipeline runs in the FastAPI backend; this app just
orchestrates uploads and downloads the resulting .xlsx.
"""

from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

import backend

AUDIO_EXTENSIONS = (".m4a", ".mp3", ".wav", ".ogg", ".flac", ".webm")
BACKEND_URL = os.environ.get("BACKEND_URL", backend.DEFAULT_BASE_URL)

PIPELINE_STEPS = (
    "Upload audio + images",
    "Run pipeline (transcribe + analyse + build xlsx)",
    "Download report",
)
_STEP_PENDING = "○"
_STEP_RUNNING = "▶"
_STEP_DONE = "✓"
_STEP_FAILED = "✗"

PathsCallback = Callable[[list[str]], None]


class DropArea(QLabel):
    def __init__(self, text: str, on_paths: PathsCallback):
        super().__init__(text)
        self._on_paths = on_paths
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            "QLabel { border: 2px dashed #777; border-radius: 6px;"
            " padding: 25px; font-size: 14px; }"
        )

    def dragEnterEvent(self, e: QDragEnterEvent | None) -> None:
        if e is None:
            return
        mime = e.mimeData()
        if mime is not None and mime.hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent | None) -> None:
        if e is None:
            return
        mime = e.mimeData()
        if mime is None:
            return
        self._on_paths([url.toLocalFile() for url in mime.urls()])


class ReportWorker(QThread):
    step = pyqtSignal(int)  # index into PIPELINE_STEPS
    finished_ok = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(
        self,
        audio_path: str,
        image_paths: list[str],
        metadata: list[dict[str, Any]],
        template: str,
        base_url: str,
    ):
        super().__init__()
        self.audio_path = audio_path
        self.image_paths = image_paths
        self.metadata = metadata
        self.template = template
        self.base_url = base_url

    def run(self) -> None:
        try:
            self.step.emit(0)
            inspection = backend.create_inspection(
                self.audio_path,
                self.image_paths,
                self.metadata,
                self.template,
                self.base_url,
            )
            self.step.emit(1)
            result = backend.run_inspection(inspection["id"], self.base_url)
            if result.get("status") != "completed":
                raise RuntimeError(
                    f"Pipeline status={result.get('status')}: {result.get('error')}"
                )
            self.step.emit(2)
            tmp = Path(tempfile.gettempdir()) / f"inspection-{inspection['id']}.xlsx"
            backend.download_report(inspection["id"], tmp, self.base_url)
            self.finished_ok.emit(str(tmp))
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class ReportApp(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Drone Inspection Report Generator")
        self.resize(560, 540)

        self.audio_file: str | None = None
        self.image_folders: list[str] = []
        self.image_records: list[dict[str, Any]] = []
        self.report_tempfile: str | None = None
        self.worker: ReportWorker | None = None

        self.audio_drop = DropArea(
            f"Drop one audio file\n({', '.join(AUDIO_EXTENSIONS)})",
            self.on_audio_drop,
        )
        self.audio_label = QLabel("Audio: not selected")
        self.audio_browse_button = QPushButton("Browse audio file…")
        self.audio_browse_button.clicked.connect(self.browse_audio)
        audio_row = QHBoxLayout()
        audio_row.addWidget(self.audio_label, stretch=1)
        audio_row.addWidget(self.audio_browse_button)

        self.image_drop = DropArea(
            "Drop image folders\n(timestamps from EXIF / DJI filenames)",
            self.on_image_drop,
        )
        self.image_label = QLabel("Imported images: 0")
        self.image_browse_button = QPushButton("Browse folder…")
        self.image_browse_button.clicked.connect(self.browse_image_folder)
        image_row = QHBoxLayout()
        image_row.addWidget(self.image_label, stretch=1)
        image_row.addWidget(self.image_browse_button)

        self.template_combo = QComboBox()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.load_templates)
        template_row = QHBoxLayout()
        template_row.addWidget(QLabel("Template:"))
        template_row.addWidget(self.template_combo, stretch=1)
        template_row.addWidget(self.refresh_button)

        self.generate_button = QPushButton("Generate Report")
        self.generate_button.clicked.connect(self.generate_report)
        self.save_button = QPushButton("Save Report…")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_report)

        # Progress: indeterminate bar + per-step labels.
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # marquee/indeterminate
        self.progress_bar.setVisible(False)
        self.step_labels: list[QLabel] = []
        for text in PIPELINE_STEPS:
            lbl = QLabel(f"{_STEP_PENDING}  {text}")
            lbl.setStyleSheet("color: #888;")
            self.step_labels.append(lbl)

        self.status_label = QLabel(f"Backend: {BACKEND_URL}")
        self.status_label.setStyleSheet("color: #555;")

        layout = QVBoxLayout()
        layout.addWidget(self.audio_drop)
        layout.addLayout(audio_row)
        layout.addWidget(self.image_drop)
        layout.addLayout(image_row)
        layout.addLayout(template_row)
        layout.addWidget(self.generate_button)
        layout.addWidget(self.save_button)
        layout.addWidget(self.progress_bar)
        for lbl in self.step_labels:
            layout.addWidget(lbl)
        layout.addWidget(self.status_label)
        self.setLayout(layout)

        self.load_templates()

    def load_templates(self) -> None:
        self.template_combo.clear()
        # Always-present "no template" option — template selection is optional.
        self.template_combo.addItem("(none — let backend decide)", userData="")
        try:
            templates = backend.list_templates(BACKEND_URL)
        except Exception as exc:
            self.status_label.setText(f"Could not load templates: {exc}")
            return
        for tpl in templates:
            self.template_combo.addItem(tpl["filename"], userData=tpl["filename"])
        self.status_label.setText(
            f"Backend: {BACKEND_URL} — {len(templates)} template(s)"
        )

    def browse_audio(self) -> None:
        filter_ = f"Audio files (*{' *'.join(AUDIO_EXTENSIONS)})"
        path, _ = QFileDialog.getOpenFileName(self, "Select audio file", "", filter_)
        if path:
            self.on_audio_drop([path])

    def browse_image_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select image folder")
        if path:
            self.on_image_drop([path])

    def on_audio_drop(self, paths: list[str]) -> None:
        if len(paths) != 1 or not os.path.isfile(paths[0]):
            QMessageBox.warning(self, "Invalid", "Drop exactly one audio file.")
            return
        if not paths[0].lower().endswith(AUDIO_EXTENSIONS):
            QMessageBox.warning(
                self, "Invalid Format", f"Allowed: {', '.join(AUDIO_EXTENSIONS)}"
            )
            return
        self.audio_file = paths[0]
        self.audio_label.setText(f"Audio: {os.path.basename(paths[0])}")

    def on_image_drop(self, paths: list[str]) -> None:
        new = [p for p in paths if os.path.isdir(p) and p not in self.image_folders]
        if not new:
            QMessageBox.information(self, "No Folders", "Drop directories, not files.")
            return
        self.image_folders.extend(new)
        self.image_records, skipped = backend.collect_from_folders(self.image_folders)
        msg = f"Imported images: {len(self.image_records)}"
        if skipped:
            msg += f"  ({skipped} skipped — no timestamp)"
        self.image_label.setText(msg)

    def generate_report(self) -> None:
        if not self.audio_file:
            QMessageBox.warning(self, "Missing Audio", "Drop an audio file.")
            return
        if not self.image_records:
            QMessageBox.warning(self, "No Images", "Drop image folders with timestamps.")
            return

        meta = [
            {"filename": r["filename"], "captured_at": r["captured_at"]}
            for r in self.image_records
        ]
        paths = [r["filepath"] for r in self.image_records]

        self.generate_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.status_label.setText("Starting…")
        template_filename = self.template_combo.currentData() or ""
        self.reset_steps()
        self.progress_bar.setVisible(True)
        self.worker = ReportWorker(
            self.audio_file,
            paths,
            meta,
            template_filename,
            BACKEND_URL,
        )
        self.worker.step.connect(self.on_step)
        self.worker.finished_ok.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)
        self.worker.start()

    # ---------------- step indicators ----------------
    def reset_steps(self) -> None:
        for i, text in enumerate(PIPELINE_STEPS):
            self.step_labels[i].setText(f"{_STEP_PENDING}  {text}")
            self.step_labels[i].setStyleSheet("color: #888;")

    def on_step(self, idx: int) -> None:
        for i, text in enumerate(PIPELINE_STEPS):
            if i < idx:
                self.step_labels[i].setText(f"{_STEP_DONE}  {text}")
                self.step_labels[i].setStyleSheet("color: #2a7a2a;")
            elif i == idx:
                self.step_labels[i].setText(f"{_STEP_RUNNING}  {text}")
                self.step_labels[i].setStyleSheet("color: #0078d4; font-weight: bold;")
            else:
                self.step_labels[i].setText(f"{_STEP_PENDING}  {text}")
                self.step_labels[i].setStyleSheet("color: #888;")
        total = len(PIPELINE_STEPS)
        self.status_label.setText(f"Step {idx + 1}/{total}: {PIPELINE_STEPS[idx]}…")

    def on_finished(self, tmp: str) -> None:
        self.report_tempfile = tmp
        self.progress_bar.setVisible(False)
        for i, text in enumerate(PIPELINE_STEPS):
            self.step_labels[i].setText(f"{_STEP_DONE}  {text}")
            self.step_labels[i].setStyleSheet("color: #2a7a2a;")
        self.generate_button.setEnabled(True)
        self.save_button.setEnabled(True)
        self.status_label.setText("Report ready.")
        QMessageBox.information(self, "Report Ready", "Inspection report generated.")

    def on_failed(self, message: str) -> None:
        self.progress_bar.setVisible(False)
        # Whichever step was still running at failure time is marked failed.
        for i, lbl in enumerate(self.step_labels):
            if lbl.text().startswith(_STEP_RUNNING):
                lbl.setText(f"{_STEP_FAILED}  {PIPELINE_STEPS[i]}")
                lbl.setStyleSheet("color: #c0392b; font-weight: bold;")
                break
        self.generate_button.setEnabled(True)
        self.status_label.setText("Failed.")
        QMessageBox.critical(self, "Pipeline Error", message)

    def save_report(self) -> None:
        if not self.report_tempfile or not os.path.exists(self.report_tempfile):
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Report", "inspection-report.xlsx", "Excel Workbook (*.xlsx)"
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        Path(path).write_bytes(Path(self.report_tempfile).read_bytes())
        QMessageBox.information(self, "Saved", f"Report saved:\n{path}")


def main() -> int:
    app = QApplication(sys.argv)
    win = ReportApp()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
