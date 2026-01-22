# SimpleMem - 多模态原生 RAG 知识库系统使用手册

## 📖 项目简介
SimpleMem 是一个基于 **Multimodal Native RAG** 架构的智能知识库。它专为处理**非结构化技术手册**（如芯片手册、电路图、工程规范）而设计。
与传统 RAG 不同，SimpleMem 不强行将图片转为有损的文本描述，而是直接索引 **“原始高页截图 + 文本上下文”**，支持 Agent "以图搜图" 和 "看图说话"。

---

## 🚀 核心功能
1.  **所见即所得 (WYSWYG) 摄取**: 每一页都被保存为高精度 PNG 快照，完美保留复杂电路图和不规则表格。
2.  **多模态嵌入 (Multimodal Embedding)**: 使用 Qwen3-VL 思想，将文本语义与视觉特征融合在同一个向量空间。
3.  **MCP 标准服务**: 提供标准的 Model Context Protocol 接口，任何支持 MCP 的 Agent (如 Claude Desktop, Cursor) 均可直接挂载使用。

---

## 🛠️ 操作指南：添加新文档

当你有了新的 PDF 手册（例如 `New_Manual.pdf`）需要入库时，请按以下两步操作：

### 第一步：多模态摄取 (Ingestion)
此步骤会将 PDF 拆解为“每页截图”和“每页文本”，并生成 Manifest 清单。

```powershell
# 语法: python src/multimodal_ingest.py <PDF路径>
python src/multimodal_ingest.py "docs/New_Manual.pdf"
```
*   **产出**: `multimodal_data/New_Manual_manifest.json` 以及对应的 `images/` 和 `texts/` 文件夹。

### 第二步：数据库注入 (Injection)
此步骤读取 Manifest，通过模拟多模态 Embedding 生成向量，并存入 LanceDB。

```powershell
# 语法: python src/inject_multimodal.py <Manifest路径>
python src/inject_multimodal.py "multimodal_data/New_Manual_manifest.json"
```
*   **结果**: 数据存入本地向量库，即刻可查。

---

## 🔌 MCP 接入指南

SimpleMem 通过 MCP 协议暴露搜索能力。你可以将其连接到任何支持 MCP 的客户端。

### 1. 启动服务器 (命令行模式)
如果你想在本地简单测试，可以直接运行：
```powershell
python src/mcp_server.py
```
*(注意：它运行在 Stdio 模式，启动后不会有打印输出，是给机器读的)*

### 2. 配置 Claude Desktop (推荐)
要让 Claude 直接使用该知识库，请编辑你的 Claude Desktop 配置文件：
*   **Windows 路径**: `%APPDATA%\Claude\claude_desktop_config.json`
*   **Mac 路径**: `~/Library/Application Support/Claude/claude_desktop_config.json`

在 `mcpServers` 字段中添加：

```json
{
  "mcpServers": {
    "simple-mem": {
      "command": "python",
      "args": [
        "D:\\SimpleMem\\src\\mcp_server.py"
      ]
    }
  }
}
```
*(请将 `D:\\SimpleMem` 替换为你的实际项目路径)*

重启 Claude Desktop 后，你会发现多了一个 🛠️ 工具图标。你可以直接问它：
> “查一下 BE-1125-6 手册里怎么接线？”

Claude 将会自动调用搜索工具，并能拿到你硬盘里的**原始电路图截图**进行回答。
