# AGENTS.md

This file provides guidance to coding agents working with code in this repository.
Claude Code compatibility is kept through `CLAUDE.md`, which imports this file.

## Build and Test Commands

This project uses [uv](https://docs.astral.sh/uv/) for Python project management.

### Building

```bash
uv run maturin develop   # Build Rust code and install Python package (required after Rust changes)
```

### Testing

```bash
cargo test               # Run Rust tests
uv run mypy              # Type check Python code
uv run pytest python/    # Run Python tests (use after both Rust and Python changes)
```

### Code Formatting and Linting

```bash
uv run ruff format .           # Format Python code
uv run ruff format --check .   # Check formatting without making changes (same as CI)
uv run ruff check .            # Lint Python code
```

### Workflow Summary

| Change Type | Commands to Run |
|-------------|-----------------|
| Rust code only | `uv run maturin develop && cargo test` |
| Python code only | `uv run mypy && uv run pytest python/` |
| Both Rust and Python | Run all commands from both categories above |
| Python formatting | `uv run ruff format .` |

## Code Structure

```
cocoindex/
├── rust/                       # Rust crates (workspace)
│   ├── core/                   # Core engine crate
│   │   └── src/
│   │       ├── engine/         # Core engine
│   │       ├── state/          # States of the core engine
│   │       └── inspect/        # Database inspection utilities
│   ├── py/                     # Python bindings (PyO3)
│   ├── py_utils/               # Python-Rust utility helpers (error, convert, future)
│   ├── utils/                  # General utilities: error, batching, fingerprint, etc.
│   └── ops_text/               # Text processing operations (splitter, language detection)
│
├── python/
│   ├── cocoindex/              # Python package
│   │   ├── __init__.py         # Package entry point
│   │   ├── cli.py              # CLI commands
│   │   ├── _internal/          # Internal implementation for the core engine
│   │   │   ├── api.py          # Public API: mount, use_mount, mount_each, map, mount_target, App, fn, start/stop
│   │   │   ├── app.py          # App base implementation
│   │   │   ├── context_keys.py # ContextKey and ContextProvider
│   │   │   ├── environment.py  # Environment and lifespan handling
│   │   │   ├── function.py     # @coco.fn decorator implementation
│   │   │   ├── component_ctx.py # ComponentContext and component_subpath
│   │   │   ├── target_state.py # Target state implementation
│   │   │   └── core.pyi        # Type stubs for the Rust extension module (update when PyO3 APIs change)
│   │   ├── connectors/         # External system connectors (localfs, postgres, qdrant, lancedb, google_drive)
│   │   ├── connectorkits/      # Connector building utilities
│   │   ├── resources/          # Abstractions: file.py (FileLike), chunk.py (Chunk), schema.py
│   │   └── ops/                # Operations: text.py (RecursiveSplitter), sentence_transformers.py
│   └── tests/                  # Python tests
│
├── examples/                   # Example applications
├── docs/                       # Documentation
└── dev/                        # Development utilities
```

## Key Concepts

### Mental model: declarative data pipelines

CocoIndex uses a **declarative** programming model — you specify *what* your output should look like (target states), not *how* to incrementally update it. The engine handles change detection and applies minimal updates automatically.

Think of it like:

* **React**: declare UI as function of state → React re-renders what changed
* **Spreadsheets**: declare formulas → cells recompute when inputs change
* **CocoIndex**: declare target states as function of source → engine syncs what changed

### Core concepts

**App** — The top-level runnable unit. Bundles a main function with its arguments. When you call `app.update()`, the main function runs as the root processing component.

**Processing Component** — The unit of execution that owns a set of target states. Created by `mount()` or `use_mount()` at a specific component path. When a component finishes, its target states sync atomically to external systems.

**Component Path** — Stable identifier for a processing component across runs. Created via `coco.component_subpath("process", filename)`. CocoIndex uses component paths to:

* Match components to their previous runs for change detection
* Determine ownership of target states (if a path disappears, its target states are cleaned up)

**Target State** — What you want to exist in an external system (a file, a database row, a table). You *declare* target states; CocoIndex keeps them in sync — creating, updating, or removing as needed.

**Target** — The API object used to declare target states (e.g., `DirTarget`, `TableTarget`). Targets can be nested: a container target state (directory/table) provides a Target for declaring child target states (files/rows).

**Function** — A Python function decorated with `@coco.fn`. Use `memo=True` to enable memoization (skip execution when inputs and code are unchanged).

**Context** — React-style provider mechanism for sharing resources. Define keys with `ContextKey[T]`, provide values in lifespan via `builder.provide()`, use in functions via `coco.use_context(key)`.

### Key APIs

```python
# Mounting processing components (subpath auto-derived from fn.__name__)
await coco.mount(fn, *args, **kw)                                       # child runs independently
result = await coco.use_mount(fn, *args, **kw)                          # returns value directly

# Explicit subpath (for multi-part paths or multiple mounts of same function)
await coco.mount(coco.component_subpath("process", filename), fn, *args, **kw)
result = await coco.use_mount(coco.component_subpath("name"), fn, *args, **kw)

# Component subpath composition
subpath = coco.component_subpath("process", filename)  # multiple parts
subpath = coco.component_subpath("a") / "b" / "c"      # chaining with /

# Using component_subpath as context manager (applies to all nested mount calls)
with coco.component_subpath("process"):
    for f in files:
        await coco.mount(coco.component_subpath(str(f.relative_path)), process_file, f, target)

# Declaring target states (typically via Target methods)
dir_target.declare_file(filename=name, content=data)
table_target.declare_row(row=MyRow(...))

# Using context values
db = coco.use_context(PG_DB)  # retrieve value provided in lifespan

# Explicit context management (for ThreadPoolExecutor)
ctx = coco.get_component_context()
with ctx.attach():
    # coco APIs work correctly in this thread
    coco.mount(...)
```

**Mount handles:**

* `mount()` → `ComponentMountHandle`: call `await handle.ready()` to wait until target states are synced
* `use_mount()` → returns the result value directly (awaitable)

### How syncing works

When a processing component finishes, CocoIndex compares its declared target states with those from the previous run at the same component path:

* New target states → create (insert row, create file)
* Changed target states → update
* Missing target states → delete

Changes are applied atomically per component. If a source item is deleted (path no longer mounted), all its target states are cleaned up automatically.

### Example

```python
@coco.fn(memo=True)
async def process_file(file: FileLike, target: localfs.DirTarget) -> None:
    html = _markdown_it.render(await file.read_text())
    outname = "__".join(file.file_path.path.parts) + ".html"
    target.declare_file(filename=outname, content=html)

@coco.fn
async def app_main(sourcedir: pathlib.Path, outdir: pathlib.Path) -> None:
    target = await coco.use_mount(localfs.declare_dir_target, outdir)

    files = localfs.walk_dir(
        sourcedir, path_matcher=PatternFilePathMatcher(included_patterns=["**/*.md"])
    )
    await coco.mount_each(process_file, files.items(), target)


app = coco.App(
    coco.AppConfig(name="FilesTransform"),
    app_main,
    sourcedir=pathlib.Path("./docs"),
    outdir=pathlib.Path("./out"),
)
app.update_blocking(report_to_stdout=True)
```

## Code Conventions

### Internal vs External Modules

We distinguish between **internal modules** (under packages with `_` prefix, e.g. `_internal.*` or `connectors.*._source`) and **external modules** (which users can directly import).

**External modules** (user-facing, e.g. `cocoindex/ops/sentence_transformers.py`):

* Be strict about not leaking implementation details
* Use `__all__` to explicitly list public exports
* Prefix ALL non-public symbols with `_`, including:
  * Standard library imports: `import threading as _threading`, `import typing as _typing`
  * Third-party imports: `import numpy as _np`, `from numpy.typing import NDArray as _NDArray`
  * Internal package imports: `from cocoindex.resources import schema as _schema`
* Exception: `TYPE_CHECKING` imports for type hints don't need prefixing

**Internal modules** (e.g. `cocoindex/_internal/component_ctx.py`, `**/_target.py`):

* Less strict since users shouldn't import these directly
* Standard library and internal imports don't need underscore prefix
* Only prefix symbols that are truly private to the module itself (e.g. `_context_var` for a module-private ContextVar)

### Minimize API surface until deemed necessary

When adding a new public API (function, class, kwarg, configuration option), prefer the smallest surface that solves the concrete need in front of you. Do not pre-expose tunables, hooks, or alternatives "in case someone needs them." Adding a kwarg later is straightforward and backwards-compatible; removing or renaming one is disruptive. If a knob is currently a hardcoded constant inside the implementation, leave it there until a real use case demands it — at which point promoting it to a kwarg is mechanical. This applies equally to optional parameters, callback hooks, parser/transformer plug-points, and configuration keys.

### General principles (also covered by `/review-changes`)

- **Top-level imports.** Defer to in-function only for a real circular dependency or a heavy import that isn't always needed.
- **Specific types over `Any`.** Use concrete types — including concrete types from third-party libraries. `Any` only when the type is truly generic and no downstream code needs to downcast it.
- **Validate and exchange early.** When a value enters as a weaker form (`str`, `Any`, raw identifier), convert to the strong type at the earliest point. Don't propagate the weak form. Concrete example in this codebase: connector handlers receive a `ContextKey` string as part of a target-state key. The parent handler resolves the key once (when constructing the child handler) and passes the typed connection directly — the child stores `_pool: asyncpg.Pool`, not `_db_key: str`.
- **`NamedTuple`/small dataclass for multi-value returns.** Access fields by name (`result.can_reuse`) at call sites.
- **Exceptions for exceptional situations only.** Reserve exceptions (Python) and errors (Rust) for truly unexpected failures — not for end-of-iteration, "not found", or other expected state transitions. Use explicit return values (sentinel, enum variant, `None`) for those.
- **Single source of truth, delete dead code, honest names.** When the same value/logic appears in multiple places, consolidate. When changes make code unreachable, delete it (and its tests, and any dead config knobs). Function and field names should describe what the implementation does today.

### Testing Guidelines

We prefer end-to-end tests on user-facing APIs, over unit tests on smaller internal functions. With this said, there're cases where unit tests are necessary, e.g. for internal logic with various situations and edge cases, in which case it's usually easier to cover various scenarios with unit tests.

#### Test Environment Setup

Use `common.create_test_env(__file__)` to create a CocoIndex `Environment` for tests. It derives a unique `db_path` from the test file path and picks up the current event loop automatically.

* **Sync tests** (module-level creation): Call at module level — the Environment creates a background loop for async callbacks.

  ```python
  coco_env = common.create_test_env(__file__)
  ```

* **Async tests with async resources** (e.g., asyncpg pools): Call inside an async fixture so the Environment binds to the test's running event loop (same loop the pool is on). Use the `suffix` parameter when each test needs its own Environment:

  ```python
  @pytest_asyncio.fixture
  async def pg_env(request: pytest.FixtureRequest) -> Any:
      pool = await asyncpg.create_pool(dsn)
      coco_env = common.create_test_env(__file__, suffix=request.node.name)
      coco_env.context_provider.provide(DB_KEY, pool)
      yield pool, coco_env
      await pool.close()
  ```

  The `suffix` ensures each test gets a unique `db_path`, avoiding "environment already open" errors.

#### Testcontainers for Database Tests

Use `testcontainers[postgres]` (in the `build-test` dependency group) to spin up real database instances automatically — no manual setup or environment variables needed. Use a module-scoped sync fixture for the container and a function-scoped async fixture for per-test resources:

```python
@pytest.fixture(scope="module")
def pg_dsn() -> Any:
    with PostgresContainer("postgres:16-alpine") as pg:
        dsn = pg.get_connection_url().replace("postgresql+psycopg2://", "postgresql://")
        yield dsn

@pytest_asyncio.fixture
async def pool(pg_dsn: str) -> Any:
    p = await asyncpg.create_pool(pg_dsn)
    yield p
    await p.close()
```

### LMDB write paths

- All LMDB writes must go through `Storage::run_txn` (uses the single-writer batcher).
- Do not open a heed write txn directly or wrap the env in a separate mutex/semaphore — bypassing the batcher loses fsync coalescing and regresses concurrent-submit throughput by 10-100×.
- LMDB has no savepoints. If a sub-operation needs to "abort," handle it at the body level (e.g. return a sentinel result without writing); never attempt per-body rollback inside the batcher.

### Sync vs Async

The Rust core (`rust/core`, `rust/utils`) uses **async-first** design with Tokio. The `rust/py` crate bridges Rust async to Python, offering both sync and async APIs:

* Rust core exposes async functions
* `rust/py` provides sync wrappers that use `block_on()` to call async Rust from sync Python
* Python's `cocoindex` API is **async-first**: mount APIs (`mount`, `use_mount`, `mount_each`, `map`) are all `async def`; `App.update()`/`App.drop()` are async; sync entry points (`App.update_blocking()`, `App.drop_blocking()`, `start_blocking()`, `stop_blocking()`) are available for CLI and blocking contexts

When adding new functionality that involves I/O or concurrency:

* Implement async in Rust
* Bridge to Python via `rust/py`, providing both sync and async variants if needed

## Versioning

The current codebase is for CocoIndex v1, which is a fundamental redesign from CocoIndex v0. Currently the `v1` branch is the main branch for CocoIndex v1 code.

## Docs diagrams

All diagrams embedded in docs pages are built as inline Astro components under `docs/src/components/diagrams/`, not exported SVG files. See [docs/src/components/diagrams/README.md](docs/src/components/diagrams/README.md) for the palette, primitives, shared CSS classes, animation conventions, and step-by-step authoring guidelines. Follow that guide for any new or updated diagram.

## Agent Playbooks

Reusable task-specific agent guidance lives under `dev/agent-skills/`. These playbooks use a `SKILL.md` format so Claude Code can load them directly from `.claude/skills/`, but the content is intended to be readable by any coding agent.

- For docs diagrams, read `dev/agent-skills/cocoindex-diagrams/SKILL.md`.
- For new target connectors, read `dev/agent-skills/target-connector/SKILL.md`.
- For upgrading example package versions, read `dev/agent-skills/upgrade-examples/SKILL.md`.

Claude-specific runtime configuration, hooks, and compatibility symlinks remain under `.claude/`. Do not put portable project guidance there; keep it in this file or under `dev/agent-skills/`.

Portable agent checks live under `dev/agent-checks/`. Claude Code hooks in `.claude/hooks/` are thin adapters that call these scripts when relevant files changed.

## Local Machine Operation Notes

# CocoIndex 项目代理操作说明

本文档记录了 `D:\knowledgeBase\cocoindex\cocoindex_repo` 的本地拉取、安装、验证与启动方式，供后续代理或人工操作时直接复用。

## 1. 项目定位

- GitHub 仓库：`https://github.com/cocoindex-io/cocoindex.git`
- 本地目录：`D:\knowledgeBase\cocoindex\cocoindex_repo`
- 项目类型：`Python + Rust` 混合项目
- 官方入口：`cocoindex` CLI
- 重要区别：该项目当前不是传统意义上的 Web 服务仓库，根目录没有 `serve` 或 `server` 子命令。常见运行方式是：
  - `cocoindex init`
  - `cocoindex update`
  - `cocoindex update --live`

## 2. 本次已完成的安装与验证

### 2.1 代码下载

已成功克隆仓库到当前目录下：

```powershell
git clone https://github.com/cocoindex-io/cocoindex.git cocoindex_repo
```

### 2.2 环境探测结果

- `Python 3.13.2` 可用
- `cargo 1.95.0` 可用
- `rustc 1.95.0` 可用
- `uv` 当时未安装，但不影响使用 `pip install -e .`

### 2.3 本地安装方式

在仓库根目录执行：

```powershell
cd D:\knowledgeBase\cocoindex\cocoindex_repo
pip install -e .
```

安装结果：

- 已成功构建并安装本地可编辑版本
- `cocoindex --version` 返回 `999.0.0`
- `cocoindex --help` 可正常显示命令列表

说明：

- 该版本号来自本地源码 editable 安装，不代表 PyPI 发布版本号
- `pip` 本次安装已自动使用国内镜像源，无需额外切换代理

## 3. CLI 能力确认

已确认根 CLI 当前包含以下命令：

- `cocoindex ls`
- `cocoindex show`
- `cocoindex update`
- `cocoindex drop`
- `cocoindex init`

根目录当前未发现：

- `cocoindex serve`
- `cocoindex server`

因此不要把本项目按“HTTP 服务”来理解。对于 CocoIndex，所谓“启动服务”更准确的说法是：

- 启动某个 CocoIndex App 进行一次处理：`cocoindex update`
- 启动某个 CocoIndex App 持续监听更新：`cocoindex update --live`

## 4. 已完成的实际运行记录

### 4.1 Quickstart 项目初始化

已执行：

```powershell
cd D:\knowledgeBase\cocoindex\cocoindex_repo
cocoindex init quickstart_demo --dir quickstart_demo
cd quickstart_demo
cocoindex update .\main.py
```

结果：

- 已创建 `quickstart_demo`
- 示例 App 可正常运行
- 本地数据库文件由项目自身在运行目录下维护

### 4.2 官方示例 files_transform 运行

已验证目录：

`D:\knowledgeBase\cocoindex\cocoindex_repo\examples\files_transform`

首次运行时遇到依赖缺口：

- 缺少 `markdown-it-py[linkify,plugins]`

已补装：

```powershell
pip install "markdown-it-py[linkify,plugins]"
```

随后重新执行：

```powershell
cd D:\knowledgeBase\cocoindex\cocoindex_repo\examples\files_transform
cocoindex update .\main.py
```

结果：

- 成功处理示例目录中的 Markdown 文件
- 成功生成 HTML 输出文件
- 输出目录：`examples\files_transform\output_html`

## 5. 当前已启动的常驻进程

已在后台启动 `files_transform` 的 live 模式：

```powershell
cd D:\knowledgeBase\cocoindex\cocoindex_repo\examples\files_transform
cocoindex update .\main.py --live
```

本次记录到的后台进程信息：

- 进程名：`cocoindex`
- PID：`31648`

说明：

- PID 仅代表本次记录时的进程号，后续重启后可能变化
- 如果进程已退出，应重新启动，不要依赖旧 PID

## 6. 日志与输出位置

后台 live 进程日志：

- 标准输出：
  `D:\knowledgeBase\cocoindex\cocoindex_repo\examples\files_transform\cocoindex-live.stdout.log`
- 标准错误：
  `D:\knowledgeBase\cocoindex\cocoindex_repo\examples\files_transform\cocoindex-live.stderr.log`

示例输出目录：

- `D:\knowledgeBase\cocoindex\cocoindex_repo\examples\files_transform\output_html`

## 7. 常用操作命令

### 7.1 进入仓库

```powershell
cd D:\knowledgeBase\cocoindex\cocoindex_repo
```

### 7.2 安装项目

```powershell
pip install -e .
```

### 7.3 查看 CLI 帮助

```powershell
cocoindex --help
```

### 7.4 初始化一个新项目

```powershell
cocoindex init my_app --dir my_app
```

### 7.5 运行某个 App

```powershell
cocoindex update .\main.py
```

### 7.6 以 live 模式常驻运行

```powershell
cocoindex update .\main.py --live
```

### 7.7 停止后台 live 进程

```powershell
Stop-Process -Id 31648
```

如果 PID 已变化，先查询再停止：

```powershell
Get-Process | Where-Object { $_.ProcessName -eq 'cocoindex' }
Stop-Process -Id <PID>
```

## 8. 代理使用建议

后续代理在处理本仓库时，建议遵守以下顺序：

1. 先判断目标是“开发库本身”还是“运行某个示例/业务 App”
2. 如果只是验证安装，优先使用 `cocoindex --help`、`cocoindex --version`
3. 如果要验证运行，优先使用 `quickstart_demo` 或 `examples\files_transform`
4. 如果需要常驻模式，优先使用 `cocoindex update .\main.py --live`
5. 如果示例缺依赖，优先查看该示例目录下的 `pyproject.toml`
6. 不要默认假设项目存在 HTTP 服务入口

## 9. 代理与网络说明

本次操作中：

- `git clone` 已成功完成
- `pip install -e .` 已成功完成
- 未强制使用本地代理服务
- `pip` 已自动使用镜像源，因此下载速度可接受

如果后续遇到下载慢或超时，可以再检查并设置本机代理环境变量，例如：

```powershell
$env:HTTP_PROXY="http://127.0.0.1:端口"
$env:HTTPS_PROXY="http://127.0.0.1:端口"
```

设置前应先确认本机代理实际监听端口。

## 10. 本机 Ollama 约定

后续如果在本仓库里做本地 embedding、LiteLLM 联调或需要本地模型时，优先复用这台机器已经验证过的 `Ollama` 环境，不要重复安装或重新拉模型。

### 10.1 当前已知可用状态

- `Ollama 0.24.0` 已安装可用
- `ollama list` 已验证可正常返回
- `http://127.0.0.1:11434/api/tags` 已验证可访问
- 当前已确认存在模型：`nomic-embed-text:latest`

### 10.2 本机固定路径

Ollama 在这台机器上不是默认散落在 C 盘，而是已经迁移到 D 盘，并通过目录联接兼容原路径：

- 程序目录实际位置：`D:\knowledgeBase\Ollama`
- 程序目录原路径联接：`C:\Users\zhouy\AppData\Local\Programs\Ollama -> D:\knowledgeBase\Ollama`
- 模型与数据目录实际位置：`D:\knowledgeBase\.ollama`
- 模型与数据目录原路径联接：`C:\Users\zhouy\.ollama -> D:\knowledgeBase\.ollama`
- 日志与本地状态目录实际位置：`D:\knowledgeBase\OllamaLocal`
- 日志与本地状态目录原路径联接：`C:\Users\zhouy\AppData\Local\Ollama -> D:\knowledgeBase\OllamaLocal`
- `ollama.exe` 实际路径：`D:\knowledgeBase\Ollama\ollama.exe`

不要擅自把这些目录迁回 C 盘，也不要在未知前提下删除这些联接。

### 10.3 最小检查命令

进入本仓库前后，如需确认本地模型链路是否可用，优先执行：

```powershell
ollama --version
ollama list
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:11434/api/tags
```

如需补模型，优先使用已验证过的 embedding 模型：

```powershell
ollama pull nomic-embed-text
```

### 10.4 网络与代理约定

`Ollama` 本地接口走回环地址，一般不应经过代理。若当前任务同时需要联网拉依赖，可设置：

```powershell
$env:HTTP_PROXY="http://127.0.0.1:18080"
$env:HTTPS_PROXY="http://127.0.0.1:18080"
$env:NO_PROXY="127.0.0.1,localhost"
```

如果只是访问本地 `Ollama`，优先保留 `NO_PROXY`，避免把 `11434` 的本地请求错误转发到代理。

### 10.5 在 CocoIndex 任务中的使用建议

- 如果任务是本地向量化或 embedding 实验，优先考虑 `Ollama + nomic-embed-text`
- 如果任务文档写的是 `LiteLLMEmbedder`，模型名应写成 `ollama/nomic-embed-text`
- 默认本地 API 地址使用 `http://127.0.0.1:11434`
- 若任务目标只是验证本地链路，可先验证 `ollama` 本身，再运行 `cocoindex update`
- 不要把外部 API key 方案和本地 `Ollama` 混为一谈；`Ollama` 本地 embedding 不需要 API key

### 10.6 已验证的最小 Ollama 示例

当前仓库已新增并跑通一个最小本地示例：

- 示例目录：`examples\text_embedding_local_ollama`
- 入口文件：`examples\text_embedding_local_ollama\main.py`
- 输入目录：`examples\text_embedding_local_ollama\data`
- 输出目录：`examples\text_embedding_local_ollama\output_embeddings`
- 内部状态库：`examples\text_embedding_local_ollama\cocoindex.db`

用途：

- 读取本地 Markdown
- 使用 `RecursiveSplitter` 切分文本
- 通过 `LiteLLMEmbedder("ollama/nomic-embed-text", api_base="http://127.0.0.1:11434")` 调用本地 Ollama
- 把每个 chunk 的 embedding 直接写成本地 JSON 文件
- 基于输出 JSON 做本地 cosine similarity 查询，不依赖外部向量库

最小运行命令：

```powershell
cd D:\knowledgeBase\cocoindex\cocoindex_repo\examples\text_embedding_local_ollama
pip install litellm
cocoindex update .\main.py
```

已验证结果：

- `cocoindex update .\main.py` 成功
- 生成文件：`output_embeddings\data__sample.md__0_334.json`
- 输出 JSON 已包含：
  - `embedding_model = ollama/nomic-embed-text`
  - `ollama_api_base = http://127.0.0.1:11434`
  - `embedding_dim = 768`
- 第二次运行命中 memo，`process_file` 显示 `1 unchanged`
- `python .\main.py "local embedding path"` 查询成功
- 当前实际命中结果：
  - Top 1: `data\sample.md`
  - score: `0.7575`
- 查询路径会：
  - 先用本地 Ollama 为查询词生成 embedding
  - 再读取 `output_embeddings\*.json`
  - 在本地做 cosine similarity 排序

当前脚本入口约定：

- `cocoindex update .\main.py`：更新/生成 embedding
- `python .\main.py "query text"`：执行单次本地相似度查询
- `python .\main.py`：进入交互式多轮查询模式
- `python .\main.py --query "query text" --top-k 3`：执行可配置 Top K 的单次查询
- `python .\main.py --top-k 3`：以指定默认 Top K 进入交互模式

交互式模式已验证通过：

- 启动后会提示 `Interactive local query mode`
- 每行输入一个查询
- 空行退出
- 已实际验证两次查询：
  - `local embedding path` -> `score = 0.7002`
  - `CocoIndex sample` -> `score = 0.6169`

当前示例已扩成演示版：

- `data` 目录下已有 4 个 Markdown 文件
- 当前已生成 4 个 embedding JSON 块
- 查询输出会先打印 `Showing top N of M indexed chunks`
- 交互式模式支持输入 `/top 2` 这类命令，动态调整会话内 Top K
- 支持按文件名子串过滤结果
- 支持把查询结果导出成 Markdown 报告
- 支持查询结果高亮片段预览
- 已在代码里设置 `LITELLM_LOCAL_MODEL_COST_MAP=true`，避免远端 cost map 超时
- 已安装 `botocore`，避免 Bedrock/SageMaker 预加载缺失 warning

本次实际验证结果：

- 单次查询命令：
  - `python .\main.py --query "local model embeddings" --top-k 3`
- 返回结果：
  - `Showing top 3 of 4 indexed chunks`
  - Top 1: `data\ollama_notes.md`，`score = 0.8379`
  - Top 2: `data\sample.md`，`score = 0.7375`
  - Top 3: `data\vector_search_demo.md`，`score = 0.5862`

- 交互式查询命令：
  - `python .\main.py`
  - 输入 `/top 2` 后生效
  - `vector search` 的 Top 1 命中：`data\vector_search_demo.md`
  - `Ollama API` 的 Top 2 包含：`data\ollama_notes.md`

- 文件名过滤 + Markdown 报告导出命令：
  - `python .\main.py --query "local model embeddings" --top-k 3 --file-contains ollama --report .\demo-report.md`
  - 已实际输出：
    - `Showing top 1 of 1 indexed chunks`
    - `File filter: ollama`
    - Top 1: `data\ollama_notes.md`
  - 已生成报告：`examples\text_embedding_local_ollama\demo-report.md`

- 交互式文件过滤与报告导出：
  - 已实际验证命令序列：
    - `/file vector`
    - `vector search`
    - `/clearfile`
    - `/report .\interactive-report.md`
    - `Ollama API`
  - 已生成报告：`examples\text_embedding_local_ollama\interactive-report.md`

- 高亮片段已验证：
  - 终端查询结果里使用 `[[...]]` 标出查询词命中片段
  - Markdown 报告里使用 `**...**` 标出查询词命中片段
  - `python .\main.py --query "Ollama API" --top-k 2` 时，`data\ollama_notes.md` 的预览中出现 `[[Ollama]]` 与 `[[API]]`
  - `python .\main.py --query "vector search" --top-k 2 --report .\highlight-report.md` 时，报告中的高亮预览已正确显示 `**Vector**` 与 `**Search**`
  - 已生成报告：`examples\text_embedding_local_ollama\highlight-report.md`

- 静态 HTML 查询报告页已验证：
  - 单次导出命令：
    - `python .\main.py --query "vector search" --top-k 2 --html-report .\report.html`
  - 交互式导出命令序列：
    - `/htmlreport .\interactive-report.html`
    - `vector search`
    - `/clearhtmlreport`
  - 单次导出已实际输出：
    - `Showing top 2 of 4 indexed chunks`
    - Top 1: `data\vector_search_demo.md`，`score = 0.7222`
    - Top 2: `data\cocoindex_overview.md`，`score = 0.4809`
    - `HTML report written to report.html`
  - 已生成 HTML 文件：
    - `examples\text_embedding_local_ollama\report.html`
    - `examples\text_embedding_local_ollama\interactive-report.html`
  - 当前 HTML 报告页特性：
    - 纯静态文件，可直接本地浏览器打开
    - 展示 Query、Top K、Indexed Chunks、File Filter
    - 结果使用卡片布局显示 score、chunk range、embedding dim
    - 预览片段使用 `<mark>` 高亮查询词
    - 每条结果支持展开查看完整文本
  - 当前交互命令补充：
    - `/htmlreport PATH`：为后续查询启用 HTML 报告导出
    - `/clearhtmlreport`：关闭 HTML 报告导出

- 本地小型 Web UI 已验证：
  - 启动命令：
    - `python .\main.py --web-ui`
    - `python .\main.py --web-ui --port 8008`
  - 本次联调验证方式：
    - 在同一 Python 进程内用线程启动 `launch_web_ui(...)`
    - 实际请求首页：`http://127.0.0.1:8016/`
    - 实际请求查询页：`http://127.0.0.1:8016/?query=vector+search&top_k=2&file_contains=vector`
  - 已确认页面返回内容包含：
    - `Local Ollama Web UI`
    - `data\vector_search_demo.md`
    - `Matching Chunks`
    - `<mark>Vector</mark>`
  - 当前 Web UI 能力：
    - 浏览器表单输入 Query、Top K、File Filter
    - File Filter 输入框带本地索引文件名下拉候选
    - 请求时实时调用本地 Ollama 生成查询 embedding
    - 从 `output_embeddings\*.json` 读取候选向量并做本地 cosine similarity 排序
    - 页面展示 Query、Top K、File Filter、Indexed Chunks、Matching Chunks、Embed Model 摘要
    - 当前查询结果可直接下载为 Markdown 或 HTML
    - 结果卡片支持高亮预览与全文展开
  - 当前定位说明：
    - `--html-report` 适合导出留档
    - `--web-ui` 适合本机浏览器交互查询
    - 两者都不依赖 Postgres、Qdrant 或远端向量服务

- Web UI 导出按钮与文件名下拉候选已验证：
  - 本次联调验证地址：
    - 首页：`http://127.0.0.1:8018/`
    - 查询页：`http://127.0.0.1:8018/?query=vector+search&top_k=2&file_contains=vector`
    - Markdown 下载：`http://127.0.0.1:8018/?query=vector+search&top_k=2&file_contains=vector&download=md`
    - HTML 下载：`http://127.0.0.1:8018/?query=vector+search&top_k=2&file_contains=vector&download=html`
  - 已确认首页包含：
    - `file-filter-options`
    - `data\vector_search_demo.md`
    - `Indexed source files`
  - 已确认查询页包含：
    - `Download Markdown`
    - `Download HTML`
    - `Matching Chunks`
    - `<mark>Vector</mark>`
  - 已确认 Markdown 下载内容包含：
    - `# Local Ollama Query Report`
    - `File filter: \`vector\``
    - `Matching chunks after filter: \`1\``
  - 已确认 HTML 下载内容包含：
    - `Local Ollama Query Report`
    - `Matching Chunks After Filter`
    - `data\vector_search_demo.md`
  - 当前实现约束：
    - Web UI 内部使用常驻 asyncio event loop 复用本地 Ollama 查询 embedding
    - 已规避每次请求独立 `asyncio.run(...)` 时可能出现的 `Event loop is closed`

- Web UI 文件标签点击过滤与下载文件名增强已验证：
  - 本次联调验证地址：
    - 查询页：`http://127.0.0.1:8019/?query=vector+search&top_k=2`
    - 过滤目标页：`http://127.0.0.1:8020/?query=vector+search&top_k=2&file_contains=data%5Cvector_search_demo.md`
  - 已确认结果卡片里出现：
    - `filter:data\vector_search_demo.md`
  - 已确认点击后的过滤目标页包含：
    - `Current filter: <code>data\vector_search_demo.md</code>`
    - `Matching Chunks`
    - `data\vector_search_demo.md`
  - 已确认下载响应头文件名带 query 和时间戳：
    - `attachment; filename="local-ollama-query-vector-search-20260517-191126.md"`
    - `attachment; filename="local-ollama-query-vector-search-20260517-191126.html"`

- Web UI 当前过滤高亮态与一键清除过滤已验证：
  - 本次联调验证地址：
    - 过滤页：`http://127.0.0.1:8021/?query=vector+search&top_k=2&file_contains=data%5Cvector_search_demo.md`
    - 无过滤页：`http://127.0.0.1:8021/?query=vector+search&top_k=2`
  - 已确认过滤页包含：
    - `ui-file-tag is-active`
    - `Clear Current Filter`
    - `Current filter: <code>data\vector_search_demo.md</code>`
  - 已确认无过滤页包含：
    - `filter:data\vector_search_demo.md`
    - `Download Markdown`
    - `Matching Chunks`
    - `Current filter: <code>(none)</code>`
  - 当前交互语义：
    - 若结果卡片文件标签对应当前过滤文件，则标签显示高亮态
    - 点击 `Clear Current Filter` 会保留当前 `query` 与 `top_k`，只清除 `file_contains`

- Web UI 过滤结果数徽标与全量结果对比视图已验证：
  - 本次联调验证地址：
    - 过滤页：`http://127.0.0.1:8023/?query=vector+search&top_k=2&file_contains=data%5Cvector_search_demo.md`
    - 对比页：`http://127.0.0.1:8023/?query=vector+search&top_k=2&file_contains=data%5Cvector_search_demo.md&compare=all`
  - 已确认过滤页包含：
    - `Compare With All Results`
    - `Filtered Results:`
    - `Clear Current Filter`
  - 已确认对比页包含：
    - `All Results Baseline`
    - `Showing the same query without the current file filter`
    - `Current filter: <code>data\vector_search_demo.md</code>`
    - `data\vector_search_demo.md`
  - 当前交互语义：
    - 过滤态下会显示单独的过滤结果数徽标
    - 点击该徽标会保留当前过滤结果，并在下方追加同 query / 同 top-k / 无 file filter 的全量基线结果区
    - 对比视图用于直接观察“当前过滤结果”和“全量结果”之间的差别，不会覆盖当前过滤态

当前高亮实现说明：

- 高亮基于查询词的本地字面匹配，不是 embedding 模型内部 token 级解释
- 作用是提高结果可读性，不改变实际向量检索排序

当前 warning 处理结论：

- `LiteLLM: Failed to fetch remote model cost map ... Falling back to local backup`
  - 已通过 `LITELLM_LOCAL_MODEL_COST_MAP=true` 规避
- `litellm: could not pre-load bedrock-runtime... Error: No module named 'botocore'`
  - 已通过安装 `botocore` 消除

当前环境中的一个实际注意事项：

- `pip install -e ".[litellm]"` 可能因为 `python\cocoindex\_internal\core.pyd` 被占用而失败
- 在这种情况下，优先改用 `pip install litellm`

## 11. 最小复现路径

如果需要最快验证 CocoIndex 当前仓库处于可用状态，执行以下命令即可：

```powershell
cd D:\knowledgeBase\cocoindex\cocoindex_repo
pip install -e .
cocoindex --version
cd .\examples\files_transform
pip install "markdown-it-py[linkify,plugins]"
cocoindex update .\main.py
```

若输出目录下生成 HTML 文件，则说明安装和运行链路正常。

## 12. 项目初始化整理摘要

本次已对 `D:\knowledgeBase\cocoindex\cocoindex_repo` 做了一轮可直接复用的仓库级整理，后续代理可把下面这份摘要当作默认入口认知。

### 12.1 仓库定位

- 这是一个 `Python + Rust` 混合仓库，不是传统 Web 服务仓库
- Python 包入口：`python\cocoindex`
- Rust 相关目录：`rust\cocoindex`、`rust\core`、`rust\py`、`rust\ops_text`、`rust\sdk`、`rust\utils`
- CLI 入口来自 `pyproject.toml`：
  - `cocoindex = "cocoindex.cli:cli"`
- 构建方式：
  - Python 侧由 `maturin` 驱动
  - Rust 扩展模块名：`cocoindex._internal.core`

### 12.2 根目录关键分层

- `python\`：Python 包与测试
- `rust\`：Rust 核心与 Python 绑定
- `examples\`：示例集合，当前已看到 29 个目录
- `docs\`：文档
- `skills\`：项目级技能文档
- `benchmarks\`：基准
- `quickstart_demo\`：本地初始化验证时创建的 demo
- `target\`：Rust 构建输出

### 12.3 当前最值得复用的运行入口

- 安装/验证：
  - `pip install -e .`
  - `cocoindex --version`
  - `cocoindex --help`
- 最快确认 CLI 正常：
  - `cocoindex init quickstart_demo --dir quickstart_demo`
  - `cd .\quickstart_demo`
  - `cocoindex update .\main.py`
- 最稳妥的官方示例验证：
  - `examples\files_transform`
- 当前本机最完整的本地 Ollama 演示入口：
  - `examples\text_embedding_local_ollama`

### 12.4 examples 目录当前可见示例面

当前已看到的示例目录包括：

- `amazon_s3_embedding`
- `audio_to_text`
- `code_embedding`
- `code_embedding_lancedb`
- `conversation_to_knowledge`
- `csv_to_kafka`
- `entire_session_search`
- `files_transform`
- `gdrive_text_embedding`
- `hn_trending_topics`
- `image_search`
- `image_search_colpali`
- `kafka_to_lancedb`
- `meeting_notes_graph_falkordb`
- `meeting_notes_graph_neo4j`
- `multi_codebase_summarization`
- `oci_object_storage_embedding`
- `paper_metadata`
- `patient_intake_extraction_baml`
- `patient_intake_extraction_dspy`
- `pdf_embedding`
- `pdf_to_markdown`
- `postgres_source`
- `rust`
- `text_embedding`
- `text_embedding_lancedb`
- `text_embedding_local_ollama`
- `text_embedding_qdrant`
- `text_embedding_turbopuffer`

### 12.5 当前仓库内已经整理完成的本地专用能力

`examples\text_embedding_local_ollama` 当前已经被扩成一个本机优先的完整演示入口，适合后续所有“先证明本地链路通不通”的任务。

已整理完成的能力包括：

- 本地 Markdown -> 本地 Ollama embedding -> 本地 JSON
- 本地 cosine similarity 查询
- 多文件检索
- Top K 可配置
- 交互式多轮查询
- 文件名过滤
- Markdown 报告导出
- 静态 HTML 报告导出
- 本地小型 Web UI
- Web UI 结果下载按钮
- Web UI 文件名下拉候选
- Web UI 文件标签点击过滤
- Web UI 当前过滤高亮态
- Web UI 一键清除过滤
- Web UI 过滤结果数徽标
- Web UI 全量结果对比视图

当前示例目录也已完成“最终演示收口”：

- 目录里临时性报告与空日志文件已清理
- 当前只保留 1 份 Markdown 样例报告：`examples\text_embedding_local_ollama\sample-report.md`
- 当前只保留 1 份 HTML 样例报告：`examples\text_embedding_local_ollama\sample-report.html`
- `examples\text_embedding_local_ollama\README.md` 已把这两个文件标成推荐查看入口

### 12.6 后续代理默认工作顺序

如果后续任务再次落到这个仓库，建议默认按以下顺序处理：

1. 先判断是“框架源码开发”还是“示例联调/运行”
2. 若只是确认环境，先跑 `cocoindex --help` 与 `cocoindex --version`
3. 若只是验证库可运行，优先用 `quickstart_demo` 或 `examples\files_transform`
4. 若任务涉及本地 embedding、LiteLLM、Ollama、检索交互或演示页面，优先从 `examples\text_embedding_local_ollama` 开始
5. 若需要仓库级知识回填，优先写入本文件 `AGENTS.md`
