"""
Verification Script for Phase 4
Runs the IngestionPipeline on a target file and validates the output integrity.
"""

import sys
import json
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from ingest_markdown import IngestionPipeline

def verify_output(json_path: str):
    """
    Check the content of the generated JSON.
    """
    print(f"\n[Verification] Checking {json_path}...")

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Check structure
    assert "section_id" in data
    assert "entries" in data
    assert "total_relations" in data

    entries = data["entries"]
    relations = data["total_relations"]

    print(f"  - Section ID: {data['section_id']}")
    print(f"  - Total Atoms: {len(entries)}")
    print(f"  - Total Relations: {len(relations)}")

    # Check for specific expected content (if this is Section 2.2.2)
    found_windows = False
    found_build_bat = False

    for rel in relations:
        # Check if we captured the build.bat -> Windows dependency
        # This is a heuristic check based on typical LLM output
        s = rel.get("subject", "").lower()
        o = rel.get("object", "").lower()
        r = rel.get("relation", "").lower()

        print(f"    Possible Relation: {s} --[{r}]--> {o}")

        if "build.bat" in s and "windows" in o:
            found_windows = True
            print("    [MATCH] Found dependency: build.bat -> Windows")

    if len(entries) > 0:
        print("\n  [Sample Atom]")
        print(f"  Original: {entries[0]['original_text'][:50]}...")
        print(f"  Resolved: {entries[0]['atomized_text'][:50]}...")

    print("\n[Verification] Basic checks passed!")

if __name__ == "__main__":
    # Target file
    target_md = r"d:\SimpleMem\knowledge_base\Section_2_2_2.md"

    if not os.path.exists(target_md):
        print(f"[ERROR] Target file not found: {target_md}")
        print("Please ensure Phase 1-3 ran and generated the knowledge base.")
        sys.exit(1)

    pipeline = IngestionPipeline()
    output_json = pipeline.process_file(target_md)

    verify_output(output_json)
