import asyncio
import sys
import pytest
from latex_mcp_server.local import Workspace
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_paths(tmp_path):
    w = Workspace(tmp_path)
    for path in ('../outside', '/etc/passwd'):
        with pytest.raises(ValueError):
            w.path(path)
    (tmp_path / 'link').symlink_to('/etc')
    with pytest.raises(ValueError):
        w.path('link/passwd')


@pytest.mark.parametrize('engine', ['pdflatex', 'xelatex', 'lualatex'])
def test_compile(tmp_path, engine):
    (tmp_path / 'main.tex').write_text(r'\documentclass{article}\begin{document}Hello\end{document}')
    result = Workspace(tmp_path).compile(engine=engine)
    assert result['ok'], result
    assert (tmp_path / result['pdf']).is_file()


def test_nested_and_error(tmp_path):
    (tmp_path / 'src').mkdir()
    (tmp_path / 'src/main.tex').write_text(r'\documentclass{article}\begin{document}\undefinedcommand\end{document}')
    result = Workspace(tmp_path).compile('src/main.tex')
    assert not result['ok']
    assert result['diagnostics']


def test_timeout(tmp_path):
    (tmp_path / 'main.tex').write_text(r'\documentclass{article}\begin{document}\loop\iftrue\repeat\end{document}')
    result = Workspace(tmp_path).compile(timeout=1)
    assert result['timed_out'] and not result['ok']


def test_mcp(tmp_path):
    async def run():
        params = StdioServerParameters(command=sys.executable, args=['-m', 'latex_mcp_server.local', '--workspace', str(tmp_path)])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = {t.name for t in (await session.list_tools()).tools}
                assert {'compile_latex', 'texlive_info', 'read_pdf'} <= names
                assert not (await session.call_tool('texlive_info', {})).isError
                assert (await session.call_tool('read_file', {'path': '../outside'})).isError
                assert (await session.call_tool('read_pdf', {'path': 'missing.pdf'})).isError
    asyncio.run(run())


def test_chinese(tmp_path):
    (tmp_path / 'main.tex').write_text(r'\documentclass[fontset=fandol]{ctexart}\begin{document}你好，中文。\end{document}')
    result = Workspace(tmp_path).compile()
    assert result['ok'], result


@pytest.mark.parametrize('backend', ['bibtex', 'biber'])
def test_bibliography(tmp_path, backend):
    (tmp_path / 'refs.bib').write_text('@book{test,author={Test Author},title={Test Book},year={2020},publisher={Test Press}}')
    if backend == 'bibtex':
        text = r'\documentclass{article}\begin{document}Citation\cite{test}.\bibliographystyle{plain}\bibliography{refs}\end{document}'
    else:
        text = r'\documentclass{article}\usepackage[backend=biber]{biblatex}\addbibresource{refs.bib}\begin{document}Citation\cite{test}.\printbibliography\end{document}'
    (tmp_path / 'main.tex').write_text(text)
    result = Workspace(tmp_path).compile()
    assert result['ok'], result
    bbl = tmp_path / '.latex-mcp-build/main/main.bbl'
    assert bbl.is_file() and 'Test' in bbl.read_text()


def test_rc_disabled(tmp_path):
    (tmp_path / '.latexmkrc').write_text('die "THIS MUST NOT RUN";')
    (tmp_path / 'main.tex').write_text(r'\documentclass{article}\begin{document}Hello\end{document}')
    assert Workspace(tmp_path).compile()['ok']


def test_output_symlink(tmp_path):
    (tmp_path / 'main.tex').write_text('test')
    (tmp_path / '.latex-mcp-build').symlink_to('/tmp')
    with pytest.raises(ValueError):
        Workspace(tmp_path).compile()
