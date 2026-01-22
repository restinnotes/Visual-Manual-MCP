"""
Multimodal Ingestor - Native Image + Text Processing

Logic:
1. Iterate PDF pages.
2. Render high-res snapshot (for Qwen-VL Visual Embedding).
3. Extract raw text (for BM25 Keyword Search).
4. Save to `multimodal_data/`.
"""

import sys
import os
import fitz  # PyMuPDF
import json
from pathlib import Path
from typing import List, Dict

class MultimodalIngestor:
    def __init__(self, output_dir: str = "multimodal_data"):
        self.output_dir = Path(output_dir)
        self.images_dir = self.output_dir / "images"
        self.texts_dir = self.output_dir / "texts"

        # Create directories
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.texts_dir.mkdir(parents=True, exist_ok=True)

    def ingest_document(self, pdf_path: str) -> str:
        """
        Process PDF and return path to manifest JSON.
        """
        doc = fitz.open(pdf_path)
        doc_name = Path(pdf_path).stem

        manifest = {
            "doc_name": doc_name,
            "doc_path": str(pdf_path),
            "pages": []
        }

        total_pages = len(doc)
        print(f"[Multimodal] Processing {doc_name} ({total_pages} pages)...")

        for page_idx in range(total_pages):
            page_num = page_idx + 1
            page = doc[page_idx]

            # 1. Snapshot (PNG) - High Res (2x zoom = ~144 DPI, sufficient for VL models)
            # Qwen-VL handles dynamic resolution, but clearer is better.
            try:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                image_filename = f"{doc_name}_p{page_num}.png"
                image_path = self.images_dir / image_filename
                pix.save(str(image_path))
            except Exception as e:
                print(f"[ERROR] Failed to render page {page_num}: {e}")
                continue

            # 2. Raw Text (TXT)
            text = page.get_text("text")
            # Basic cleanup
            text = self._clean_text(text)
            text_filename = f"{doc_name}_p{page_num}.txt"
            text_path = self.texts_dir / text_filename

            with open(text_path, "w", encoding="utf-8") as f:
                f.write(text)

            # 3. Add to Manifest
            manifest["pages"].append({
                "page_num": page_num,
                "image_path": str(image_path),
                "text_path": str(text_path),
                "text_preview": text[:100].replace("\n", " ") + "..."
            })

            if page_num % 10 == 0:
                print(f"  Processed {page_num}/{total_pages} pages...")

        doc.close()

        # Save Manifest
        manifest_path = self.output_dir / f"{doc_name}_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        print(f"[Multimodal] Ingestion complete. Manifest: {manifest_path}")
        return str(manifest_path)

    def _clean_text(self, text: str) -> str:
        """Simple Text Cleanup"""
        lines = text.split('\n')
        cleaned = []
        for line in lines:
            l = line.strip()
            # Filter standard noise
            if not l: continue
            if "Bosch Sensortec" in l: continue
            if "Modifications reserved" in l: continue
            if l.startswith("Document number"): continue
            cleaned.append(l)
        return "\n".join(cleaned)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", help="Path to PDF file")
    args = parser.parse_args()

    ingestor = MultimodalIngestor()
    ingestor.ingest_document(args.pdf)
