# LaTeX MCP Server

An **MCP (Model Context Protocol) server** exposing utilities for working with a LaTeX thesis project.

It demonstrates how to implement MCP tools in **both Python and TypeScript**. The Python process is the MCP server; selected tools are delegated to a small Node/TypeScript module via a bridge.

## Features

- List `.tex` files in your workspace
- Read file content (with size cap)
- Compile LaTeX (pdflatex) with minimal args
- Extract citation keys from a `.tex` file
- TypeScript-provided tools:
  - Summarize a block of text heuristically
  - Suggest a BibTeX key given a title & authors

## Install (with `uv`)

From the repository root:

```bash
cd latex-mcp-server
uv tool install -e .
```
or
```
uv tool install -e ./latex-mcp-server
```

This will make the console script `latex-mcp-server` available on your PATH.

> If you prefer a one-off run without installing as a tool:
>
> ```bash
> uv run latex-mcp-server
> ```

## MCP Configuration Snippet

Add to your `mcp.json` (VS Code / Claude Desktop user settings):

```jsonc
"latex-mcp-server": {
  "command": "uv",
  "args": ["tool", "run", "latex-mcp-server", "--workspace", "ABSOLUTE_PATH_TO_YOUR_THESIS_ROOT"]
}
```

If you omit `--workspace`, the server will infer the current working directory.

## TypeScript Bridge

The TypeScript sources live in `ts_functions/src`. Their compiled JavaScript output is vendored into the Python package under `latex_mcp_server/ts_dist` so users do **not** need `npm` or `tsc` just to run the server. To modify or add TS functions:

```bash
cd latex-mcp-server/ts_functions
npm install
npm run build
```

Then copy (or allow the provided helper script to sync) the `dist/` contents into `latex_mcp_server/ts_dist/`.

## Adding New Python Tools

Add functions in `latex_mcp_server/functions/latex_ops.py` (or new modules) and register them in `server.py` inside `register_python_tools`.

## Adding New TS Tools

1. Create a new file in `ts_functions/src/functions/` exporting a function.
2. Add it to the export map in `ts_functions/src/index.ts`.
3. Rebuild and sync dist output.
4. Register a Python wrapper in `server.py` using `bridge.register_ts_tool`.

## Protocol Notes

This server follows the MCP JSON-RPC message patterns. If the `mcp` Python package updates its APIs, adjust imports accordingly.

## License

MIT
