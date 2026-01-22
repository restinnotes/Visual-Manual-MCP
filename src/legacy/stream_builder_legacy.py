"""
Stream Builder Module - 流式构建器

负责将 PDF 文档转换为全局线性元素流，并按章节进行切割。

核心组件:
- StreamElement: 流中的单个元素 (文本块/图片块)
- PDFStreamLoader: 从 PDF 提取所有元素并排序
- SectionSegmenter: 根据 TOC 对流进行章节切割
"""

import io
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

# 初始化 RapidOCR 引擎 (全局单例)
_ocr_engine = None

def get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        _ocr_engine = RapidOCR()
    return _ocr_engine


class ElementType(Enum):
    TEXT = "text"
    IMAGE = "image"
    HEADER = "header"  # 章节标题 (特殊文本块)


@dataclass
class StreamElement:
    """流中的单个元素"""
    element_type: ElementType
    content: str  # 文本内容或图片路径 (对于图片)
    page_num: int  # 原始页码 (1-indexed for human readability)
    y_position: float  # 元素在页面上的 Y 坐标 (用于排序)
    bbox: tuple = field(default_factory=tuple)  # (x0, y0, x1, y1)
    image_bytes: Optional[bytes] = None  # 图片的原始字节 (如果是图片)
    section_id: Optional[str] = None  # 所属章节 ID (由 Segmenter 填充)

    def __repr__(self):
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<{self.element_type.value}@P{self.page_num}:Y{self.y_position:.0f} '{preview}'>"


@dataclass
class TOCEntry:
    """目录条目"""
    title: str
    page: int  # 1-indexed
    level: int
    section_id: str  # 例如 "2.2.2"
    children: list = field(default_factory=list)


class PDFStreamLoader:
    """
    从 PDF 中提取所有文本块和图片块，构建全局线性流。

    流的顺序按照 (page_num, y_position) 排序，模拟人类的阅读顺序。
    """

    # 图片最小尺寸阈值 (过滤装饰性小图)
    MIN_IMAGE_WIDTH = 50
    MIN_IMAGE_HEIGHT = 50

    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)
        self.doc: Optional[fitz.Document] = None
        self.global_stream: list[StreamElement] = []

    def load(self) -> list[StreamElement]:
        """加载 PDF 并构建全局流"""
        self.doc = fitz.open(self.pdf_path)
        all_elements = []

        for page_idx in range(len(self.doc)):
            page = self.doc[page_idx]
            page_num = page_idx + 1  # 1-indexed

            # 提取文本块
            text_elements = self._extract_text_blocks(page, page_num)
            all_elements.extend(text_elements)

            # 提取图片块
            image_elements = self._extract_images(page, page_num)
            all_elements.extend(image_elements)

        # 按 (page_num, y_position) 排序形成线性流
        self.global_stream = sorted(all_elements, key=lambda e: (e.page_num, e.y_position))

        # [自动修复] 恢复丢失的矢量图 (针对 Figure X 但无图片的情况)
        self._recover_vector_figures()

        # 再次排序，确保插入的图片在正确位置
        self.global_stream.sort(key=lambda e: (e.page_num, e.y_position))

        return self.global_stream

    def _recover_vector_figures(self):
        """
        扫描流中的 'Figure X:' 字样，如果上方没有图片，则尝试截图 (处理矢量绘图)。
        """
        for i, elem in enumerate(self.global_stream):
            if elem.element_type == ElementType.TEXT and re.match(r"^Figure\s+\d+:", elem.content):
                # 检查上一个元素是否是图片
                prev_elem = self.global_stream[i-1] if i > 0 else None

                # 如果前一个不是图片，或者距离太远 (>400 units)，或者在不同页
                needs_recovery = False
                if not prev_elem:
                    needs_recovery = True
                elif prev_elem.page_num != elem.page_num:
                    # 图片在上一页？或者在当前页顶部（Caption在Top）
                    # 无论如何，只要这就是当页第一个元素（或前面无图片），就尝试截图
                    needs_recovery = True
                elif prev_elem.element_type != ElementType.IMAGE:
                    # 前一个不是图片 (是文本)
                    needs_recovery = True
                elif (elem.y_position - prev_elem.y_position) > 400:
                    # 距离太远，可能不是对应的图
                    needs_recovery = True

                if needs_recovery:
                    print(f"[Auto-Recovery] Detected orphan caption '{elem.content[:20]}...' at P{elem.page_num}:Y{elem.y_position}. Attempting snapshot.")
                    snapshot = self._take_page_snapshot(elem.page_num, elem.y_position)
                    if snapshot:
                        # 插入到 caption 之前
                        self.global_stream.append(snapshot)

    def _take_page_snapshot(self, page_num: int, caption_y: float) -> Optional[StreamElement]:
        """对 caption 上方区域进行截图"""
        try:
            page = self.doc[page_num - 1]
            rect = page.rect

            # 定义截图区域: Caption 上方 300 像素范围 (不包括页眉)
            # 动态调整高度: min(caption_y - 50, 350)
            lookback_height = 350
            # 避开页眉 (Y=50)
            top_y = max(50, caption_y - lookback_height)
            bottom_y = max(top_y + 50, caption_y - 10) # 留 10px 间隙

            clip_rect = fitz.Rect(rect.x0 + 50, top_y, rect.x1 - 50, bottom_y) # 左右留边

            # 渲染
            pix = page.get_pixmap(clip=clip_rect, matrix=fitz.Matrix(2, 2)) # 2x 缩放保证清晰
            img_bytes = pix.tobytes("png")

            return StreamElement(
                element_type=ElementType.IMAGE,
                content=f"[SNAPSHOT:P{page_num}]",
                page_num=page_num,
                y_position=top_y,
                bbox=(clip_rect.x0, clip_rect.y0, clip_rect.x1, clip_rect.y1),
                image_bytes=img_bytes
            )
        except Exception as e:
            print(f"[WARN] Snapshot failed: {e}")
            return None

    def _extract_text_blocks(self, page: fitz.Page, page_num: int) -> list[StreamElement]:
        """提取页面上的文本块 (过滤页眉页脚噪音)"""
        elements = []
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
        page_height = page.rect.height

        # 噪音模式 (页眉/页脚常见文本)
        NOISE_PATTERNS = [
            "Modifications reserved",
            "Data subject to change",
            "Printed in Germany",
            "Document number:",
            "Revision_",
            "| 61",  # 页码分隔符
            "Bosch Sensortec |",
            "[TBD]",
            ". . . . . .", # TOC 引导符
        ]

        for block in blocks:
            if block.get("type") != 0:  # 0 = text block
                continue

            # 合并 block 中的所有行
            text_lines = []
            for line in block.get("lines", []):
                line_text = "".join(span["text"] for span in line.get("spans", []))
                text_lines.append(line_text)

            text = "\n".join(text_lines).strip()
            if not text:
                continue

            bbox = block["bbox"]  # (x0, y0, x1, y1)
            y_pos = bbox[1]  # y0

            # 过滤条件 1: 页眉 (Y < 50) 或页脚 (Y > page_height - 50)
            if y_pos < 50 or y_pos > page_height - 50:
                # 额外检查是否包含噪音模式
                if any(pattern in text for pattern in NOISE_PATTERNS):
                    continue  # 跳过噪音

            # 过滤条件 2: 任何位置包含噪音模式的短文本块
            if len(text) < 100 and any(pattern in text for pattern in NOISE_PATTERNS):
                continue

            elements.append(StreamElement(
                element_type=ElementType.TEXT,
                content=text,
                page_num=page_num,
                y_position=y_pos,
                bbox=tuple(bbox)
            ))

        return elements

    def _extract_images(self, page: fitz.Page, page_num: int) -> list[StreamElement]:
        """
        提取页面上的实质性图片。

        简化过滤逻辑:
        1. 如果图片区域内有 PyMuPDF 文本 -> 丢弃 (文字已在 text stream)
        2. 如果无文本且位于页眉/页脚 -> 丢弃 (装饰图片)
        3. 否则 -> 保留 (实质性图片：截图/图表)
        """
        elements = []
        page_height = page.rect.height

        # 页眉/页脚区域阈值
        HEADER_THRESHOLD = 80  # Y < 80 为页眉
        FOOTER_THRESHOLD = page_height - 80  # Y > page_height - 80 为页脚

        for img_info in page.get_images(full=True):
            xref = img_info[0]

            try:
                base_image = self.doc.extract_image(xref)
                image_bytes = base_image["image"]

                # 获取图片在页面上的位置
                img_rects = page.get_image_rects(xref)
                if not img_rects:
                    continue

                rect = img_rects[0]  # 取第一个位置

                # === 简化判定 ===
                pdf_text = page.get_text("text", clip=rect).strip()

                # 条件 A: 有文本层 -> 丢弃 (文字渲染层，已在 text stream)
                # 修正: 许多图表包含少量文字标签，不能直接丢弃。
                # 只有当图片区域包含"大量"文字(可能是正文背景图)时才丢弃。
                if pdf_text and len(pdf_text) > 50:
                    print(f"[DEBUG] Skip image at {rect} (Page {page_num}): Overlaps with significant text ({len(pdf_text)} chars)")
                    continue

                # 条件 B: 无文本 + 页眉/页脚位置 -> 丢弃 (装饰图片)
                if rect.y0 < HEADER_THRESHOLD or rect.y0 > FOOTER_THRESHOLD:
                    print(f"[DEBUG] Skip image at {rect} (Page {page_num}): In Header/Footer region")
                    continue

                # 通过过滤 -> 保留为实质性图片
                elements.append(StreamElement(
                    element_type=ElementType.IMAGE,
                    content=f"[IMAGE:{xref}]",
                    page_num=page_num,
                    y_position=rect.y0,
                    bbox=(rect.x0, rect.y0, rect.x1, rect.y1),
                    image_bytes=image_bytes
                ))

            except Exception as e:
                print(f"[WARN] 提取图片失败 xref={xref}: {e}")
                continue

        return elements

    def close(self):
        if self.doc:
            self.doc.close()


class SectionSegmenter:
    """
    根据 TOC 将全局流切割为按章节分段的子流。

    核心逻辑:
    1. 将 TOC 扁平化为有序列表 (按页码/Y位置)
    2. 遍历全局流，当检测到章节标题时进行切割
    3. 返回 Dict[section_id, List[StreamElement]]
    """

    def __init__(self, toc_json_path: str):
        self.toc_path = Path(toc_json_path)
        self.flat_toc: list[TOCEntry] = []
        self._load_toc()

    def _load_toc(self):
        """加载并扁平化 TOC"""
        with open(self.toc_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        def flatten(entries, parent_id=""):
            for entry in entries:
                title = entry["title"]
                # 从标题中提取章节 ID (例如 "2.2.2 Compiling..." -> "2.2.2")
                match = re.match(r"^([\d.]+)\s+", title)
                section_id = match.group(1) if match else title

                toc_entry = TOCEntry(
                    title=title,
                    page=entry["page"],
                    level=entry["level"],
                    section_id=section_id
                )
                self.flat_toc.append(toc_entry)

                if entry.get("children"):
                    flatten(entry["children"], section_id)

        flatten(data.get("toc_tree", []))
        # 按页码排序
        self.flat_toc.sort(key=lambda e: e.page)

    def segment(self, stream: list[StreamElement]) -> dict[str, list[StreamElement]]:
        """
        将全局流按章节切割。

        算法:
        1. 为每个 TOC 条目创建一个"锚点"
        2. 遍历流，匹配文本块是否包含章节标题
        3. 匹配成功时，将该元素标记为 HEADER 并切换到新章节

        返回: {section_id: [elements...]}
        """
        if not stream:
            return {}

        # 创建章节标题到 section_id 的映射
        title_to_section: dict[str, str] = {}
        for toc in self.flat_toc:
            # 使用标题的核心部分进行匹配 (去除数字前缀后的文字)
            match = re.match(r"^[\d.]+\s+(.+)$", toc.title)
            if match:
                core_title = match.group(1).strip()
                title_to_section[core_title] = toc.section_id
            # 同时保留完整标题用于精确匹配
            title_to_section[toc.title] = toc.section_id

        # 结果容器
        sections: dict[str, list[StreamElement]] = {}
        current_section_id = "_preamble"  # 第一个章节之前的内容

        for element in stream:
            detected_section = None

            # 只对文本块进行标题检测
            if element.element_type == ElementType.TEXT:
                detected_section = self._detect_section_header(element.content, title_to_section)

            if detected_section:
                # 切换章节
                current_section_id = detected_section
                element.element_type = ElementType.HEADER
                element.section_id = current_section_id
            else:
                element.section_id = current_section_id

            # 添加到当前章节
            if current_section_id not in sections:
                sections[current_section_id] = []
            sections[current_section_id].append(element)

        return sections

    def _detect_section_header(self, text: str, title_map: dict[str, str]) -> Optional[str]:
        """
        检测文本块是否是章节标题。

        策略 (严格模式):
        1. 文本块必须以 "X.X.X" 格式开头 (如 "2.2.2 Compiling...")
        2. 该 ID 必须存在于 TOC 中
        3. 文本块不能太长 (标题通常很短)
        """
        text = text.strip()

        # 标题通常不会太长
        if len(text) > 150:
            return None

        # 过滤 TOC 条目 (结尾是点和数字)
        # e.g. "3.7 Log Generation Commands ........................ 30"
        if re.search(r"\.\.+\s*\d+$", text):
            return None

        # 唯一策略: 必须以 "X.X.X 标题" 格式开头
        match = re.match(r"^(\d+(?:\.\d+)*)\s+\S", text)
        if match:
            potential_id = match.group(1)
            # 检查这个 ID 是否在 TOC 中
            for toc in self.flat_toc:
                if toc.section_id == potential_id:
                    return potential_id

        return None



# ========== 便捷函数 ==========

def build_stream(pdf_path: str, toc_path: str) -> dict[str, list[StreamElement]]:
    """
    一站式函数: 加载 PDF、构建流、按章节切割。

    返回: {section_id: [StreamElement, ...]}
    """
    loader = PDFStreamLoader(pdf_path)
    try:
        stream = loader.load()
        print(f"[INFO] 加载完成，全局流共 {len(stream)} 个元素")

        segmenter = SectionSegmenter(toc_path)
        sections = segmenter.segment(stream)
        print(f"[INFO] 切割完成，共 {len(sections)} 个章节")

        return sections
    finally:
        loader.close()


if __name__ == "__main__":
    # 测试脚本
    import sys

    PDF_PATH = r"d:\SimpleMem\bhy2cli_test_data\docs\BHy2CLI_User_Guide.pdf"
    TOC_PATH = r"d:\SimpleMem\simplified_mem\verified_toc_tree.json"

    if len(sys.argv) > 1:
        target_section = sys.argv[1]
    else:
        target_section = "2.2.2"  # 默认验证目标

    print(f"=== Stream Builder 测试 ===")
    print(f"目标章节: {target_section}")
    print()

    sections = build_stream(PDF_PATH, TOC_PATH)

    if target_section in sections:
        elements = sections[target_section]
        print(f"\n--- 章节 {target_section} 内容 ({len(elements)} 个元素) ---")
        for i, elem in enumerate(elements):
            print(f"  [{i}] {elem}")
    else:
        print(f"[WARN] 未找到章节 {target_section}")
        print(f"可用章节: {list(sections.keys())}")
