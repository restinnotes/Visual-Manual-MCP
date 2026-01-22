"""
SimpleMem Master Ingestion Script - 一键生成管线
Chains: [PDF + TOC] -> [Visual Markdown] -> [Atomic Knowledge JSON]
"""

import os
import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from generator import run_pipeline
from ingest_markdown import IngestionPipeline

def run_master_pipeline(pdf_path: str, toc_path: str, output_base: str = "output"):
    """
    Run the full end-to-end pipeline.
    """
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        print(f"[ERROR] PDF not found: {pdf_path}")
        return

    # 1. Define internal paths
    kb_dir = Path(output_base) / "knowledge_base"
    atom_dir = Path(output_base) / "atomized_data"

    print("=" * 60)
    print(f"🚀 SimpleMem Master Pipeline: {pdf_file.name}")
    print("=" * 60)

    # Step 1: Visual Markdown Generation (generator.py)
    print("\n[Step 1/2] Generating Visual Markdown sections (Hybrid Page-Level)...")
    # Use new Hybrid pipeline
    from hybrid_ingest import HybridPageIngestor

    ingestor = HybridPageIngestor(str(pdf_path), str(kb_dir))
    try:
        md_files = ingestor.process_document(str(toc_path))
    finally:
        ingestor.close()

    if not md_files:
        print("[ERROR] No markdown files were generated. Aborting.")
        return

    # Step 2: Deep Atomization (ingest_markdown.py)
    print("\n[Step 2/2] Starting Deep Atomization (Parallel)...")
    pipeline = IngestionPipeline(output_dir=str(atom_dir), max_workers=5)
    atom_files = pipeline.process_directory(str(kb_dir))

    print("\n" + "=" * 60)
    print("✨ Pipeline Complete!")
    print(f"📂 Markdown files: {kb_dir}")
    print(f"📂 Atomized JSON: {atom_dir}")
    print(f"📊 Total Sections: {len(atom_files)}")
    print("=" * 60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SimpleMem One-Click Ingestion")
    parser.add_argument("pdf", type=str, help="Path to the PDF file")
    parser.add_argument("toc", type=str, help="Path to the TOC JSON file")
    parser.add_argument("--output", "-o", type=str, default="output", help="Output base directory")

    args = parser.parse_args()

    run_master_pipeline(args.pdf, args.toc, args.output)
