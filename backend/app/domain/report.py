from typing import Any

from pydantic import BaseModel, Field


class ReportSheet(BaseModel):
    """A sheet in the generated workbook.

    `rows` is a list of rows; each row is a list of cell values that openpyxl
    can render as-is (str/int/float/bool/None).
    """

    title: str
    rows: list[list[Any]] = Field(default_factory=list)


class ReportWorkbook(BaseModel):
    sheets: list[ReportSheet]


class ReportTemplateRef(BaseModel):
    filename: str
    path: str
    size_bytes: int
