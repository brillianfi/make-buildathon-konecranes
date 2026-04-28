from concurrent.futures import ThreadPoolExecutor

from app.core.errors import ValidationError
from app.core.logging import get_logger
from app.domain.inspection import Finding, Inspection, InspectionStatus
from app.services.correlation import commentary_for_image
from app.services.glossary import load_glossary_text
from app.services.report_builder import build_report
from app.services.template_loader import resolve_template
from app.services.transcription import transcribe
from app.services.vision import analyse_image
from app.storage.local import LocalStorage

log = get_logger(__name__)

_VISION_CONCURRENCY = 4


def run_inspection(inspection: Inspection, storage: LocalStorage) -> Inspection:
    log.info("pipeline.start", inspection_id=str(inspection.id))
    inspection.status = InspectionStatus.RUNNING

    try:
        if inspection.audio is None:
            raise ValidationError("Inspection has no audio track")
        if not inspection.images:
            raise ValidationError("Inspection has no images")

        glossary = load_glossary_text()

        # 1. Transcribe the single audio file.
        inspection.transcript = transcribe(inspection.audio.path, prompt=glossary[:500])

        # 2. Order images by frontend-supplied capture time.
        inspection.images.sort(key=lambda i: i.captured_at)

        # 3. Audio anchor: prefer explicit start, else first image's timestamp.
        anchor = inspection.audio_started_at or inspection.images[0].captured_at

        # 4. Vision pass per image, parallelised (I/O bound).
        def analyse(image_idx: int) -> Finding:
            image = inspection.images[image_idx]
            commentary = commentary_for_image(image, inspection.transcript, anchor)
            return analyse_image(
                image.path,
                operator_commentary=commentary,
                location=image.location,
                glossary_excerpt=glossary[:2000],
            )

        with ThreadPoolExecutor(max_workers=_VISION_CONCURRENCY) as pool:
            inspection.findings = list(pool.map(analyse, range(len(inspection.images))))

        # 5. Build the xlsx report.
        template_path = resolve_template(inspection.template_filename)
        report_path = build_report(
            findings=inspection.findings,
            images=inspection.images,
            transcript=inspection.transcript,
            template_path=template_path,
            output_path=storage.report_path(inspection.id),
            glossary=glossary,
        )
        inspection.report_path = report_path
        inspection.status = InspectionStatus.COMPLETED
        log.info("pipeline.done", inspection_id=str(inspection.id), report=str(report_path))
    except Exception as exc:
        inspection.status = InspectionStatus.FAILED
        inspection.error = str(exc)
        log.exception("pipeline.failed", inspection_id=str(inspection.id))
        raise

    return inspection
