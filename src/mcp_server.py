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
# sys.path.insert(0, str(Path(__file__).parent.parent / "simplified_mem")) # REMOVED

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
        # Minimal MCP protocol implementation over Stdio

        # Robust Input Reading for Windows (Threads instead of async pipes)
        # This avoids WinError 6 (Proactor) and NotImplementedError (Selector)
        loop = asyncio.get_running_loop()
        reader = asyncio.StreamReader()

        def reading_thread():
            """Reads stdin in a separate thread and feeds the async reader"""
            try:
                while True:
                    # buffer.readline gives raw bytes, safer than text wrapper
                    line = sys.stdin.buffer.readline()
                    if not line:
                        break
                    loop.call_soon_threadsafe(reader.feed_data, line)
                loop.call_soon_threadsafe(reader.feed_eof)
            except Exception as e:
                print(f"[TCP Error] Reading thread failed: {e}", file=sys.stderr)
                loop.call_soon_threadsafe(reader.feed_eof)

        # Start input thread
        import threading
        t = threading.Thread(target=reading_thread, daemon=True)
        t.start()

        # Setup Output
        # Use stdout directly or via wrapper.
        # For simplicity and robustness, we just write to sys.stdout.buffer

        async for line in reader:
            try:
                 # line is bytes
                msg_str = line.decode('utf-8').strip()
                if not msg_str: continue

                msg = json.loads(msg_str)

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
                    self._send_json(response)

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
                    self._send_json(response)

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

                        response = {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "result": {
                                "content": content
                            }
                        }
                        self._send_json(response)
                    else:
                        # Unknown tool
                         self._send_json({
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "error": {"code": -32601, "message": "Method not found"}
                        })

                # Handle Ping/Other
                elif msg.get("method") == "ping":
                     self._send_json({"jsonrpc": "2.0", "id": msg["id"], "result": {}})

            except Exception as e:
                # Log error to stderr (don't corrupt stdout JSON-RPC)
                print(f"[MCP Error] {e}", file=sys.stderr)

    def _send_json(self, data: dict):
        """Write JSON response to stdout safely"""
        try:
            json_str = json.dumps(data)
            # Write bytes to stdout buffer to avoid encoding issues
            sys.stdout.buffer.write(json_str.encode('utf-8') + b"\n")
            sys.stdout.buffer.flush()
        except Exception as e:
            print(f"[MCP Write Error] {e}", file=sys.stderr)

if __name__ == "__main__":
    # Remove previous Windows-specific loop policy fix as we are now using threads
    # Debug: Print absolute path of DB
    print(f"[INFO] Using LanceDB path: {os.path.abspath(global_config.LANCEDB_PATH)}", file=sys.stderr)

    server = SimpleMemMCPServer()
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        pass
