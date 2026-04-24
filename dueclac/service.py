from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .excel_exporter import ExcelReportExporter
from .models import ReportData
from .parser import DueClacPDFParser


def process_pdf_to_excel(
    pdf_path: str | Path,
    output_path: str | Path,
    group_names: Iterable[str] | None = None,
) -> ReportData:
    parser = DueClacPDFParser(known_groups=group_names)
    report = parser.parse(pdf_path)
    exporter = ExcelReportExporter()
    exporter.export(report, output_path)
    return report

