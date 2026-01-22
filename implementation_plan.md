# Implementation Plan - SimpleMem for Hallucination Prevention

The goal is to configure **SimpleMem** as an MCP server, ingest **BHy2CLI** documentation, and verify its ability to:
1.  Provide answers with source citations.
2.  Decline to answer "unknown" questions and suggest asking the user, instead of hallucinating.

## User Review Required
> [!IMPORTANT]
> **API Key Required**: SimpleMem requires an OpenAI-compatible API key (OpenAI/Qwen/Azure) to function. I will need to configure this in `config.py`. I will assume you can provide this or I will use a placeholder that you must update before running.

## Proposed Changes

### Configuration
#### [NEW] [config.py](file:///C:/Users/MECHREVO/.gemini/antigravity/brain/6c96d50a-54bf-4d85-819b-7bcaf9b1128a/simplified_mem/config.py)
- Create `config.py` from `config.py.example`.
- Set up model parameters (using `gpt-4.1-mini` or similar efficient model as default).

### Ingestion Script
#### [NEW] [ingest_bhy2.py](file:///C:/Users/MECHREVO/.gemini/antigravity/brain/6c96d50a-54bf-4d85-819b-7bcaf9b1128a/simplified_mem/ingest_bhy2.py)
- A script to read `bhy2cli_test_data` documentation.
- **Data Source**: Focus on `CHANGELOG.md` and `Compatibility.txt`. *Note: PDF parsing will be attempted if `pypdf` is available, otherwise text files will be used.*
- **Action**: Call `SimpleMemSystem.add_dialogue` (treating sentences as atomic facts) to populate the database.

### MCP Logic Adjustment
#### [MODIFY] [simplified_mem/MCP/server.py](file:///C:/Users/MECHREVO/.gemini/antigravity/brain/6c96d50a-54bf-4d85-819b-7bcaf9b1128a/simplified_mem/MCP/server.py)
- (Or `main.py` depending on where the logic resides).
- **Goal**: Modify the retrieval/query response.
- **Logic**:
    - Check the confidence score returned by SimpleMem.
    - If `confidence < THRESHOLD` (e.g., "medium" or "low"), overwrite the answer to: "I do not have enough information to answer this. Please ask the user for more details." to strictly prevent hallucination.
    - Ensure citations (source file names) are included in the output.

## Verification Plan

### Automated Tests
- **Ingestion Test**: Run `python ingest_bhy2.py` and verify no errors.
- **Query Test (Known)**: Query "What is BHy2CLI?" and expect a correct answer with citation.
- **Query Test (Unknown)**: Query "What is the capital of Mars?" (or irrelevant question) and expect the "Ask User" fallback.

### Manual Verification
- I will run the queries via a test script `test_mcp_logic.py` that simulates an MCP client request and prints the response.
