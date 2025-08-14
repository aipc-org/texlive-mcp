import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

from .functions import latex_ops
from .ts_bridge import TypeScriptBridge


def send(message: Dict[str, Any]):
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def receive() -> Dict[str, Any]:
    line = sys.stdin.readline()
    if not line:
        raise EOFError
    return json.loads(line)


class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, Any] = {}

    def register(self, name: str, func):
        self.tools[name] = func

    def call(self, name: str, params: Dict[str, Any]):
        if name not in self.tools:
            raise KeyError(f"Unknown tool: {name}")
        return self.tools[name](params)


def build_registry(workspace: Path) -> ToolRegistry:
    reg = ToolRegistry()

    reg.register(
        "list_tex_files",
        lambda _: {"files": latex_ops.list_tex_files(workspace)},
    )
    reg.register(
        "read_file",
        lambda p: latex_ops.read_file(workspace, p["path"], p.get("max_bytes", 50_000)),
    )
    reg.register(
        "extract_citations",
        lambda p: {"citations": latex_ops.extract_citations(workspace, p["path"])}
        ,
    )
    reg.register(
        "compile_latex",
        lambda p: latex_ops.compile_latex(
            workspace, p.get("main_tex", "main.tex"), p.get("passes", 1)
        ),
    )

    ts_dist = Path(__file__).parent / "ts_dist"
    bridge = TypeScriptBridge(ts_dist)
    bridge.register_ts_tool("summarize_text", "summarizeText")
    bridge.register_ts_tool("suggest_bib_key", "suggestBibKey")

    def _maybe(call_name: str):
        wrapper = bridge.make_wrapper(call_name)

        def _runner(params: Dict[str, Any]):
            if not bridge.available():
                return {"ok": False, "error": "TypeScript runtime unavailable (install Node.js)"}
            try:
                result = wrapper(params)
                return {"ok": True, "result": result}
            except Exception as e:  # pragma: no cover
                return {"ok": False, "error": str(e)}

        return _runner

    reg.register("summarize_text", _maybe("summarize_text"))
    reg.register("suggest_bib_key", _maybe("suggest_bib_key"))

    return reg


def event_loop(registry: ToolRegistry):
    while True:
        try:
            msg = receive()
        except EOFError:
            break
        except Exception as e:
            send({"jsonrpc": "2.0", "error": {"code": -32700, "message": str(e)}})
            continue
        if msg.get("method") == "ping":
            send({"jsonrpc": "2.0", "id": msg.get("id"), "result": {"pong": True}})
            continue
        if msg.get("method") == "listTools":
            send(
                {
                    "jsonrpc": "2.0",
                    "id": msg.get("id"),
                    "result": {"tools": sorted(list(registry.tools.keys()))},
                }
            )
            continue
        if msg.get("method") == "callTool":
            params = msg.get("params", {})
            tool = params.get("name")
            tool_params = params.get("arguments", {})
            try:
                result = registry.call(tool, tool_params)
                send({"jsonrpc": "2.0", "id": msg.get("id"), "result": result})
            except Exception as e:
                send(
                    {
                        "jsonrpc": "2.0",
                        "id": msg.get("id"),
                        "error": {"code": -32603, "message": str(e)},
                    }
                )
            continue
        send(
            {
                "jsonrpc": "2.0",
                "id": msg.get("id"),
                "error": {"code": -32601, "message": "Method not found"},
            }
        )


def main(argv: Any = None):
    parser = argparse.ArgumentParser(description="LaTeX MCP Server")
    parser.add_argument("--workspace", type=str, default=os.getcwd(), help="Path to LaTeX root")
    args = parser.parse_args(argv)
    workspace = Path(args.workspace).resolve()
    if not workspace.exists():
        print(f"Workspace does not exist: {workspace}", file=sys.stderr)
        sys.exit(1)
    registry = build_registry(workspace)
    event_loop(registry)

if __name__ == "__main__":  # pragma: no cover
    main()
