# SimpleMem 集成终极目标与实施路径 (Master Strategy)

## 🎯 核心目标 (Final Objective)
为 AI Agent (Antigravity) 打造一个具备 **"防幻觉" (Hallucination-Proof)** 且 **"深度理解" (Deep Understanding)** 的技术文档大脑。

1.  **绝对防幻觉**: Agent 回答必须基于记忆库置信度。若知识库无信息，诚实回复“不知道”。
2.  **强制引用来源**: 每个答案必须关联原始文件 (如 `BHy2CLI_User_Guide.pdf` Page 13)，确保信息可追溯。
3.  **高精度知识管理**: 将非结构化手册转化为 **"视觉图谱原子化"** 知识网，确保复杂命令与关联约束能被完整提取。

---

## 🏗️ SimpleMem 核心原理与工作流 (The Seamless Pipeline)

SimpleMem 采用 **"视觉-图谱-原子化" (Visual-Graph Atomization)** 的三阶段闭环架构。

### 阶段 1: 知识原子化 (MemoryBuilder)
> **任务**: 将非结构化文档转化为计算机可理解的“原子知识”和“逻辑关系”。

1.  **智能元分析 (Meta-Analysis)**:
    *   系统首先**通读**文档目录与摘要，理解文档类型（例如：CLI 手册 vs API 规范）。
    *   **动态生成**最适合该文档的提取策略（Prompt Strategy），指导后续步骤关注“命令参数”还是“函数签名”。
2.  **线性流式重组 (Stream Injection Pipeline) - [NEW]**:
    *   **PyMuPDF Extract**: 精确提取文本与实质性图片 (Text Overlap Check 过滤装饰/冗余图)。
    *   **Vision-to-Text**: 针对每张图片，注入从章节开头累积的**完整上下文**，调用 Vision LLM 生成嵌入式的 Markdown 描述或代码块。
    *   **Result**: 生成一份高精度的、图文完全融合的**线性 Markdown 流** (`Section_X.X.X.md`)。
3.  **深度原子化 (Deep Atomization)**:
    *   **Markdown Atomizer**: 读取上述 Markdown 流。
    *   **去指代**: 将模糊的 "它" 替换为具体的实体名 (e.g., "It supports -r" -> "BHy2CLI supports -r").
    *   **命题独立化**: 将复合句拆解为单条独立事实，确保每条知识都能独立检索。
4.  **关系提取 (Relation Extraction)**:
    *   LLM 主动抽取原子命题间的**工程逻辑**，构建知识图谱：
        *   `[命令: Reset] --互斥(CONFLICTS_WITH)--> [状态: Firmware Flashing]`
        *   `[命令: Upload] --依赖(REQUIRES)--> [接口: Host Interface]`

### 阶段 2: 向量化存储 (VectorStore)
> **任务**: 构建多维度的混合索引，为复杂检索做准备。

1.  **混合索引构建 (Hybrid Indexing)**:
    *   **向量层 (Vectors)**: 将原子命题通过 **Qwen Embedding** 转化为 1024 维向量，用于语义模糊匹配。
    *   **图谱层 (Graph Metadata)**: 将提取的关系三元组存储为结构化元数据，构建逻辑拓扑网。
    *   **摘要树 (RAPTOR Tree)**: 生成文档的层级摘要（章节级 -> 文档级），用于回答“整体架构”类宏观问题。
2.  **物理存储**: 所有数据存入 **LanceDB**，保证高性能查询。

### 阶段 3: 防幻觉检索 (Retrieval & Reasoning)
> **任务**: 针对复杂问题，通过混合遍历寻找完整答案链，并进行置信度核查。

**详细检索流程 (处理复杂命令的逻辑):**
*假设用户问: "如何安全地复位传感器？"*

1.  **查询分析 (Query Analysis)**:
    *   识别核心实体: `Reset` (动作), `Sensor` (对象).
    *   识别隐性意图: `Safely` -> 意味着用户关心**约束条件**或**潜在风险**。
2.  **混合召回 (Hybrid Recall)**:
    *   **语义检索 (Vector)**: 找到最相关的原子事实 -> *"Use `bhy2cli -r` to reset."*
    *   **宏观检索 (Tree)**: 检索 RAPTOR 摘要 -> *"System Control 章节描述了复位机制."*
3.  **图谱扩展遍历 (Graph Extension)** - *关键步骤*:
    *   系统以 `[Action: Reset]` 为起点，在图谱中进行**多跳遍历 (Multi-hop Traversal)**。
    *   发现关系: `Reset --CONFLICTS_WITH--> Firmware Flashing`。
    *   发现关系: `Reset --AFFECTS--> FIFO Buffer`。
    *   **结果**: 系统自动将 "Firmware Flashing" 和 "FIFO Buffer" 的相关知识也以此拉入上下文，即使原问题没提到它们。这确保了回答的**完整性**和**安全性**。
4.  **上下文组装与生成 (Synthesis)**:
    *   将所有召回信息（命令 + 冲突警告 + 影响范围）组装给 LLM。
    *   生成回答: *"使用 `bhy2cli -r` 进行复位。注意：请勿在固件烧录期间执行此操作（来源：User_Guide P13），否则可能导致冲突。复位后 FIFO 缓冲区将被清空。"*
5.  **防幻觉风控 (Confidence Check)**:
    *   最后检查：生成的回答是否每一句话都有检索到的证据支持？
    *   **Pass**: 输出回答。
    *   **Fail**: 拦截回答，输出“当前知识库不足以回答该问题”。

---

## 📅 实施完工路线图 (Roadmap)
1.  **架构升级**: 将 SimpleMem 摄取层改造为上述的 **Meta -> Visual -> Graph** 管道。
2.  **代码实现**: 依次完成 `DocumentMetaAnalyzer`, `VisionDocumentAgent`, `GraphRelationExtractor`。
3.  **全量重构**: 运行脚本，重新处理 BHy2 文档库。
4.  **端到端测试**: 验证上述“复位命令”的复杂检索链路是否通畅。
