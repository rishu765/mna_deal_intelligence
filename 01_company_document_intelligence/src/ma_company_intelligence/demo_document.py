"""Create the copyright-safe synthetic PDF used by the Project 1 demo."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

import pymupdf

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "raw" / "apex-industrial-analytics-demo.pdf"

DEMO_PAGES = (
    (
        "Apex Industrial Analytics - Company Overview\n\n"
        "Apex Industrial Analytics is a fictional industrial-technology company. It provides "
        "predictive maintenance software and industrial sensor monitoring services. Its key "
        "offerings are the ForgeAI analytics platform and Sentinel vibration sensors. The "
        "company reports two business segments: Software and Connected Devices."
    ),
    (
        "Geography, Customers and End Markets\n\n"
        "North America represented 62% of FY2025 revenue, Europe represented 25%, and other "
        "markets represented 13%. Apex serves automotive, aerospace, and general industrial "
        "customers. No individual customer represented more than 10% of FY2025 revenue."
    ),
    (
        "FY2025 Financial Highlights\n\n"
        "For the fiscal year ended December 31, 2025, reported revenue was USD 125 million, "
        "an increase of 14% from FY2024. Adjusted EBITDA was USD 18 million and adjusted "
        "EBITDA margin was 14.4%. Net income was USD 9 million. Growth was primarily driven "
        "by subscription renewals and increased Sentinel sensor deployments."
    ),
    (
        "Risk Factors\n\n"
        "Material risks include cybersecurity incidents that could disrupt hosted services, "
        "supplier concentration for specialized sensor components, and customer delays in "
        "large industrial capital programs. The company also faces foreign-exchange exposure "
        "from its European operations."
    ),
    (
        "Strategic Developments and Management Priorities\n\n"
        "During FY2025, Apex acquired VectorSense, a small condition-monitoring software "
        "provider. Management stated that its priorities are international channel expansion, "
        "continued growth in recurring software revenue, and integration of VectorSense into "
        "the ForgeAI platform. Management did not disclose a market-share estimate."
    ),
)


def create_demo_pdf(output_path: Path, *, overwrite: bool = False) -> Path:
    """Write a deterministic fictional-company PDF and return its resolved path."""

    output = output_path.expanduser().resolve()
    if output.suffix.lower() != ".pdf":
        raise ValueError("demo document output must use a .pdf extension")
    if output.exists() and not overwrite:
        raise FileExistsError(f"output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    document = pymupdf.open()  # type: ignore[no-untyped-call]
    try:
        document.set_metadata(
            {
                "title": "Apex Industrial Analytics FY2025 Synthetic Annual Report",
                "author": "M&A Company Research & Document Intelligence",
                "subject": "Copyright-safe fictional demonstration document",
                "creator": "ma-company-intelligence",
                "producer": "PyMuPDF",
            }
        )
        for page_number, text in enumerate(DEMO_PAGES, start=1):
            page = document.new_page(width=612, height=792)
            page.insert_textbox(
                (72, 72, 540, 700),
                text,
                fontsize=11,
                fontname="helv",
                lineheight=1.35,
            )
            page.insert_text((300, 744), str(page_number), fontsize=9, fontname="helv")
        document.save(output, garbage=4, deflate=True, no_new_id=True)  # type: ignore[no-untyped-call]
    finally:
        document.close()  # type: ignore[no-untyped-call]
    return output


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="madi-create-demo-pdf",
        description="Create a copyright-safe synthetic company PDF for the Project 1 demo.",
    )
    parser.add_argument("output", nargs="?", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing output file explicitly.",
    )
    arguments = parser.parse_args(argv)
    try:
        output = create_demo_pdf(arguments.output, overwrite=arguments.overwrite)
    except (FileExistsError, OSError, ValueError) as error:
        parser.exit(status=2, message=f"error: {error}\n")
    print(
        json.dumps(
            {
                "document": str(output),
                "pages": len(DEMO_PAGES),
                "fictional": True,
                "next_step": "Index this file with madi-build-index or POST /v1/documents/index.",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
