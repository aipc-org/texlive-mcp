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
 - Read PDFs directly or by citation key (`read_pdf_from_citation`) which looks up `resources/cited_papers/index.json` and auto-downloads if needed

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

### Windows example

On Windows (PowerShell / Bash), if your thesis root is at `C:\Users\User\projects\Thesis`, use:

```jsonc
"latex-mcp-server": {
  "command": "uv",
  "args": [
    "tool", "run", "latex-mcp-server",
    "--workspace", "C:/Users/User/projects/Thesis"
  ]
}
```

Forward slashes are fine; they avoid the need to escape backslashes. Be sure to replace the placeholder `ABSOLUTE_PATH_TO_YOUR_THESIS_ROOT` — leaving a placeholder like `WORKSPACE_FOLDER_PATH` will cause the runtime error:

```
Workspace does not exist: C:\Users\User\WORKSPACE_FOLDER_PATH\Thesis
```

### Alternative: Install once, then call directly

After running:

```bash
cd latex-mcp-server
uv tool install -e .
```

You can simplify the config to:

```jsonc
"latex-mcp-server": {
  "command": "latex-mcp-server",
  "args": ["--workspace", "C:/Users/User/projects/Thesis"]
}
```

### Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `No solution found when resolving tool dependencies` | The tool name `latex-mcp-server` isn’t published on PyPI and `uv` tried to resolve it as a dependency (often happens if you used a config field like `requires` or didn’t install locally) | Run `uv tool install -e ./latex-mcp-server` from repo root, then update your `mcp.json` to invoke the installed script directly |
| `Workspace does not exist: C:\\Users\\...WORKSPACE_FOLDER_PATH...` | Placeholder path left unchanged | Replace with the real absolute path |
| `TypeScript runtime unavailable` in tool results | Node.js not installed (only needed for TS bridge tools) | Install Node.js 18+ or ignore if you don’t need TS tools |

If you change TypeScript sources, rebuild and re-vendor (`npm run build`) before restarting the server.

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

### Citation-Aware PDF Reading

When a user asks about a paper (e.g. “Explain how \cite{smith2023model} differs from …”), the agent should:

1. Parse citation key(s) from the request.
2. Call `read_pdf_from_citation` for each key (fetches / downloads PDF and extracts text snippet + metadata).
3. Ground its answer on the extracted text (and optionally call `summarize_text` for a concise summary).
4. Indicate if extraction was truncated (check the `truncated` flag) and avoid over-claiming beyond available pages/characters.

The `read_pdf_from_citation` tool returns the same schema as `read_pdf` plus `citation_key` so multi-citation responses can attribute snippets correctly.

## Auto-Updating `index.json` (Chosen Method: VS Code Tasks)

This project is configured to refresh `resources/cited_papers/index.json` before each LaTeX build using VS Code tasks (method #3 from the suggested approaches).

Added file: `.vscode/tasks.json` with three tasks:

- `update-index`: Runs a short Python one-liner invoking `extract_bibliography` on `src/references.bib`.
- `latex-build`: Invokes `latexmk -pdf` on `main.tex`.
- `build+index`: Sequentially runs `update-index` then `latex-build`.

### How to Use
1. In VS Code, open the command palette and run “Tasks: Run Task”.
2. Choose `build+index` (recommend marking it as the default build task when prompted).
3. The BibTeX index will regenerate first; then LaTeX compilation proceeds.

If LaTeX Workshop cannot import the package (ModuleNotFoundError), a helper script `latex-mcp-server/update_index.py` is provided. The workspace settings have been updated to call:
```
python latex-mcp-server/update_index.py
```
so that a local editable install is not strictly required.

### Make It the Default Build
When prompted by VS Code after first run, accept setting `build+index` as the default. You can also add to your workspace settings:
```jsonc
// .vscode/settings.json (optional)
{
  "latex-workshop.latex.recipe.default": "build+index"
}
```

### Why This Approach
* No background watcher process.
* Deterministic: index refresh tied explicitly to build command.
* Minimal overhead (BibTeX parsing is fast relative to PDF compilation).

If you later need an alternative (e.g., Makefile or on-demand freshness check), you can still layer it on; the tasks approach is non-invasive.

## Adding New TS Tools

1. Create a new file in `ts_functions/src/functions/` exporting a function.
2. Add it to the export map in `ts_functions/src/index.ts`.
3. Rebuild and sync dist output.
4. Register a Python wrapper in `server.py` using `bridge.register_ts_tool`.

## Protocol Notes

This server follows the MCP JSON-RPC message patterns. If the `mcp` Python package updates its APIs, adjust imports accordingly.

## License

MIT
