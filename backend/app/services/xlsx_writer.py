from pathlib import Path

from openpyxl import Workbook

from app.domain.report import ReportWorkbook


def write_workbook(report: ReportWorkbook, target: Path) -> Path:
    wb = Workbook()
    # Remove the default sheet; we'll add our own.
    default_sheet = wb.active
    if default_sheet is not None:
        wb.remove(default_sheet)

    if not report.sheets:
        wb.create_sheet("Report")

    for sheet in report.sheets:
        ws = wb.create_sheet(title=sheet.title[:31] or "Sheet")  # Excel sheet name limit
        for row in sheet.rows:
            ws.append(row)

    target.parent.mkdir(parents=True, exist_ok=True)
    wb.save(target)
    return target
