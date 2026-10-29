# texlive-mcp

基于 [Yeok-c/latex-mcp-server](https://github.com/Yeok-c/latex-mcp-server) 的本地改造，基线提交 f791130edc4e38bada401ae4c688f121255225da。保留上游 MIT 许可。创作来自GPT

面向本机 Linux、TeX Live 2026：`/opt/texlive/bin/x86_64-linux`。使用官方 Python MCP SDK，通过 stdio 通信，Python >=3.10，不需要 Node.js。

## 功能

- `texlive_info`：检查 TeX Live 版本、编译器与参考文献工具路径。
- `list_tex_files`、`read_file`：列出和读取指定工作区内的文件。
- `compile_latex`：latexmk 自动处理多轮编译、交叉引用、BibTeX/Biber；支持 pdflatex、xelatex（默认）、lualatex；返回 PDF 路径、日志尾部和诊断。
- `check_package`：使用 kpsewhich 检查本地宏包，不自动安装。
- `read_pdf`：有页数、字符数、文件大小限制的文本提取；不存在或损坏的文件报错，不伪造内容，不支持 OCR。

## 启动

先按下方说明创建 `.venv` 并安装依赖，然后运行：

```bash
./.venv/bin/python -m latex_mcp_server.local --workspace /你的论文目录
```

启动后会等待 MCP 客户端的标准输入，这是正常行为。也可在任意目录直接调用项目内的 `run-local.sh`（带上述 workspace 参数）。

新机器安装：

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
```

`--tex-bin` 可覆盖 TeX Live 的 bin 路径。`mcp.example.json` 提供通用客户端示例，需替换论文目录。此项目没有自动修改全局 MCP 配置。

## 构建与限制

构建产物写入 `.latex-mcp-build/<入口相对路径去后缀>/`，TeX 字体缓存也在 `.latex-mcp-build/texmf-cache/`。子目录入口以入口所在目录为编译工作目录；其中的资源路径应相对此目录。使用编辑器打开返回的 PDF 路径即可预览。

读取工具拒绝绝对路径、`../` 越界和指向工作区外的符号链接。编译默认关闭 shell escape、latexmk rc 配置，设置 TeX 的受限文件读写策略，设置超时并杀死编译进程组。不提供任意命令、自动下载、源码改写或清理工具。

这些措施不等于操作系统沙箱：TeX、LuaTeX、参考文献处理器均为本地程序，**只编译可信项目**。依赖 shell escape 的 minted、外部绘图、定制 `.latexmkrc` 等流程不会按原方式工作。读取工具的路径校验不防御恶意并发替换符号链接；字体/PDF 解析仍可能消耗资源。错误编译目录里可能留有旧 PDF，必须以返回的 `ok` 为准。

## 测试

```bash
.venv/bin/python -m pytest tests/test_local.py -q
```

覆盖三种引擎、中文、BibTeX、Biber、错误诊断、超时、路径/符号链接越界、禁用 rc，以及官方 MCP 客户端握手和调用。上游试验版工具与测试已移除；其原始内容仍保留在 Git 历史。

## 上游来源

创作来自GPT

上游作者信息和 MIT 许可保留。

不带参数执行 `run-local.sh` 时，以调用时的当前目录作为论文工作区；也可以显式传入 `--workspace`。
