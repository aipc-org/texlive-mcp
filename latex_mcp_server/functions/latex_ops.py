import re
import subprocess
from pathlib import Path
from typing import List, Dict, Any


def list_tex_files(workspace: Path) -> List[str]:
    return [str(p.relative_to(workspace)) for p in workspace.rglob("*.tex")]


def read_file(workspace: Path, rel_path: str, max_bytes: int = 50_000) -> Dict[str, Any]:
    p = (workspace / rel_path).resolve()
    if not p.is_file():
        raise FileNotFoundError(rel_path)
    content = p.read_bytes()[:max_bytes].decode("utf-8", errors="replace")
    truncated = p.stat().st_size > max_bytes
    return {"path": rel_path, "truncated": truncated, "content": content}


def extract_citations(workspace: Path, rel_path: str) -> List[str]:
    p = workspace / rel_path
    if not p.is_file():
        raise FileNotFoundError(rel_path)
    text = p.read_text(encoding="utf-8", errors="replace")
    keys = set(re.findall(r"\\cite[t|p]?\{([^}]*)\}", text))
    expanded: List[str] = []
    for group in keys:
        for k in group.split(","):
            k = k.strip()
            if k:
                expanded.append(k)
    return sorted(set(expanded))


def compile_latex(workspace: Path, main_tex: str = "main.tex", passes: int = 1) -> Dict[str, Any]:
    tex_path = workspace / main_tex
    if not tex_path.exists():
        raise FileNotFoundError(main_tex)
    cmd = [
        "pdflatex",
        "-interaction=nonstopmode",
        "-halt-on-error",
        main_tex,
    ]
    logs = []
    for i in range(passes):
        proc = subprocess.run(cmd, cwd=workspace, capture_output=True, text=True)
        logs.append(proc.stdout + "\n" + proc.stderr)
        if proc.returncode != 0:
            return {"ok": False, "pass": i + 1, "log": logs[-1][-10_000:]}
    pdf_path = tex_path.with_suffix(".pdf")
    return {"ok": True, "pdf_exists": pdf_path.exists(), "log_tail": logs[-1][-5000:]}
