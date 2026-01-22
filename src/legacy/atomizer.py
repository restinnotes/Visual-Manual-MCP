"""
Markdown Atomizer Module - 深度知识原子化
Transform linear Markdown into atomic knowledge entries.
"""

import os
import sys
import json
import re
from pathlib import Path
from typing import List, Dict, Any

# Ensure we can import from simplified_mem
sys.path.insert(0, str(Path(__file__).parent.parent / "simplified_mem"))

from openai import OpenAI

try:
    from config import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL
except ImportError:
    # Default fallback
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", None)
    LLM_MODEL = "gpt-4"

class MarkdownAtomizer:
    """
    Core engine for Phase 4: deep atomization of Markdown content.
    """

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.api_key = api_key or OPENAI_API_KEY
        self.base_url = base_url or OPENAI_BASE_URL
        self.model = model or LLM_MODEL

        # Initialize OpenAI client
        client_kwargs = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        self.client = OpenAI(**client_kwargs)

    def atomize_section(self, markdown_text: str, section_id: str = "") -> Dict[str, Any]:
        """
        Main entry point: Process a markdown section.
        Steps:
        1. Semantic Chunking
        2. Coreference Resolution per chunk
        3. Relation Extraction per chunk
        """
        chunks = self._semantic_chunking(markdown_text)

        atomized_results = []
        all_relations = []

        print(f"[Atomizer] Processing {len(chunks)} chunks for section {section_id}...")

        for idx, chunk in enumerate(chunks):
            # 1. Coreference Resolution
            resolved_text = self._resolve_coreference(chunk, section_id)

            # 2. Relation Extraction
            relations = self._extract_relations(resolved_text)

            atomized_entry = {
                "chunk_id": f"{section_id}_{idx}",
                "original_text": chunk,
                "atomized_text": resolved_text,
                "relations": relations
            }
            atomized_results.append(atomized_entry)
            all_relations.extend(relations)

        return {
            "section_id": section_id,
            "entries": atomized_results,
            "total_relations": all_relations
        }

    def _semantic_chunking(self, text: str) -> List[str]:
        """
        Split text into logical chunks.
        Strategy: Split by double newlines, but keep code blocks and figures intact.
        """
        # Simple splitting by double newline for now, but sensitive to code fences
        chunks = []
        current_chunk = []
        in_code_block = False

        lines = text.split('\n')

        for line in lines:
            if line.strip().startswith('```'):
                in_code_block = not in_code_block

            # If we hit an empty line and we are NOT in a code block, split
            if not line.strip() and not in_code_block:
                if current_chunk:
                    chunks.append('\n'.join(current_chunk))
                    current_chunk = []
            else:
                current_chunk.append(line)

        if current_chunk:
            chunks.append('\n'.join(current_chunk))

        return chunks

    def _resolve_coreference(self, chunk: str, context_hint: str) -> str:
        """
        Use LLM to resolve pronouns to specific entities.
        """
        system_prompt = """You are a technical editor. Your task is to perform "Coreference Resolution" on the provided text.
Replace pronous (it, they, this command, etc.) with their specific entity names based on context.
Make the text self-contained and atomic. DO NOT change the meaning or technical details.
If the text is already clear, return it as is.
"""
        user_prompt = f"Context: Section {context_hint}\nText to resolve:\n---\n{chunk}\n---\n\nResolved Text:"

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[ERROR] Coreference resolution failed: {e}")
            return chunk

    def _extract_relations(self, text: str) -> List[Dict[str, str]]:
        """
        Extract engineering relations as triplets.
        """
        system_prompt = """You are a Knowledge Graph Engineer. Extract technical relationships from the text.
Output a JSON list of triplets with keys: "subject", "relation", "object".
Relations should be: REQUIRES, CONFLICTS_WITH, AFFECTS, DEFINES, HAS_PARAM, etc.
Only extract EXPLICIT engineering logic.
Example:
Input: "The build.bat script requires a Windows environment."
Output: [{"subject": "build.bat", "relation": "REQUIRES", "object": "Windows environment"}]
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content.strip()
            data = json.loads(content)
            # Handle if the LLM wraps it in a key
            if isinstance(data, dict):
                # Try to find a list value
                for k, v in data.items():
                    if isinstance(v, list):
                        return v
                return []
            return data if isinstance(data, list) else []
        except Exception as e:
            print(f"[ERROR] Relation extraction failed: {e}")
            return []

if __name__ == "__main__":
    # Simple test
    atomizer = MarkdownAtomizer()
    chunk = "It is used to compile the firmware. Build.bat must be run on Windows."
    print("Original:", chunk)
    res = atomizer._resolve_coreference(chunk, "2.2.2 Compilation")
    print("Resolved:", res)
    rels = atomizer._extract_relations(res)
    print("Relations:", rels)
