from fastapi import APIRouter

from app.domain.report import ReportTemplateRef
from app.services.template_loader import list_templates

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[ReportTemplateRef])
def get_templates() -> list[ReportTemplateRef]:
    return list_templates()
