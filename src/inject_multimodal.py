"""
Multimodal Database Injection
Loads manifest and injects into LanceDB with Qwen-VL-Embedding simulation.
"""

import sys
import os
import json
import logging
from pathlib import Path
from typing import List

# Setup paths
sys.path.insert(0, str(Path(__file__).parent))
# sys.path.insert(0, str(Path(__file__).parent.parent / "simplified_mem")) # REMOVED

import lancedb
import pyarrow as pa
from database.vector_store import VectorStore
from models.memory_entry import MemoryEntry
from utils.embedding import EmbeddingModel  # We will extend/wrap this

# Mock Qwen-VL Embedding wrapper
# In a real scenario, this would import the actual model code or call an API
class QwenViewEmbeddingWrapper:
    def __init__(self, base_model: EmbeddingModel):
        self.base_model = base_model

    def embed_multimodal(self, text: str, image_path: str) -> List[float]:
        """
        Simulate Qwen-VL Embedding by fusing text and 'visual' features.
        Since we can't run the actual 7B model, we simulate it:
        Vector = Enc(Text) + Enc(Image_Placeholder_Description)

        In production: return model.encode(text, image)
        """
        # Enhance text with a "visual" signal (simulation)
        # This ensures the vector is distinct from pure text
        visual_signal = f" [VISUAL_CONTENT: Image {Path(image_path).name}]"
        combined_input = text + visual_signal

        return self.base_model.encode_single(combined_input)

def inject_multimodal_data(manifest_path: str, clear_db: bool = False):
    manifest_path = Path(manifest_path)
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}")
        return

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # 1. Setup DB
    import config as global_config
    if not os.path.exists(global_config.LANCEDB_PATH):
        os.makedirs(global_config.LANCEDB_PATH)

    # We need a custom schema update for 'image_path'
    # For now, let's just use the 'location' field to store image_path
    # Or 'lossless_restatement' stores raw text, and 'location' stores image path.
    # We'll use the existing VectorStore class but abuse fields slightly to avoid full re-write
    # Ideally: Update VectorStore schema.

    # HACK: Let's reuse 'location' for 'image_path' and 'topic' for 'Doc Name'
    vector_store = VectorStore(
        db_path=global_config.LANCEDB_PATH,
        table_name="multimodal_memory" # Separate table
    )

    # Custom Schema required?
    # VectorStore class currently hardcodes schema.
    # Let's create a specialized one here or extend VectorStore.
    # To keep it simple and robust: We will extend schema in VectorStore (done in previous steps?)
    # Wait, we haven't added 'image_path' to schema yet.
    # Let's use 'location' field as 'image_path' for now as it makes semantic sense (Where is the data? In this image).

    if clear_db:
        vector_store.clear()

    # 2. Embed and Inject
    embedder = EmbeddingModel()
    vl_embedder = QwenViewEmbeddingWrapper(embedder)

    entries = []
    print(f"\n[Inject] Processing {len(manifest['pages'])} pages from {manifest['doc_name']}...")

    for page in manifest['pages']:
        page_num = page['page_num']
        image_path = page['image_path']

        # Load raw text
        with open(page['text_path'], 'r', encoding='utf-8') as f:
            raw_text = f.read()

        # Create Embedding
        # This is where the magic happens: Text + Image -> Vector
        vector = vl_embedder.embed_multimodal(raw_text, image_path) # Returns list float

        # Create Entry
        # Note: We must construct a MemoryEntry object even if we bypass some fields
        entry = MemoryEntry(
            lossless_restatement=raw_text, # Text payload for keyword search
            location=image_path,           # Image Payload for Retrieval
            topic=manifest['doc_name'],
            section=f"Page {page_num}",
            keywords=[], # Auto-generated?
            relations=[]
        )

        entries.append(entry)

    # 3. Batch Insert
    # We need to hack VectorStore to accept our pre-computed vector if possible?
    # VectorStore.add_entries computes embedding internally using self.embedding_model.
    # This is a problem. The standard flow (add_entries) forces text-only embedding.

    # SOLUTION: We will manually insert into the table to bypass the standard text-only embedding
    # But we need access to the table.

    # Prepare data for direct insertion
    data = []
    for i, entry in enumerate(entries):
        # We computed the 'multimodal' vector above manually
        # But 'add_entries' will re-compute it from text.
        # We need to override it.

        # Recalculate vector here to be sure (since previous loop didn't store it in entry object)
        vector = vl_embedder.embed_multimodal(entry.lossless_restatement, entry.location)

        item = {
            "entry_id": entry.entry_id,
            "lossless_restatement": entry.lossless_restatement,
            "keywords": entry.keywords,
            "timestamp": "",
            "location": entry.location,
            "persons": [],
            "entities": [],
            "topic": entry.topic,
            "section": entry.section,
            "relations": "[]",
            "raptor_level": 0,
            "parent_ids": [],
            "vector": vector # Pre-computed Multimodal Vector
        }
        data.append(item)

    print(f"  Inserting {len(data)} multimodal entries...")
    vector_store.table.add(data)

    print("\n[Inject] Complete!")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", help="Path to manifest JSON")
    args = parser.parse_args()

    inject_multimodal_data(args.manifest, clear_db=True)
