"""
Database Injection Script
Loads atomized JSON data, builds RAPTOR hierarchical summaries, and injects everything into LanceDB.
"""

import os
import sys
import json
import concurrent.futures
from pathlib import Path
from typing import List

# Setup paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "simplified_mem"))

from database.vector_store import VectorStore
from models.memory_entry import MemoryEntry
from utils.llm_client import LLMClient
from simplemem.indexing.raptor_builder import RaptorTreeBuilder
import config as global_config

def load_atomized_data(data_dir: str) -> List[MemoryEntry]:
    """
    Load all atomized JSON files and convert to MemoryEntry objects (Level 0).
    """
    data_path = Path(data_dir)
    if not data_path.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    json_files = sorted(list(data_path.glob("atomized_*.json")))
    print(f"[Loader] Found {len(json_files)} JSON files in {data_dir}")

    all_entries = []

    for jf in json_files:
        try:
            with open(jf, "r", encoding="utf-8") as f:
                data = json.load(f)

            section_id = data.get("section_id", "Unknown")
            entries_data = data.get("entries", [])

            for item in entries_data:
                # Map extracted fields to MemoryEntry
                # Note: 'atomized_text' is the resolved text we want to query
                # 'relations' specific to this chunk

                # Check for relations
                chunk_relations = item.get("relations", [])

                # Create keyword string from relations for better retrieval
                rel_keywords = []
                for r in chunk_relations:
                    s, pred, o = r.get("subject"), r.get("relation"), r.get("object")
                    if s and o:
                        rel_keywords.append(f"{s} {o}")

                # Simple keyword extraction (fallback) if no relations
                keywords = rel_keywords if rel_keywords else []

                entry = MemoryEntry(
                    lossless_restatement=item["atomized_text"],
                    keywords=keywords,
                    section=f"Section {section_id}",
                    topic=f"Section {section_id} Content",
                    relations=chunk_relations,
                    raptor_level=0,  # Atomic Level
                    location=f"BHy2CLI User Guide Section {section_id}"
                )
                all_entries.append(entry)

        except Exception as e:
            print(f"[ERROR] Failed to load {jf.name}: {e}")

    print(f"[Loader] Loaded {len(all_entries)} atomic entries.")
    return all_entries

def main():
    # 1. Initialize System
    print("="*60)
    print("🚀 SimpleMem Database Injection with RAPTOR")
    print("="*60)

    # Initialize DB (Clear it for fresh start if needed)
    # Note: In production, might want 'clear_db=True' or just append
    if len(sys.argv) > 1 and sys.argv[1] == "--clear":
        print("[DB] Clearing existing database...")
        clear_db = True
    else:
        clear_db = False

    # Setup VectorStore
    # Ensure config path is correct
    if not os.path.exists(global_config.LANCEDB_PATH):
        os.makedirs(global_config.LANCEDB_PATH)

    vector_store = VectorStore(
        db_path=global_config.LANCEDB_PATH,
        table_name=global_config.MEMORY_TABLE_NAME
    )

    if clear_db:
        vector_store.clear()

    # 2. Load Data
    atom_dir = r"d:\SimpleMem\atomized_data"
    l0_entries = load_atomized_data(atom_dir)

    if not l0_entries:
        print("[ERROR] No entries loaded. Exiting.")
        return

    # 3. Build RAPTOR Tree
    print("\n[RAPTOR] Initializing Tree Builder...")
    llm_client = LLMClient() # Uses config defaults
    raptor_builder = RaptorTreeBuilder(llm_client)

    # This generates the full tree: L0 (Original) + L1 (Section Summaries) + L2 (Root)
    # Note: It modifies L0 entries to add parent_ids
    all_entries = raptor_builder.build_tree(l0_entries, doc_name="BHy2CLI_User_Guide")

    # 4. Inject into LanceDB
    print(f"\n[Storage] Injecting {len(all_entries)} entries into LanceDB...")

    # Batch insert to avoid memory issues if huge, though 1000 entries is fine
    BATCH_SIZE = 100
    total = len(all_entries)
    for i in range(0, total, BATCH_SIZE):
        batch = all_entries[i:i+BATCH_SIZE]
        print(f"  - Inserting batch {i}-{min(i+BATCH_SIZE, total)}...")
        vector_store.add_entries(batch)

    print("\n" + "="*60)
    print("✨ Injection Complete!")
    print(f"Total Entries: {total}")
    print("="*60)

if __name__ == "__main__":
    main()
