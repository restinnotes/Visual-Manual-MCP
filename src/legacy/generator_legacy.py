"""
Markdown Generator Module - 文档生成器

将切割后的章节流转换为最终的 Markdown 文件。
整合 Vision Agent 的图片翻译功能，生成图文融合的文档。

核心流程:
1. 遍历章节流中的每个元素
2. 文本元素 -> 直接输出
3. 图片元素 -> 调用 Vision Agent 翻译后输出
4. 写入 knowledge_base/Section_{ID}.md
"""

import os
import sys
from pathlib import Path
from typing import Optional

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent))

from stream_builder import (
    StreamElement, ElementType,
    PDFStreamLoader, SectionSegmenter, build_stream
)
from vision_agent import ImageTranslator


class MarkdownWriter:
    """
    将章节流写入 Markdown 文件。

    支持两种模式:
    1. 纯文本模式: 图片位置用占位符标记
    2. 智能模式: 调用 Vision LLM 翻译图片
    """

    def __init__(
        self,
        output_dir: str = "knowledge_base",
        enable_vision: bool = True,
        vision_translator: Optional[ImageTranslator] = None
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.enable_vision = enable_vision
        self.translator = vision_translator if vision_translator else (
            ImageTranslator() if enable_vision else None
        )

    def write_section(
        self,
        section_id: str,
        elements: list[StreamElement],
        save_images: bool = True
    ) -> Path:
        """
        将单个章节写入 Markdown 文件。

        Args:
            section_id: 章节 ID (如 "2.2.2")
            elements: 该章节的元素列表
            save_images: 是否保存原始图片到子目录

        Returns:
            生成的 Markdown 文件路径
        """
        # 创建图片子目录
        images_dir = self.output_dir / "images" / f"section_{section_id}"
        if save_images:
            images_dir.mkdir(parents=True, exist_ok=True)

        # 构建 Markdown 内容
        md_lines = []
        preceding_context = ""  # 累积的上下文 (用于 Vision)
        section_title = ""
        image_counter = 0

        for element in elements:
            if element.element_type == ElementType.HEADER:
                # 章节标题
                section_title = element.content
                md_lines.append(f"# {element.content}\n\n")
                preceding_context = element.content + "\n"

            elif element.element_type == ElementType.TEXT:
                # 文本块
                text = element.content.strip()
                if text:
                    md_lines.append(text + "\n\n")
                    preceding_context += text + "\n"

            elif element.element_type == ElementType.IMAGE:
                image_counter += 1

                if self.enable_vision and self.translator and element.image_bytes:
                    # 智能模式: 调用 Vision LLM
                    print(f"  [VISION] 翻译图片 {image_counter}...")
                    translated = self.translator.translate(
                        element.image_bytes,
                        preceding_context,
                        section_title
                    )
                    md_lines.append(translated + "\n\n")
                    preceding_context += translated + "\n"
                else:
                    # 纯文本模式: 占位符
                    placeholder = f"[图片 {image_counter}: 待描述]\n\n"
                    md_lines.append(placeholder)

                # 保存原始图片
                if save_images and element.image_bytes:
                    img_path = images_dir / f"image_{image_counter}.png"
                    with open(img_path, "wb") as f:
                        f.write(element.image_bytes)

        # 写入 Markdown 文件
        safe_id = section_id.replace(".", "_")
        md_path = self.output_dir / f"Section_{safe_id}.md"

        with open(md_path, "w", encoding="utf-8") as f:
            f.write("".join(md_lines))

        print(f"  [DONE] 已生成: {md_path}")
        return md_path

    def write_all_sections(
        self,
        sections: dict[str, list[StreamElement]],
        skip_preamble: bool = True
    ) -> list[Path]:
        """
        批量写入所有章节。

        Args:
            sections: {section_id: [elements...]}
            skip_preamble: 是否跳过序言部分 (_preamble)

        Returns:
            生成的所有 Markdown 文件路径
        """
        output_files = []

        for section_id, elements in sections.items():
            if skip_preamble and section_id == "_preamble":
                print(f"  [SKIP] 跳过序言部分")
                continue

            print(f"[处理章节] {section_id} ({len(elements)} 个元素)")
            path = self.write_section(section_id, elements)
            output_files.append(path)

        return output_files


# ========== 端到端管线 ==========

def run_pipeline(
    pdf_path: str,
    toc_path: str,
    output_dir: str = "knowledge_base",
    target_sections: list[str] = None,
    enable_vision: bool = True
) -> list[Path]:
    """
    运行完整的 Stream Injection 管线。

    Args:
        pdf_path: PDF 文件路径
        toc_path: TOC JSON 文件路径
        output_dir: 输出目录
        target_sections: 指定要处理的章节 (None = 全部)
        enable_vision: 是否启用 Vision LLM

    Returns:
        生成的 Markdown 文件路径列表
    """
    print("=" * 50)
    print("Stream Injection Pipeline")
    print("=" * 50)

    # Step 1: 构建流并切割
    print("\n[Phase 1] 构建全局流...")
    sections = build_stream(pdf_path, toc_path)

    # Step 2: 过滤目标章节
    if target_sections:
        sections = {k: v for k, v in sections.items() if k in target_sections}
        print(f"[过滤] 目标章节: {target_sections}")

    # Step 3: 生成 Markdown
    print(f"\n[Phase 2] 生成 Markdown (Vision: {'ON' if enable_vision else 'OFF'})...")
    writer = MarkdownWriter(output_dir=output_dir, enable_vision=enable_vision)
    output_files = writer.write_all_sections(sections)

    print("\n" + "=" * 50)
    print(f"完成! 共生成 {len(output_files)} 个文件")
    print("=" * 50)

    return output_files


if __name__ == "__main__":
    # 默认路径
    PDF_PATH = r"d:\SimpleMem\bhy2cli_test_data\docs\BHy2CLI_User_Guide.pdf"
    TOC_PATH = r"d:\SimpleMem\simplified_mem\verified_toc_tree.json"
    OUTPUT_DIR = r"d:\SimpleMem\knowledge_base"

    # 解析命令行参数
    import argparse
    parser = argparse.ArgumentParser(description="Stream Injection Pipeline")
    parser.add_argument("--section", "-s", type=str, help="指定章节 ID (如 2.2.2)")
    parser.add_argument("--no-vision", action="store_true", help="禁用 Vision LLM")
    parser.add_argument("--output", "-o", type=str, default=OUTPUT_DIR, help="输出目录")
    args = parser.parse_args()

    target = [args.section] if args.section else None

    run_pipeline(
        PDF_PATH,
        TOC_PATH,
        output_dir=args.output,
        target_sections=target,
        enable_vision=not args.no_vision
    )
