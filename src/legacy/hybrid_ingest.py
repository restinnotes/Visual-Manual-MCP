"""
Hybrid Page-Level Ingestor - 混合式页面摄取器

策略:
1. 默认使用 PyMuPDF 提取纯文本 (快速, 低成本)
2. 当页面包含 "Figure" 或 "Table" 关键词时 -> 触发 "全页视觉分析" (Full Page Vision)
   - 截图整页
   - 将 PyMuPDF 提取的文本作为 "校准提示 (Calibration Hint)" 传给 Vision LLM
   - 要求 LLM 重建 Markdown，优先信任图片中的图表布局，使用文本校准文字识别
"""

import sys
import os
import re
import fitz  # PyMuPDF
import base64
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "simplified_mem"))

from vision_agent import ImageTranslator
from stream_builder_legacy import TOCEntry  # Reuse TOC structure but not logic

class HybridPageIngestor:
    def __init__(self, pdf_path: str, output_dir: str):
        self.doc = fitz.open(pdf_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.vision_agent = ImageTranslator()

    def close(self):
        if self.doc:
            self.doc.close()

    def process_document(self, toc_json_path: str, target_page: int = None, target_section: str = None) -> List[str]:
        """
        处理文档: 遍历所有页面，根据策略生成 Markdown
        """
        # Load TOC to know section boundaries (conceptually)
        # In this simplified page-level approach, we generate files per SECTION ID
        # So we need to map Pages -> Sections
        page_to_section = self._map_pages_to_sections(toc_json_path)

        # Buffer to hold markdown content for each section
        section_buffers: Dict[str, List[str]] = {}

        total_pages = len(self.doc)
        print(f"[Ingestor] Processing {total_pages} pages...")

        for page_idx in range(total_pages):
            page_num = page_idx + 1

            # Filtering
            if target_page and page_num != target_page:
                continue

            # If target section provided, check if this page belongs to it
            current_section_id = page_to_section.get(page_num, "Unknown")
            if target_section and current_section_id != target_section:
                continue

            print(f"\n[Page {page_num}] Section: {current_section_id}")

            # 1. Extract Raw Text (Candidate)
            page = self.doc[page_idx]
            raw_text = page.get_text("text")

            # 2. Decision Logic
            use_vision = self._should_trigger_vision(raw_text)

            final_content = ""
            if use_vision:
                print(f"  [TRIGGER] Found Figure/Table -> Activating Vision Mode")
                final_content = self._process_with_vision(page, raw_text, page_num)
            else:
                print(f"  [FAST] Text-only mode")
                final_content = self._clean_text(raw_text)

            # 3. Buffer Result
            if current_section_id not in section_buffers:
                section_buffers[current_section_id] = []

            # Add page marker for debugging/structure
            section_buffers[current_section_id].append(final_content)

        # 4. Write to Files
        generated_files = []
        for sec_id, contents in section_buffers.items():
            if sec_id == "Unknown" or sec_id == "_preamble":
                continue

            safe_id = sec_id.replace(".", "_")
            out_path = self.output_dir / f"Section_{safe_id}.md"

            full_text = "\n\n".join(contents)

            # Final Cleanup common to both modes (e.g. TBD artifacts)
            full_text = self._post_process_cleanup(full_text)

            with open(out_path, "w", encoding="utf-8") as f:
                f.write(full_text)

            print(f"[Write] Saved {out_path} ({len(full_text)} chars)")
            generated_files.append(str(out_path))

        return generated_files

    def _should_trigger_vision(self, text: str) -> bool:
        """
        Trigger if 'Figure X' or 'Table X' is detected.
        Wait, user said 'contains figure'.
        Let's be specific to avoid false positives.
        """
        # Look for "Figure <digit>" or "Table <digit>"
        # Also include "Fig." just in case
        pattern = r"(Figure|Fig\.|Table)\s+\d+"
        return bool(re.search(pattern, text))

    def _clean_text(self, text: str) -> str:
        """
        Basic cleaning for text mode.
        Remove headers/footers based on simple heuristics (top/bottom lines) is risky without bbox.
        We'll just rely on the fact that raw text usually extracts in order.
        TODO: Improve heater/footer filtering if strictly needed, but Vision mode handles the critical parts.
        """
        # Simple noise filter
        lines = text.split('\n')
        # Filter obvious noise lines
        clean_lines = [
            line for line in lines
            if "Modifications reserved" not in line
            and "Document number" not in line
            and "Bosch Sensortec" not in line
        ]
        return "\n".join(clean_lines)

    def _process_with_vision(self, page: fitz.Page, raw_text: str, page_num: int) -> str:
        """
        Full Page Vision Analysis.
        """
        # 1. Take Snapshot (High DPI)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img_bytes = pix.tobytes("png")
        image_b64 = base64.b64encode(img_bytes).decode("utf-8")
        image_url = f"data:image/png;base64,{image_b64}"

        # 2. Build Prompt
        prompt = f"""
I am converting a technical manual page to Markdown.
This specific page contains complex Figures or Tables (Vector Graphics) that standard OCR misses.

[Raw Extracted Text (For Calibration Only)]
{raw_text[:2000]} ... (truncated)

[Task]
1. Reconstruct this page into clean Markdown.
2. CRITICAL: When you see a Figure (Chart, Diagram, etc.), describe it in detail using the visual information from the image.
   - Do NOT just copy the caption. Explain the visual data flow, architecture, or chart values.
   - For Tables, reconstruct them as Markdown tables.
3. Use the [Raw Text] to correct spelling/OCR errors in the image analysis, but TRUST THE IMAGE for layout and structure.
4. Remove headers (e.g., "Bosch Sensortec") and footers (page numbers, "Modifications reserved").
5. Do not output "Here is the markdown..." just output the content.
"""

        # 3. Call Vision Agent (reusing client logic manually for custom prompt)
        try:
            response = self.vision_agent.client.chat.completions.create(
                model=self.vision_agent.model,
                messages=[
                    {"role": "system", "content": "You are a technical documentation expert."},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_url}}
                        ]
                    }
                ],
                max_tokens=2500,
                temperature=0.1 # Low temp for precision
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"[ERROR] Vision API failed on Page {page_num}: {e}")
            return f"[VISION FAILED MESSAGE]\n\n{raw_text}"

    def _post_process_cleanup(self, text: str) -> str:
        """Global cleanup for TBDs etc"""
        text = text.replace("[TBD]", "")
        # Remove lines like "Revision_2.6..."
        text = re.sub(r"Revision_\d+\.\d+_.*", "", text)
        return text

    def _map_pages_to_sections(self, toc_path: str) -> Dict[int, str]:
        """
        Creates a map {PageNum: SectionID}.
        Logic: A page belongs to the latest Section ID encountered in TOC up to that page.
        """
        import json
        with open(toc_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Flatten TOC
        entries = []
        def flatten(items):
            for item in items:
                # Extract ID "2.2.2" from title "2.2.2 Compiling..."
                match = re.match(r"^([\d.]+)", item["title"])
                sec_id = match.group(1) if match else "Unknown"
                entries.append({"page": item["page"], "id": sec_id})
                if item.get("children"):
                    flatten(item["children"])

        flatten(data.get("toc_tree", []))
        entries.sort(key=lambda x: x["page"])

        # Fill map
        # If Page 5 is Sec 2.1, and Page 8 is Sec 2.2
        # Page 5,6,7 -> 2.1
        page_map = {}
        last_id = "_preamble"

        # We need max page. Let's assume 100 or get from doc (not available here easily without doc open)
        # We'll build up to last known TOC page + buffer
        max_page = entries[-1]["page"] + 50

        toc_idx = 0
        for p in range(1, max_page + 1):
            # Check if this page starts a new section
            # Handle multiple sections on same page?
            # Simplified: The LAST section starting on this page wins for the WHOLE page?
            # Or better: The section active at start of page.
            # Let's stick to: Page mapping follows the starts.

            while toc_idx < len(entries) and entries[toc_idx]["page"] <= p:
                last_id = entries[toc_idx]["id"]
                toc_idx += 1

            page_map[p] = last_id

        return page_map

if __name__ == "__main__":
    # Test script
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", help="Path to PDF")
    parser.add_argument("toc", help="Path to TOC JSON")
    parser.add_argument("--page", type=int, help="Target specific page for debug")
    parser.add_argument("--section", type=str, help="Target specific section")
    args = parser.parse_args()

    ingestor = HybridPageIngestor(args.pdf, "knowledge_base")
    ingestor.process_document(args.toc, target_page=args.page, target_section=args.section)
    ingestor.close()
