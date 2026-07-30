"""Build Excel workbooks from tabular data."""

from __future__ import annotations

import io
from typing import Any

from openpyxl import Workbook


def rows_to_xlsx(headers: list[str], rows: list[list[Any]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for row in rows:
        sheet.append(row)

    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()
