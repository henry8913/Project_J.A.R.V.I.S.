from pathlib import Path

from jarvis_bot.reporting import build_pdf_report, create_histogram_png


def test_create_histogram_png(tmp_path: Path) -> None:
    output = tmp_path / "chart.png"
    created = create_histogram_png(output, "Test Chart", [("A", 1), ("B", 2)])
    assert created.exists()
    assert created.stat().st_size > 0


def test_build_pdf_report(tmp_path: Path) -> None:
    output = tmp_path / "report.pdf"
    created = build_pdf_report(
        output_path=output,
        title="Jarvis Report",
        summary="Sintesi del report.\n\nSecondo paragrafo.",
        histogram_title="Distribuzione",
        histogram_data=[("A", 2), ("B", 4)],
        infographic_descriptions=["Spiega i valori della tabella in modo semplice."],
    )
    assert created.exists()
    assert created.stat().st_size > 0
