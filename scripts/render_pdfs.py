"""
Render the sample HTML filings to real multi-page PDFs with headless Chrome,
so the PDF ingestion path (the product's primary path) is measured on the
same gold set. Output: documents/pdf/<name>.pdf (not committed).

    python -m scripts.render_pdfs
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from finsight import config
from scripts.seed_demo import load_manifest

CHROME = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome",
    "chromium",
    "chromium-browser",
]


def chrome_binary() -> str:
    for c in CHROME:
        if Path(c).exists() or shutil.which(c):
            return c
    raise SystemExit("headless Chrome/Chromium not found")


def main() -> None:
    src = Path(config.DOCUMENTS_DIR)
    out = src / "pdf"
    out.mkdir(parents=True, exist_ok=True)
    chrome = chrome_binary()
    for entry in load_manifest():
        html = src / entry["file"]
        pdf = out / (html.stem + ".pdf")
        if pdf.exists():
            continue
        subprocess.run(
            [
                chrome,
                "--headless=new",
                "--disable-gpu",
                "--no-pdf-header-footer",
                f"--print-to-pdf={pdf}",
                html.resolve().as_uri(),
            ],
            check=True,
            capture_output=True,
        )
        print(f"rendered {pdf.name} ({pdf.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
