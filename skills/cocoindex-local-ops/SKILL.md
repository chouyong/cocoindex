---
name: cocoindex-local-ops
description: 当任务涉及本地 CocoIndex 仓库的下载、安装、CLI 验证、示例运行、live 模式启动、日志检查、进程停止或操作记录维护时使用。适用于 D:\knowledgeBase\cocoindex\cocoindex_repo 这个项目工作区，尤其适合区分“库/CLI 项目”与“传统 Web 服务项目”，避免错误寻找 serve/server 入口。
---

# CocoIndex Local Ops

用于本地仓库 `D:\knowledgeBase\cocoindex\cocoindex_repo` 的运维式操作，而不是泛化的 CocoIndex 编程指导。

## 适用场景

在以下任务触发时使用本 skill：

- 克隆或更新本仓库
- 安装本地开发版本
- 验证 `cocoindex` CLI 是否可用
- 启动或重启 `quickstart_demo`、`examples/files_transform` 等示例
- 以 `--live` 模式常驻运行某个示例 App
- 查询日志、输出目录、进程 PID
- 停止后台 `cocoindex` 进程
- 检查或复用本机 `Ollama` 做本地 embedding
- 把本地操作结果写回 `AGENTS.md` 或中文操作手册

## 核心判断

先判断任务目标：

1. 如果目标是“开发 CocoIndex 框架代码”，优先阅读现有代码和对应示例。
2. 如果目标是“运行一个 App 或示例”，优先走 CLI。
3. 不要默认把本项目当成 HTTP 服务项目。

当前已知结论：

- 根 CLI 常见命令为 `init`、`ls`、`show`、`update`、`drop`
- 当前仓库根入口未提供 `serve` 或 `server` 子命令
- “启动服务”在本项目里通常指 `cocoindex update --live`

## 标准流程

### 1. 安装

在仓库根目录执行：

```powershell
cd D:\knowledgeBase\cocoindex\cocoindex_repo
pip install -e .
```

安装后先验证：

```powershell
cocoindex --version
cocoindex --help
```

### 2. 快速验证

最小验证路径：

```powershell
cd D:\knowledgeBase\cocoindex\cocoindex_repo
cocoindex init quickstart_demo --dir quickstart_demo
cd .\quickstart_demo
cocoindex update .\main.py
```

### 3. 示例运行

优先使用无需外部云服务的示例：

`examples/files_transform`

运行前检查示例自己的 `pyproject.toml` 是否有额外依赖。该示例已知可能需要：

```powershell
pip install "markdown-it-py[linkify,plugins]"
```

运行：

```powershell
cd D:\knowledgeBase\cocoindex\cocoindex_repo\examples\files_transform
cocoindex update .\main.py
```

### 4. Live 模式

需要常驻监听时：

```powershell
cocoindex update .\main.py --live
```

如果要后台运行，可记录：

- 工作目录
- 启动命令
- PID
- stdout/stderr 日志文件路径

### 5. 本机 Ollama 复用

如果任务涉及本地 embedding、LiteLLM 联调、向量化示例或“用本地模型跑一下”，先复用本机已经验证通过的 `Ollama` 环境，不要默认重装。

当前固定约定：

- `ollama.exe` 实际位置：`D:\knowledgeBase\Ollama\ollama.exe`
- 模型与数据目录：`D:\knowledgeBase\.ollama`
- 日志与状态目录：`D:\knowledgeBase\OllamaLocal`
- 本地接口：`http://127.0.0.1:11434`
- 已验证模型：`nomic-embed-text:latest`

最小检查命令：

```powershell
ollama --version
ollama list
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:11434/api/tags
```

如需补 embedding 模型：

```powershell
ollama pull nomic-embed-text
```

当前仓库里，优先用于本地 Ollama 联调的最小示例是：

- `examples/text_embedding_local_ollama`

它的特点是：

- 输入本地 Markdown
- 输出本地 JSON
- 支持本地相似度查询
- 支持交互式多轮查询
- 支持可配置 Top K
- 支持多个 Markdown 文件共同检索
- 支持按文件名过滤结果
- 支持导出 Markdown 报告
- 支持导出静态 HTML 查询报告页
- 支持本地小型 Web UI
- 支持在 Web UI 里直接下载当前结果为 Markdown / HTML
- 支持在 Web UI 里按已索引文件名下拉候选过滤
- 支持点击结果卡片里的文件名标签后自动套用过滤
- 支持下载文件名自动带 query 和时间戳
- 支持显示当前过滤结果数徽标
- 支持点击过滤徽标进入全量结果对比视图
- 支持高亮片段预览
- 不依赖 Postgres 或 Qdrant
- 适合作为“先证明确实能调到本地 Ollama”的第一入口

最小运行命令：

```powershell
cd D:\knowledgeBase\cocoindex\cocoindex_repo\examples\text_embedding_local_ollama
pip install litellm
cocoindex update .\main.py
```

查询命令：

```powershell
python .\main.py "query text"
python .\main.py --query "query text" --top-k 3 --html-report .\report.html
python .\main.py --web-ui --port 8008
```

交互式查询命令：

```powershell
python .\main.py
python .\main.py --top-k 3
```

交互式模式的预期行为：

- 每行输入一个查询
- 输出本地 cosine similarity Top K
- 空行退出
- `/top 2` 这类命令可动态调整会话内 Top K
- `/file ollama` 可启用文件名过滤
- `/clearfile` 可清除文件名过滤
- `/report .\report.md` 可开启 Markdown 报告导出
- `/clearreport` 可停止 Markdown 报告导出
- `/htmlreport .\report.html` 可开启静态 HTML 报告导出
- `/clearhtmlreport` 可停止静态 HTML 报告导出
- 终端结果预览里的 `[[...]]` 表示查询词高亮
- Markdown 报告里的 `**...**` 表示查询词高亮
- HTML 报告里的 `<mark>` 表示查询词高亮
- HTML 报告是静态文件，不需要本地 Web 服务
- `--web-ui` 会启动一个本地 HTTP UI，适合浏览器交互查询
- Web UI 页面包含 Query、Top K、File Filter、Indexed Chunks、Matching Chunks 摘要
- Web UI 可直接下载当前结果为 Markdown / HTML
- Web UI 的 File Filter 可显示已索引 source file 的下拉候选
- Web UI 结果卡片里的文件名标签可直接跳到对应过滤结果
- Web UI 下载响应头文件名会带 query 和时间戳，便于留档
- Web UI 过滤态会显示单独的结果数徽标
- Web UI 可在过滤态下追加“全量结果基线”对比区，而不是覆盖当前过滤结果

## 排障要点

### 缺少命令

- 如果 `cocoindex` 不存在，先确认是否已执行 `pip install -e .`
- 如果 Python 环境不一致，确认 `pip` 与 `python` 指向的是同一环境

### 缺少依赖

- 优先查看仓库根 `pyproject.toml`
- 运行示例时优先查看示例目录自己的 `pyproject.toml`
- 缺哪个装哪个，不要盲目安装全部可选依赖

### Ollama 不可用

- 先检查 `ollama --version` 与 `ollama list`
- 再检查 `http://127.0.0.1:11434/api/tags` 是否可访问
- 确认不要把本地 `11434` 请求走代理，必要时设置 `NO_PROXY=127.0.0.1,localhost`
- 不要擅自改动 `C:\Users\zhouy\.ollama`、`C:\Users\zhouy\AppData\Local\Ollama`、`C:\Users\zhouy\AppData\Local\Programs\Ollama` 这三处到 D 盘的目录联接
- 如果 `pip install -e ".[litellm]"` 因 `core.pyd` 被占用失败，改用 `pip install litellm`

### 误判为 Web 服务

如果用户要求“启动服务”，先解释并确认：

- 该仓库主要是 CLI/库
- 根目录不是典型 HTTP server 项目
- 可运行对象一般是某个 CocoIndex App
- 常驻运行方式一般是 `cocoindex update --live`

## 文档更新要求

如果任务要求同步记录到仓库文档：

- 本地操作摘要写入 `AGENTS.md`
- 用户向导写入中文操作手册
- 所有新增 Markdown 文档使用 UTF-8 编码
- 中文内容直接书写，不要复制含乱码的终端输出
- 记录本机 `Ollama` 信息时，优先写“已验证可用状态 + 固定路径 + 最小检查命令”
- 若完成了 Ollama 联调，优先补充“示例目录 + 运行命令 + 输出文件 + embedding 维度 + 是否命中 memo”
- 若完成了本地查询联调，额外补充“查询命令 + Top 1 命中结果 + 相似度分数 + 是否为本地 cosine similarity”
- 若完成了演示版验证，补充“索引文件数 + Showing top N of M + `/top N` 是否生效 + 多文件命中情况”
- 若完成了过滤/报告能力验证，补充“--file-contains 是否生效 + 报告文件路径 + 报告是否落盘 + warning 是否已消除”
- 若完成了静态 HTML 报告页验证，补充“--html-report 是否生效 + HTML 文件路径 + 是否可直接浏览器打开 + `/htmlreport` 与 `/clearhtmlreport` 是否生效”
- 若完成了本地 Web UI 验证，补充“--web-ui 启动命令 + 绑定地址 + 是否可返回查询结果页 + 页面上是否展示 filter 与参数摘要”
- 若完成了 Web UI 下载/过滤增强验证，补充“下载按钮是否生效 + 下载内容包含哪些摘要字段 + 首页是否出现文件名下拉候选 + 是否修复 event loop closed”
- 若完成了过滤态对比视图验证，补充“过滤结果数徽标是否出现 + Compare With All Results 是否可点击 + 是否出现 All Results Baseline 区块”
- 若完成了高亮验证，补充“终端高亮标记 + 报告高亮标记 + 示例查询词 + 高亮是否命中正确文件”

## 参考资料

按需读取，不要一次性全部加载：

- 常用命令：`references/commands.md`
- 目录和路径：`references/layout.md`
- 常见排障：`references/troubleshooting.md`
- 项目判定标准：`references/project-rules.md`
- 收口检查清单：`references/checklist.md`

## 输出要求

完成任务时，优先给出：

- 实际执行的关键命令
- 当前可用的入口命令
- 是否成功安装
- 是否成功运行示例
- 日志和输出文件位置
- 如何停止后台进程
