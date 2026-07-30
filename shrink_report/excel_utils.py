"""Excel post-processing for shrink contributor reports."""

from __future__ import annotations

import io

from openpyxl import load_workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter


def format_shrink_report(
    data: bytes,
    *,
    contributor_column: str,
    category_column: str,
    excluded_categories: tuple[str, ...],
    top_n: int = 10,
) -> bytes:
    """
    Exclude herbs, sort by shrink contribution descending (biggest contributors first),
    and keep only the top N rows.
    """
    workbook = load_workbook(io.BytesIO(data))
    sheet = _find_sheet_with_column(workbook, contributor_column)
    if sheet is None:
        raise RuntimeError(f'Column "{contributor_column}" not found in Excel export')

    header_row = 1
    contributor_col = _find_column_index(sheet, header_row, contributor_column)
    if contributor_col is None:
        raise RuntimeError(
            f'Column "{contributor_column}" not found in sheet "{sheet.title}"'
        )

    category_col = _find_column_index(sheet, header_row, category_column)

    max_col = sheet.max_column
    max_row = sheet.max_row
    if max_row <= header_row:
        output = io.BytesIO()
        workbook.save(output)
        return output.getvalue()

    excluded = {value.strip().lower() for value in excluded_categories}
    rows: list[tuple[tuple, list]] = []

    for row_idx in range(header_row + 1, max_row + 1):
        row_values = [
            sheet.cell(row=row_idx, column=col).value for col in range(1, max_col + 1)
        ]
        if category_col is not None:
            category_value = row_values[category_col - 1]
            if category_value is not None and str(category_value).strip().lower() in excluded:
                continue

        sort_key = _sort_key(row_values[contributor_col - 1])
        rows.append((sort_key, row_values))

    rows.sort(key=lambda item: item[0], reverse=True)

    if top_n > 0:
        rows = rows[:top_n]

    bold_font = Font(bold=True)
    for col in range(1, max_col + 1):
        sheet.cell(row=header_row, column=col).font = bold_font
    sheet.cell(row=header_row, column=contributor_col).font = bold_font

    for offset, (_, row_values) in enumerate(rows, start=header_row + 1):
        for col in range(1, max_col + 1):
            sheet.cell(row=offset, column=col).value = row_values[col - 1]

    for row_idx in range(header_row + 1 + len(rows), max_row + 1):
        for col in range(1, max_col + 1):
            sheet.cell(row=row_idx, column=col).value = None

    _ = get_column_letter(contributor_col)

    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def _find_sheet_with_column(workbook, column_name: str):
    target = column_name.strip().lower()
    for sheet in workbook.worksheets:
        for col in range(1, sheet.max_column + 1):
            value = sheet.cell(row=1, column=col).value
            if value and str(value).strip().lower() == target:
                return sheet
    return None


def _find_column_index(sheet, header_row: int, column_name: str) -> int | None:
    target = column_name.strip().lower()
    for col in range(1, sheet.max_column + 1):
        value = sheet.cell(row=header_row, column=col).value
        if value and str(value).strip().lower() == target:
            return col
    return None


def _sort_key(value) -> tuple:
    if value is None:
        return (1, float("-inf"))
    if isinstance(value, (int, float)):
        return (0, float(value))
    text = str(value).strip().replace("%", "").replace(",", "")
    try:
        return (0, float(text))
    except ValueError:
        return (0, float("-inf"))
