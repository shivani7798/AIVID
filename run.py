#!/usr/bin/env python3
import argparse
import logging
import shutil
import time
from pathlib import Path
import fitz  # PyMuPDF

def sanitize_filename(name: str) -> str:
    """Sanitize string for use as filename."""
    return "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).rstrip().replace(' ', '_').lower()

def extract_title(pdf_path: Path) -> str:
    """Extract title from PDF's first page."""
    try:
        doc = fitz.open(pdf_path)
        page = doc.load_page(0)
        text = page.get_text()
        lines = text.split('\n')
        title = next((line.strip() for line in lines if line.strip()), pdf_path.stem)
        doc.close()
        return title
    except Exception as e:
        logging.warning(f"Failed to extract title from {pdf_path}: {e}")
        return pdf_path.stem

def setup_logging(level: str):
    """Set up logging configuration."""
    numeric_level = getattr(logging, level.upper(), logging.DEBUG)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

def main():
    parser = argparse.ArgumentParser(description="Process PDFs into video explainers.")
    parser.add_argument("--log-level", default="DEBUG", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Set logging level")
    args = parser.parse_args()
    
    setup_logging(args.log_level)
    
    input_dir = Path("input")
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    pdfs = list(input_dir.glob("*.pdf"))
    if not pdfs:
        logging.info("No PDFs found in input folder.")
        return
    
    for pdf in pdfs:
        start_time = time.time()
        logging.info(f"Processing {pdf.name}")
        
        # Extract and sanitize title
        title = extract_title(pdf)
        sanitized = sanitize_filename(title)
        
        # Create output folder (handle duplicates)
        folder = output_dir / sanitized
        counter = 1
        while folder.exists():
            folder = output_dir / f"{sanitized}_{counter}"
            counter += 1
        folder.mkdir()
        
        # Copy PDF
        pdf_dest = folder / "paper.pdf"
        shutil.copy(pdf, pdf_dest)
        
        # Process
        try:
            from make_video import main as make_video_main
            import asyncio
            asyncio.run(make_video_main(folder))
            elapsed = time.time() - start_time
            logging.info(f"Completed {pdf.name} in {elapsed:.2f}s → {folder}")
        except Exception as e:
            logging.error(f"Failed to process {pdf.name}: {e}")
    
    # Clean up legacy directories
    for legacy in ["read_pdf", "audio", "timeline"]:
        legacy_path = Path(legacy)
        if legacy_path.exists():
            shutil.rmtree(legacy_path)
            logging.info(f"Removed legacy directory: {legacy}")

if __name__ == "__main__":
    main()