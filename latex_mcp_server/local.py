"""Local TeX Live tools for trusted projects; compilation is not a sandbox."""
import argparse
import os
import re
import signal
import subprocess
import tempfile
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from pypdf import PdfReader


class Workspace:
    def __init__(self, root, tex_bin='/opt/texlive/bin/x86_64-linux'):
        self.root = Path(root).resolve(strict=True)
        self.tex_bin = Path(tex_bin).resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError('Workspace must be a directory')

    def path(self, relative):
        if not relative or Path(relative).is_absolute():
            raise ValueError('Use a relative workspace path')
        p = (self.root / relative).resolve()
        if not p.is_relative_to(self.root):
            raise ValueError('Path escapes workspace')
        return p

    def executable(self, name):
        p = self.tex_bin / name
        if not p.is_file() or not os.access(p, os.X_OK):
            raise ValueError(f'TeX Live executable missing: {name}')
        return str(p)

    def environment(self):
        env = os.environ.copy()
        env['PATH'] = str(self.tex_bin) + os.pathsep + env.get('PATH', '')
        cache = self.path('.latex-mcp-build/texmf-cache')
        cache.mkdir(parents=True, exist_ok=True)
        env.update(openin_any='p', openout_any='p', shell_escape='f', TEXMFVAR=str(cache), TEXMFCACHE=str(cache))
        return env

    def compile(self, main_tex='main.tex', engine='xelatex', timeout=120):
        if engine not in ('pdflatex', 'xelatex', 'lualatex'):
            raise ValueError('Unsupported engine')
        if type(timeout) is not int or not 1 <= timeout <= 600:
            raise ValueError('timeout must be 1..600 seconds')
        source = self.path(main_tex)
        if source.suffix != '.tex' or not source.is_file():
            raise ValueError('Expected an existing .tex file')
        rel = source.relative_to(self.root)
        output = self.path(str(Path('.latex-mcp-build') / rel.with_suffix('')))
        output.mkdir(parents=True, exist_ok=True)
        option = {'pdflatex': '-pdf', 'xelatex': '-xelatex', 'lualatex': '-lualatex'}[engine]
        cmd = [self.executable('latexmk'), '-norc', option, '-no-shell-escape',
               '-interaction=nonstopmode', '-halt-on-error', '-file-line-error',
               '-recorder', '-outdir=' + os.path.relpath(output, source.parent), './' + source.name]
        timed_out = False
        with tempfile.TemporaryFile() as capture:
            proc = subprocess.Popen(cmd, cwd=source.parent, env=self.environment(),
                                    stdout=capture, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
            capture.seek(0, 2)
            size = capture.tell()
            capture.seek(max(0, size - 24000))
            tail = capture.read().decode('utf-8', errors='replace')
        pdf = output / (source.stem + '.pdf')
        log_file = output / (source.stem + '.log')
        diagnostic_text = tail
        if not timed_out and log_file.is_file():
            with log_file.open('rb') as stream:
                stream.seek(0, 2)
                stream.seek(max(0, stream.tell() - 100000))
                diagnostic_text = stream.read().decode('utf-8', errors='replace')
        diagnostics = [line for line in diagnostic_text.splitlines() if re.search(
            r'(^!|:[0-9]+:|Warning|Error|Overfull|Underfull|undefined|not found)', line)]
        return dict(ok=proc.returncode == 0 and not timed_out and pdf.is_file(),
                    timed_out=timed_out, returncode=proc.returncode, engine=engine,
                    pdf=str(pdf.relative_to(self.root)) if pdf.is_file() else None,
                    diagnostics=diagnostics[-100:], log_tail=tail, log_truncated=size > 24000)


def create_server(workspace):
    mcp = FastMCP('Local TeX Live LaTeX', instructions='Compile trusted local LaTeX projects. Paths are relative to the configured workspace. No network downloads or arbitrary shell tools.')

    @mcp.tool()
    def texlive_info() -> dict:
        """Report local TeX Live executables and version."""
        tools = {}
        for name in ('pdflatex', 'xelatex', 'lualatex', 'latexmk', 'bibtex', 'biber', 'kpsewhich'):
            try:
                tools[name] = workspace.executable(name)
            except ValueError:
                tools[name] = None
        version = subprocess.run([workspace.executable('pdflatex'), '--version'],
                                 capture_output=True, text=True, timeout=10).stdout.splitlines()[0]
        return dict(workspace=str(workspace.root), version=version, tools=tools)

    @mcp.tool()
    def list_tex_files() -> dict:
        """List up to 1000 TeX files, excluding generated output."""
        files = []
        for p in workspace.root.rglob('*.tex'):
            if '.latex-mcp-build' in p.parts or '.git' in p.parts:
                continue
            if p.resolve().is_relative_to(workspace.root) and p.is_file():
                files.append(str(p.relative_to(workspace.root)))
                if len(files) == 1000:
                    return dict(files=sorted(files), truncated=True)
        return dict(files=sorted(files), truncated=False)

    @mcp.tool()
    def read_file(path: str, max_bytes: int = 50000) -> dict:
        """Read bounded UTF-8 text inside the workspace; no writes."""
        if not 1 <= max_bytes <= 1000000:
            raise ValueError('max_bytes must be 1..1000000')
        p = workspace.path(path)
        with p.open('rb') as stream:
            data = stream.read(max_bytes + 1)
        return dict(path=path, text=data[:max_bytes].decode('utf-8', errors='replace'), truncated=len(data) > max_bytes)

    @mcp.tool()
    def compile_latex(main_tex: str = 'main.tex', engine: str = 'xelatex', timeout: int = 120) -> dict:
        """Compile with latexmk, resolving bibliography and references. Writes .latex-mcp-build. Engines: pdflatex, xelatex, lualatex. Shell escape and rc scripts disabled."""
        return workspace.compile(main_tex, engine, timeout)

    @mcp.tool()
    def check_package(name: str) -> dict:
        """Locate a local .sty or .cls package; never install packages."""
        if not re.fullmatch(r'[A-Za-z0-9_-]+\.(sty|cls)', name):
            raise ValueError('Expected package.sty or class.cls')
        result = subprocess.run([workspace.executable('kpsewhich'), name],
                                capture_output=True, text=True, timeout=10, env=workspace.environment())
        return dict(name=name, found=result.returncode == 0, path=result.stdout.strip())

    @mcp.tool()
    def read_pdf(path: str, max_pages: int = 5, max_chars: int = 50000) -> dict:
        """Extract PDF text without OCR/network. Missing or invalid files raise errors."""
        if not 1 <= max_pages <= 100 or not 1 <= max_chars <= 200000:
            raise ValueError('Limits: 1..100 pages; 1..200000 characters')
        p = workspace.path(path)
        if p.stat().st_size > 50 * 1024 * 1024:
            raise ValueError('PDF exceeds 50 MiB')
        with p.open('rb') as stream:
            if stream.read(5) != b'%PDF-':
                raise ValueError('Not a PDF')
            stream.seek(0)
            reader = PdfReader(stream)
            total = len(reader.pages)
            pieces, extracted, length = [], 0, 0
            for page in reader.pages[:max_pages]:
                text = page.extract_text() or ''
                pieces.append(text)
                extracted += 1
                length += len(text)
                if length > max_chars:
                    break
            text = '\n\n'.join(pieces)
        return dict(path=path, text=text[:max_chars], pages=total, extracted_pages=extracted,
                    truncated=extracted < total or len(text) > max_chars)

    return mcp


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--tex-bin', default='/opt/texlive/bin/x86_64-linux')
    args = parser.parse_args()
    create_server(Workspace(args.workspace, args.tex_bin)).run(transport='stdio')


if __name__ == '__main__':
    main()
