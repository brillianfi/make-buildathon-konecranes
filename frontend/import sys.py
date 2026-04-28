import sys
import os
import shutil

from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QMessageBox,
    QFileDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

from docx import Document
from docx.shared import Inches

# -------------------------------------------------
# Configuration
# -------------------------------------------------
AUDIO_EXTENSIONS = (".wav", ".mp3", ".aac", ".m4a")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp")

IMAGE_STORAGE_DIR = "imported_images"
os.makedirs(IMAGE_STORAGE_DIR, exist_ok=True)


# =================================================
# Drag & Drop Area Widget
# =================================================
class DropArea(QLabel):
    def __init__(self, text):
        super().__init__(text)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #777;
                border-radius: 6px;
                padding: 25px;
                font-size: 14px;
            }
        """)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        paths = [url.toLocalFile() for url in event.mimeData().urls()]
        self.handle_drop(paths)

    def handle_drop(self, paths):
        pass


# =================================================
# Main Application
# =================================================
class ReportApp(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Report Generator")
        self.resize(520, 480)

        # State
        self.audio_file: str | None = None
        self.image_folders: list[str] = []
        self.imported_images: list[str] = []
        self.report_ready: bool = False

        layout = QVBoxLayout()

        # ---------------- Audio Drop ----------------
        self.audio_drop = DropArea(
            "Drop audio file here\n(.wav, .mp3, .aac, .m4a)"
        )
        self.audio_drop.handle_drop = self.handle_audio_drop
        self.audio_label = QLabel("Audio: Not selected")

        # ---------------- Image Drop ----------------
        self.image_drop = DropArea(
            "Drop image folders here\n(Multiple folders allowed)"
        )
        self.image_drop.handle_drop = self.handle_image_folder_drop
        self.image_label = QLabel("Imported images: 0")

        # ---------------- Buttons -------------------
        self.generate_button = QPushButton("Generate Report")
        self.generate_button.clicked.connect(self.generate_report)

        self.save_button = QPushButton("Save Report…")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_report)

        # ---------------- Layout --------------------
        layout.addWidget(self.audio_drop)
        layout.addWidget(self.audio_label)
        layout.addSpacing(12)

        layout.addWidget(self.image_drop)
        layout.addWidget(self.image_label)
        layout.addSpacing(16)

        layout.addWidget(self.generate_button)
        layout.addWidget(self.save_button)

        self.setLayout(layout)

    # -------------------------------------------------
    # Audio Drop Logic
    # -------------------------------------------------
    def handle_audio_drop(self, paths: list[str]):
        if len(paths) != 1:
            QMessageBox.warning(self, "Invalid Drop", "Drop exactly ONE audio file.")
            return

        path = paths[0]
        if not os.path.isfile(path):
            QMessageBox.warning(self, "Invalid Item", "Dropped item is not a file.")
            return

        if not path.lower().endswith(AUDIO_EXTENSIONS):
            QMessageBox.warning(
                self,
                "Invalid Audio Format",
                "Allowed formats: .wav, .mp3, .aac, .m4a"
            )
            return

        self.audio_file = path
        self.audio_label.setText(f"Audio: {os.path.basename(path)}")

    # -------------------------------------------------
    # Image Folder Drop Logic
    # -------------------------------------------------
    def handle_image_folder_drop(self, paths: list[str]):
        total_new = 0

        for path in paths:
            if not os.path.isdir(path):
                continue

            if path in self.image_folders:
                continue

            self.image_folders.append(path)
            total_new += self.import_images_from_folder(path)

        self.image_label.setText(f"Imported images: {len(self.imported_images)}")

        if total_new == 0:
            QMessageBox.information(
                self,
                "No Images Imported",
                "No new images were found in dropped folders."
            )

    def import_images_from_folder(self, folder: str) -> int:
        count = 0

        for filename in os.listdir(folder):
            if not filename.lower().endswith(IMAGE_EXTENSIONS):
                continue

            src = os.path.join(folder, filename)
            dst = os.path.join(IMAGE_STORAGE_DIR, filename)

            base, ext = os.path.splitext(filename)
            index = 1
            while os.path.exists(dst):
                dst = os.path.join(
                    IMAGE_STORAGE_DIR,
                    f"{base}_{index}{ext}"
                )
                index += 1

            shutil.copy2(src, dst)
            self.imported_images.append(dst)
            count += 1

        return count

    # -------------------------------------------------
    # Generate Report (background logic placeholder)
    # -------------------------------------------------
    def generate_report(self):
        if not self.audio_file:
            QMessageBox.warning(self, "Missing Audio", "Please drop an audio file.")
            return

        if not self.imported_images:
            QMessageBox.warning(self, "No Images", "Please drop image folders.")
            return

        # Placeholder for heavy processing
        self.report_ready = True
        self.save_button.setEnabled(True)

        QMessageBox.information(
            self,
            "Report Ready",
            "Report generated successfully.\nClick 'Save Report…'"
        )

    # -------------------------------------------------
    # Save DOCX Report
    # -------------------------------------------------
    def save_report(self):
        if not self.report_ready:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Report",
            "",
            "Word Document (*.docx)"
        )

        if not path:
            return

        if not path.lower().endswith(".docx"):
            path += ".docx"

        try:
            self.build_docx_report(path)
            QMessageBox.information(
                self,
                "Saved",
                f"Report saved successfully:\n{path}"
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save report:\n{exc}"
            )

    # -------------------------------------------------
    # DOCX Report Generator
    # -------------------------------------------------
    def build_docx_report(self, output_path: str):
        # Report builder TO DO
        doc = Document()
        doc.save(output_path)
        return

# =================================================
# Application Entry Point
# =================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ReportApp()
    window.show()
    sys.exit(app.exec())