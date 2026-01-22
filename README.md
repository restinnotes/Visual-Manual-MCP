# Visual-Manual-MCP 👁️📚

> **Photographic Memory for your AI Agents.**

SimpleMem (Visual-Manual-MCP) is a **Multimodal Native RAG** system designed to turn complex technical manuals (chip datasheets, circuit diagrams, machinery guides) into a searchable, visual knowledge base via the **Model Context Protocol (MCP)**.

## 🚀 Why Visual-Manual-MCP?

Traditional RAG systems "bottleneck" image data by converting it into lossy text descriptions. This project takes a **"Multimodal Native"** approach:

1.  **Zero-Loss Ingestion**: Every page is captured as a high-resolution snapshot.
2.  **Multimodal Embedding**: Uses Qwen3-VL-style embeddings to link pixels with technical terminology in a unified vector space.
3.  **VLM-Ready Retrieval**: Instead of just sending text, the MCP server provides the **exact visual page** (PNG) to your agent, allowing models like GPT-4o or Claude 3.5 Sonnet to "see" the blueprints directly.

---

## 🛠️ Quick Start

### 1. Ingest a Manual
Convert your PDF into a multimodal knowledge stream:
```bash
python src/multimodal_ingest.py "path/to/your/manual.pdf"
python src/inject_multimodal.py "multimodal_data/manual_manifest.json"
```

### 2. Connect to Agent
Add this to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "visual-manual-mcp": {
      "command": "python",
      "args": ["/path/to/Visual-Manual-MCP/src/mcp_server.py"]
    }
  }
}
```

---

## 📂 Project Structure
- `src/multimodal_ingest.py`: High-res page renderer & text extractor.
- `src/inject_multimodal.py`: Multimodal vector injection (LanceDB).
- `src/mcp_server.py`: MCP Tool provider (`search_technical_manual`).
- `src/query_multimodal.py`: CLI testing script.

## 🛡️ Requirements
- `PyMuPDF` (fitz)
- `lancedb`
- `sentence-transformers`
- `openai` (for VLM capabilities)

## 📄 License
MIT
