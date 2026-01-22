# Phase 4 Implementation Plan: Markdown Atomization & Graph Injection

## 🎯 目标 (Objective)
将 Phase 3 生成的高质量、线性、图文融合的 Markdown 流 (`Stream Injection Output`)，转化为 SimpleMem 核心架构所需的 **原子化知识图谱 (Atomized Knowledge Graph)** 和 **RAPTOR 索引**。

---

## 🏗️ 核心组件设计 (Component Design)

### 1. Markdown Atomizer Agent (`MarkdownAtomizer`)
这是 Phase 4 的核心引擎，负责"读懂" Markdown 并进行深度处理。

*   **输入**: `knowledge_base/Section_X.X.X.md` (包含 Vision LLM 翻译的代码/图表描述)
*   **处理流程**:
    1.  **Semantic Chunking (语义切分)**:
        - 基于 Markdown 结构 (Header, List, Code Block) 进行物理切分。
        - *特殊处理*: 保持 Vision LLM 生成的 "Figure X" 描述块与其紧邻的上下文绑定，不被打断。
    2.  **Deep Atomization (深度原子化)**:
        - **Coreference Resolution (指代消解)**:
            - 识别代词 ("It", "The command", "This parameter")。
            - 替换为全称实体 (e.g., "BHy2CLI", "-p parameter")。
        - **Proposition Splitting (命题拆解)**:
            - 将复杂长句拆解为独立的原子事实 (Atomic Facts)。
    3.  **Relation Extraction (关系提取)**:
        - 扫描原子化文本，提取工程逻辑三元组。
        - **Schema**: `[Subject] --[Rel: REQUIRES/CONFLICTS_WITH/AFFECTS]-- [Object]`
        - *重点*: 从 CLI 命令描述中提取参数依赖关系。

### 2. Integrated Indexing (统一索引)

*   **LanceDB Storage Strategy**:
    - **Table**: `memory_entries`
    - **Fields**:
        - `content`: 原子化后的文本 (用于语义检索)。
        - `vector`: Embedding (Qwen)。
        - `section_id`: 章节 ID (e.g., "2.2.2")。
        - `source_file`: 源文件名。
        - `graph_triplets`: 提取的关系 (JSON) -> 供 GraphRAG 使用。
        - `raptor_level`: 0 (Atomic Fact) 或 1+ (Summary)。

*   **RAPTOR Tree Construction (Per-Section)**:
    - 仅对长章节构建局部 RAPTOR 树。
    - **Level 1 Summary**: 聚合该章节内的原子事实，生成高层摘要，用于回答宏观问题 (e.g., "Section 2.2.2 讲了什么？")。

---

## 📅 实施步骤 (Work Breakdown)

1.  **开发 `MarkdownAtomizer` (src/atomizer.py)**
    - 实现 Markdown 解析器。
    - 集成 LLM Prompt 进行指代消解和关系提取。
2.  **开发 `IngestionPipeline` (src/ingest_markdown.py)**
    - 串联: `Read MD -> Atomize -> Embed -> Store`。
3.  **验证 (Verification)**
    - 使用 Section 2.2.2 进行端到端测试。
    - 检查提取的关系三元组是否准确 (e.g., `build.bat` 依赖 `Windows`)。
