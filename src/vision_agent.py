"""
Vision Agent Module - 视觉语义翻译器

使用 Vision LLM 将图片转化为无缝融入文本流的 Markdown 描述。

核心功能:
- 接收图片 + 上下文文本
- 调用 Vision API 生成语义描述
- 输出可直接插入 Markdown 的文本块
"""

import base64
import os
import sys
from pathlib import Path

# 添加 simplified_mem 到路径以导入 config
sys.path.insert(0, str(Path(__file__).parent.parent / "simplified_mem"))

from openai import OpenAI

try:
    from config import OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL
except ImportError:
    # 默认配置
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", None)
    LLM_MODEL = "gpt-4o"


class ImageTranslator:
    """
    将图片翻译为语义化的 Markdown 文本。

    使用 Vision LLM 分析图片内容，并基于上下文生成与阅读流无缝衔接的描述。
    """

    # 系统提示词 - 核心指令
    SYSTEM_PROMPT = """你是一个专业的技术文档处理助手。你的任务是将图片内容"翻译"为文字，使其能够无缝融入技术文档的阅读流程中。

关键规则:
1. **禁止生硬开场**: 不要使用"这张图显示..."、"图片中可以看到..."等开场白
2. **直接描述内容**: 像续写前文一样，直接输出图片传达的信息
3. **保持技术精确**: 如果是代码截图，输出为代码块；如果是架构图，输出数据流描述
4. **格式匹配**: 输出格式应与上下文保持一致 (例如：前文是步骤列表，则继续用列表)

示例:
- 输入: 命令行终端截图
- 正确输出:
  ```bash
  $ bhy2cli --help
  Usage: bhy2cli [OPTIONS]
  ...
  ```
- 错误输出: "这张图显示了命令行终端，其中..."

你必须根据上下文判断这张图片要传达什么信息，然后用最恰当的格式输出。"""

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.api_key = api_key or OPENAI_API_KEY
        self.base_url = base_url or OPENAI_BASE_URL
        self.model = model or LLM_MODEL

        # 自动切换到 Vision 模型 (Moonshot 特有逻辑)
        print(f"[DEBUG] Init ImageTranslator with model: '{self.model}'")
        if "moonshot" in self.model.lower() and "vision" not in self.model.lower():
            print(f"[Vision Agent] 检测到非 Vision 模型 {self.model}，自动切换到 moonshot-v1-8k-vision-preview")
            self.model = "moonshot-v1-8k-vision-preview"

        # 创建 OpenAI 客户端
        client_kwargs = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        self.client = OpenAI(**client_kwargs)

    def translate(
        self,
        image_bytes: bytes,
        preceding_context: str,
        section_title: str = "",
        image_format: str = "png"
    ) -> str:
        """
        将图片翻译为 Markdown 文本。

        Args:
            image_bytes: 图片的原始字节数据
            preceding_context: 图片之前的文本上下文 (章节开头到图片位置)
            section_title: 当前章节标题
            image_format: 图片格式 (png, jpeg, etc.)

        Returns:
            可直接插入 Markdown 的文本
        """
        # 构建上下文提示
        context_prompt = self._build_context_prompt(preceding_context, section_title)

        # 将图片编码为 base64
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        image_url = f"data:image/{image_format};base64,{image_b64}"

        # 调用 Vision API
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": context_prompt},
                            {"type": "image_url", "image_url": {"url": image_url}}
                        ]
                    }
                ],
                max_tokens=2000,
                temperature=0.3
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"[ERROR] Vision API 调用失败: {e}")
            return f"[图片描述生成失败: {e}]"

    def _build_context_prompt(self, preceding_context: str, section_title: str) -> str:
        """构建上下文提示"""
        # 限制上下文长度
        max_context_len = 2000
        if len(preceding_context) > max_context_len:
            preceding_context = "..." + preceding_context[-(max_context_len-3):]

        prompt = f"""这是章节 "{section_title}" 的一张配图。

截至图片出现前，上下文内容为:
---
{preceding_context}
---

请基于上下文，将这张图片的内容"翻译"为 Markdown 文本。
你的输出将直接接在上文之后，形成流畅的阅读体验。"""

        return prompt


# ========== 便捷函数 ==========

def translate_image(
    image_bytes: bytes,
    context: str,
    section_title: str = ""
) -> str:
    """
    一站式函数: 翻译单张图片为 Markdown。
    """
    translator = ImageTranslator()
    return translator.translate(image_bytes, context, section_title)


if __name__ == "__main__":
    # 测试脚本 - 需要提供测试图片
    print("=== Vision Agent 测试 ===")
    print("使用方法: python vision_agent.py <image_path>")
    print()

    if len(sys.argv) > 1:
        img_path = Path(sys.argv[1])
        if img_path.exists():
            with open(img_path, "rb") as f:
                img_bytes = f.read()

            test_context = """
2.2.2 Compiling BHy2CLI

- Move to BHy2CLI folder, open Command Prompt from here.
- For PC mode: execute build.bat script if on Windows. Example:
"""
            result = translate_image(img_bytes, test_context, "2.2.2 Compiling BHy2CLI")
            print("=== 翻译结果 ===")
            print(result)
        else:
            print(f"[ERROR] 图片不存在: {img_path}")
    else:
        print("[INFO] 未提供图片路径，跳过测试")
