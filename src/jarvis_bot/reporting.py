from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image as ReportImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def slugify_filename(value: str, default_stem: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-._")
    return cleaned or default_stem


def normalise_histogram_data(raw_data: str | Iterable[tuple[str, float]] | None) -> list[tuple[str, float]]:
    if raw_data is None:
        return []

    if isinstance(raw_data, str):
        raw_data = raw_data.strip()
        if not raw_data:
            return []
        decoded = json.loads(raw_data)
    else:
        decoded = list(raw_data)

    normalised: list[tuple[str, float]] = []
    for item in decoded:
        if isinstance(item, dict):
            label = str(item.get("label", "item"))
            value = float(item.get("value", 0))
        else:
            label, value = item
            label = str(label)
            value = float(value)
        normalised.append((label, value))
    return normalised


def create_histogram_png(output_path: str | Path, title: str, chart_data: str | Iterable[tuple[str, float]]) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    bars = normalise_histogram_data(chart_data)
    if not bars:
        raise ValueError("Histogram data is empty")

    labels = [label for label, _ in bars]
    values = [value for _, value in bars]

    figure, axis = plt.subplots(figsize=(8, 4.5))
    axis.bar(labels, values, color="#2563eb")
    axis.set_title(title)
    axis.set_ylabel("Valore")
    axis.grid(axis="y", alpha=0.2)
    axis.set_axisbelow(True)
    plt.xticks(rotation=20, ha="right")
    figure.tight_layout()
    figure.savefig(output, dpi=150)
    plt.close(figure)
    return output


def write_csv_file(output_path: str | Path, rows_json: str) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = json.loads(rows_json)
    if not isinstance(rows, list) or not rows:
        raise ValueError("rows_json must describe a non-empty list")

    fieldnames = sorted({key for row in rows if isinstance(row, dict) for key in row.keys()})
    if not fieldnames:
        raise ValueError("rows_json must contain dictionaries with keys")

    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return output


def build_pdf_report(
    output_path: str | Path,
    title: str,
    summary: str,
    histogram_title: str | None = None,
    histogram_data: str | Iterable[tuple[str, float]] | None = None,
    infographic_descriptions: Iterable[str] | None = None,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    story = [Paragraph(title, styles["Title"]), Spacer(1, 6 * mm)]

    for paragraph in summary.split("\n\n"):
        cleaned = paragraph.strip().replace("\n", "<br/>")
        if cleaned:
            story.append(Paragraph(cleaned, styles["BodyText"]))
            story.append(Spacer(1, 4 * mm))

    if histogram_data:
        chart_path = create_histogram_png(output.with_suffix(".png"), histogram_title or "Istogramma", histogram_data)
        story.append(Paragraph(histogram_title or "Istogramma", styles["Heading2"]))
        story.append(Spacer(1, 3 * mm))
        story.append(ReportImage(str(chart_path), width=165 * mm, height=92 * mm))
        story.append(Spacer(1, 4 * mm))

    descriptions = [item.strip() for item in infographic_descriptions or [] if item.strip()]
    if descriptions:
        story.append(Paragraph("Descrizione delle infografiche", styles["Heading2"]))
        story.append(Spacer(1, 3 * mm))
        for description in descriptions:
            story.append(Paragraph(f"- {description}", styles["BodyText"]))
            story.append(Spacer(1, 2 * mm))

    document = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    document.build(story)
    return output
