"""
Ingestion Pipeline Module
Orchestrates the process of reading Markdown files, atomizing them, and preparing for storage.
"""

import os
import sys
import json
import concurrent.futures
from pathlib import Path
from typing import Dict, Any, List

# Ensure we can import from src
sys.path.insert(0, str(Path(__file__).parent))

from atomizer import MarkdownAtomizer

class IngestionPipeline:
    """
    Pipeline to ingest Markdown files into atomic knowledge entries.
    """

    def __init__(self, output_dir: str = "atomized_data", max_workers: int = 10):
        self.atomizer = MarkdownAtomizer()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_workers = max_workers

    def process_file(self, md_path: str, force: bool = False) -> str:
        """
        Process a single Markdown file.
        Returns the path to the saved JSON output.
        """
        md_file = Path(md_path)
        if not md_file.exists():
            raise FileNotFoundError(f"File not found: {md_path}")

        # Check if already exists
        output_filename = f"atomized_{md_file.stem}.json"
        output_path = self.output_dir / output_filename
        if output_path.exists() and not force:
            print(f"[Pipeline] Skipping {md_file.name} (already atomized)")
            return str(output_path)

        print(f"[Pipeline] Reading {md_file.name}...")
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Extract section ID from filename (e.g., Section_2_2_2.md -> 2.2.2)
        # Using simple heuristic
        section_id = md_file.stem.replace("Section_", "").replace("_", ".")

        # Atomize
        print(f"[Pipeline] Atomizing content for Section {section_id}...")
        result = self.atomizer.atomize_section(content, section_id=section_id)

        # Add metadata
        result["source_file"] = str(md_file)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"[Pipeline] Saved atomized data to: {output_path}")
        return str(output_path)

    def process_directory(self, input_dir: str, force: bool = False) -> List[str]:
        """
        Process all Markdown files in a directory using thread pool.
        """
        input_path = Path(input_dir)
        if not input_path.exists() or not input_path.is_dir():
            raise NotADirectoryError(f"Directory not found: {input_dir}")

        md_files = sorted(list(input_path.glob("Section_*.md")))
        print(f"[Pipeline] Found {len(md_files)} markdown files. Using {self.max_workers} workers.")

        output_paths = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Prepare futures
            future_to_file = {executor.submit(self.process_file, str(md_file), force): md_file for md_file in md_files}

            for future in concurrent.futures.as_completed(future_to_file):
                md_file = future_to_file[future]
                try:
                    data = future.result()
                    output_paths.append(data)
                except Exception as exc:
                    print(f'[ERROR] {md_file.name} generated an exception: {exc}')

        return output_paths

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ingestion Pipeline")
    parser.add_argument("--file", "-f", type=str, help="Process a single file")
    parser.add_argument("--dir", "-d", type=str, help="Process all files in a directory")
    parser.add_argument("--force", action="store_true", help="Force re-atomization")
    parser.add_argument("--workers", "-w", type=int, default=10, help="Number of parallel workers")
    args = parser.parse_args()

    pipeline = IngestionPipeline(max_workers=args.workers)

    if args.file:
        pipeline.process_file(args.file, force=args.force)
    elif args.dir:
        pipeline.process_directory(args.dir, force=args.force)
    else:
        # Default test
        TEST_FILE = r"d:\SimpleMem\knowledge_base\Section_2_2_2.md"
        if os.path.exists(TEST_FILE):
            pipeline.process_file(TEST_FILE)
        else:
            print(f"[WARN] No target specified and default test file not found.")
