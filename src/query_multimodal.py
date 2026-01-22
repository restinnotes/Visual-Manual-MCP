"""
Multimodal Query Script
Performs semantic search on the multimodal memory.
"""

import sys
import os
from pathlib import Path
from typing import List

# Setup paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "simplified_mem"))

import lancedb
from database.vector_store import VectorStore
from utils.embedding import EmbeddingModel
import config as global_config

def query_multimodal(query: str, top_k: int = 3):
    print(f"\n🔍 Query: '{query}'")

    # 1. Connect to DB
    # Note: We need to access the specific table "multimodal_memory"
    # The VectorStore class defaults to config.MEMORY_TABLE_NAME
    # We'll instantiate it specifically for our table
    db = lancedb.connect(global_config.LANCEDB_PATH)
    table_name = "multimodal_memory"

    if table_name not in db.table_names():
        print(f"[ERROR] Table '{table_name}' not found. Did you run inject_multimodal.py?")
        return

    table = db.open_table(table_name)

    # 2. Embed Query
    embedder = EmbeddingModel()
    query_vector = embedder.encode_query([query])[0]

    # 3. Search
    results = table.search(query_vector.tolist()).limit(top_k).to_list()

    # 4. Display Results
    print(f"✅ Found {len(results)} matches:\n")

    for i, res in enumerate(results):
        score = 1.0 # LanceDB doesn't easy give score in .to_list() unless requested, assuming close enough
        # Actually _distance is usually available
        dist = res.get('_distance', 0.0)

        print(f"--- [Match #{i+1}] (Dist: {dist:.4f}) ---")
        print(f"📄 Document: {res['topic']}")
        print(f"📍 Section:  {res['section']}") # e.g. "Page 5"
        print(f"🖼️  Image:    {res['location']}")
        print(f"📝 Text Snippet: {res['lossless_restatement'][:150].replace(chr(10), ' ')}...")
        print("-" * 40)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="Query string")
    parser.add_argument("--k", type=int, default=3, help="Top K results")
    args = parser.parse_args()

    query_multimodal(args.query, args.k)
