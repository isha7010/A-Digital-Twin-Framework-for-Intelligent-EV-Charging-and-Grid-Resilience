"""CSV report writers shared by the CLI and dashboard."""

import csv
import os
from collections.abc import Iterable, Mapping


def write_csv_report(path: str, rows: Iterable[Mapping]) -> str:
    """Write a non-empty sequence of mapping rows and return its path."""
    rows = list(rows)
    if not rows:
        raise ValueError("Cannot write a CSV report without rows")
    fieldnames = list(rows[0].keys())
    if not fieldnames:
        raise ValueError("Cannot write a CSV report without columns")
    if any(set(row.keys()) != set(fieldnames) for row in rows):
        raise ValueError("All CSV report rows must have the same columns")

    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path
