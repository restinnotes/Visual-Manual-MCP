"""
SimpleMem MCP Server
Exposes the Multimodal RAG retrieval capabilities as an MCP tool.
"""

import sys
import os
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any

# Setup paths
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "simplified_mem"))

# Import RAG capability
from database.vector_store import VectorStore
from utils.embedding import EmbeddingModel
import lancedb
import config as global_config

# MCP Constants
MCP_PROTOCOL_VERSION = "2024-11-05"

class SimpleMemMCPServer:
    def __init__(self):
        self.db = lancedb.connect(global_config.LANCEDB_PATH)
        self.table_name = "multimodal_memory"
        if self.table_name in self.db.table_names():
            self.table = self.db.open_table(self.table_name)
        else:
            self.table = None
            print(f"[WARN] Table {self.table_name} not found in {global_config.LANCEDB_PATH}", file=sys.stderr)

        self.embedder = EmbeddingModel()

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Perform multimodal search"""
        if not self.table:
            return [{"error": "Database not initialized"}]

        query_vector = self.embedder.encode_query([query])[0]
        results = self.table.search(query_vector.tolist()).limit(top_k).to_list()

        matches = []
        for res in results:
            matches.append({
                "content": res["lossless_restatement"],
                "image_path": res["location"],
                "source": res["topic"],
                "section": res["section"],
                "score": 1.0 - res.get('_distance', 0.5) # Rough score approx
            })
        return matches

    async def run(self):
        """Standard IO Loop for MCP"""
        # This is a minimal raw implementation of MCP protocol over Stdio
        # In a real scenario, we'd use `mcp` python package if available
        # But this ensures zero-dependency compatibility for now if mcp is not installed

        # Handshake
        # Start read loop
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_running_loop().connect_read_pipe(lambda: protocol, sys.stdin)
        w_transport, w_protocol = await asyncio.get_running_loop().connect_write_pipe(asyncio.streams.FlowControlMixin, sys.stdout)
        writer = asyncio.StreamWriter(w_transport, w_protocol, reader, asyncio.get_running_loop())

        async for line in reader:
            try:
                msg = json.loads(line)
                if not msg: continue

                # Handle Initialize
                if msg.get("method") == "initialize":
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg["id"],
                        "result": {
                            "protocolVersion": MCP_PROTOCOL_VERSION,
                            "capabilities": {
                                "tools": {}
                            },
                            "serverInfo": {
                                "name": "SimpleMem Multimodal Server",
                                "version": "1.0"
                            }
                        }
                    }
                    writer.write(json.dumps(response).encode() + b"\n")
                    await writer.drain()

                # Handle Tools List
                elif msg.get("method") == "tools/list":
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg["id"],
                        "result": {
                            "tools": [
                                {
                                    "name": "search_technical_manual",
                                    "description": "Search the technical manual for wiring diagrams, specs, and instructions. Returns text content and paths to relevant original manual pages (images).",
                                    "inputSchema": {
                                        "type": "object",
                                        "properties": {
                                            "query": {
                                                "type": "string",
                                                "description": "The search query (e.g., 'how to wire port 3')"
                                            }
                                        },
                                        "required": ["query"]
                                    }
                                }
                            ]
                        }
                    }
                    writer.write(json.dumps(response).encode() + b"\n")
                    await writer.drain()

                # Handle Tool Call
                elif msg.get("method") == "tools/call":
                    req_id = msg["id"]
                    params = msg.get("params", {})
                    name = params.get("name")
                    args = params.get("arguments", {})

                    if name == "search_technical_manual":
                        query = args.get("query")
                        results = self.search(query)

                        # Format as MCP content
                        content = []
                        for item in results:
                            # Send text
                            text_block = f"Source: {item['source']} (Section {item['section']})\nContent: {item['content']}\nImage Ref: {item['image_path']}"
                            content.append({"type": "text", "text": text_block})

                            # Ideally we send image as integrated resource or embedded?
                            # For now, text reference as requested.
                            # "The specific ability to look at the picture is left to the web-end agent"
                            # So just returning the path is correct.

                        response = {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "result": {
                                "content": content
                            }
                        }
                        writer.write(json.dumps(response).encode() + b"\n")
                        await writer.drain()
                    else:
                        # Unknown tool
                         writer.write(json.dumps({
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "error": {"code": -32601, "message": "Method not found"}
                        }).encode() + b"\n")
                         await writer.drain()

                # Handle Ping/Other
                elif msg.get("method") == "ping":
                     writer.write(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": {}}).encode() + b"\n")
                     await writer.drain()

            except Exception as e:
                # Log error to stderr (don't corrupt stdout JSON-RPC)
                print(f"[MCP Error] {e}", file=sys.stderr)

if __name__ == "__main__":
    server = SimpleMemMCPServer()
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        pass
