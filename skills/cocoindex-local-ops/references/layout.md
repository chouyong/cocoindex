# CocoIndex Local Ops 目录与路径参考

## 1. 仓库根目录

`D:\knowledgeBase\cocoindex\cocoindex_repo`

关键文件：

- `AGENTS.md`
- `README.md`
- `pyproject.toml`
- `CLAUDE.md`
- `操作手册说明文档.md`

## 2. 项目级 skill 目录

`D:\knowledgeBase\cocoindex\cocoindex_repo\skills\cocoindex-local-ops`

当前结构：

- `SKILL.md`
- `agents/openai.yaml`
- `references/commands.md`
- `references/layout.md`
- `references/troubleshooting.md`

## 3. 运行验证相关目录

Quickstart 验证项目：

`D:\knowledgeBase\cocoindex\cocoindex_repo\quickstart_demo`

官方示例目录：

`D:\knowledgeBase\cocoindex\cocoindex_repo\examples\files_transform`

示例输入目录：

`D:\knowledgeBase\cocoindex\cocoindex_repo\examples\files_transform\data`

示例输出目录：

`D:\knowledgeBase\cocoindex\cocoindex_repo\examples\files_transform\output_html`

## 4. 日志路径

后台 live 日志通常放在：

- `D:\knowledgeBase\cocoindex\cocoindex_repo\examples\files_transform\cocoindex-live.stdout.log`
- `D:\knowledgeBase\cocoindex\cocoindex_repo\examples\files_transform\cocoindex-live.stderr.log`

## 5. 可执行入口

当前已验证的本机 CLI 可执行路径：

`D:\miniconda3\Scripts\cocoindex.exe`

说明：

- 这是当前机器上的实际路径
- 如果 Python 环境切换，路径可能变化
- 重新确认时可使用 `Get-Command cocoindex`
