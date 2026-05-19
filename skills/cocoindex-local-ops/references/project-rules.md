# CocoIndex Local Ops 项目约定

本文档用于约束后续代理在 `D:\knowledgeBase\cocoindex\cocoindex_repo` 中执行安装、运行、验证和汇报时的判定标准。

## 1. 总体原则

后续代理在本仓库中工作时，必须先确认：

1. 这是一个 `Python + Rust` 的库/CLI 项目。
2. 不要默认把它当成传统 Web 服务仓库。
3. “启动服务”在本仓库里通常表示运行某个 CocoIndex App，尤其是 `cocoindex update --live`。
4. 结论必须基于本地命令实际输出，不要凭 README 文案直接下结论。

## 2. “安装完成”的判定标准

只有同时满足以下条件，才能向用户报告“安装完成”：

1. 仓库目录存在且结构完整，不是只有 `.git` 的半成品目录。
2. 在仓库根目录执行过：

```powershell
pip install -e .
```

3. 以下命令至少成功一个回合：

```powershell
cocoindex --version
cocoindex --help
```

4. `cocoindex --help` 中能看到根命令，例如：

- `init`
- `ls`
- `show`
- `update`
- `drop`

如果 `pip install -e .` 成功，但 `cocoindex --help` 失败，不得报告“安装完成”，只能报告“依赖已安装，但 CLI 不可用”。

## 3. “服务已启动”的判定标准

本仓库不应轻易使用“服务已启动”这种说法。后续代理需要先明确区分以下两种情况。

### 3.1 一次性运行成功

如果只执行了：

```powershell
cocoindex update .\main.py
```

则只能说：

- App 已成功执行一次
- 处理链路已跑通

不能说：

- 服务正在运行
- 服务已常驻启动

### 3.2 常驻运行成功

只有在 `--live` 模式下，并且满足以下条件，才能说“已启动并处于监听状态”：

1. 已执行：

```powershell
cocoindex update .\main.py --live
```

或等价的后台启动命令。

2. 存在仍在运行的 `cocoindex` 进程。

3. stdout 日志或前台输出中出现类似：

- `Watching for changes`
- `Ready`

4. 如有条件，至少做一次变更触发验证，确认 live 模式不是假启动。

如果只有进程存在，但没有日志证据，不要直接报告“已成功监听”。

## 4. “示例已验证通过”的判定标准

建议优先使用：

- `quickstart_demo`
- `examples/files_transform`

### 4.1 quickstart_demo 通过标准

满足以下条件才算通过：

1. 已执行：

```powershell
cocoindex init quickstart_demo --dir quickstart_demo
cd .\quickstart_demo
cocoindex update .\main.py
```

2. `update` 命令返回成功，没有致命报错。

3. 能说明这是模板 App 跑通，而不是功能型业务示例。

### 4.2 files_transform 通过标准

满足以下条件才算通过：

1. 已进入：

`D:\knowledgeBase\cocoindex\cocoindex_repo\examples\files_transform`

2. 示例依赖已满足；如果缺依赖，已补装并复跑。

3. 执行：

```powershell
cocoindex update .\main.py
```

返回成功。

4. 输出目录 `output_html` 中存在生成的 HTML 文件。

只有命令成功但没有产物时，不要报告“示例验证通过”。

## 5. Live 模式验证标准

如果代理需要报告 `files_transform` 的 live 模式已验证通过，应补做一次最小变更测试：

1. 在 `data` 目录新增或修改一个 Markdown 文件。
2. 等待 watcher 处理。
3. 检查 `output_html` 中是否生成或更新对应 HTML 文件。
4. 如为临时验证文件，验证完成后删除临时文件和对应产物。

只有命令启动成功但未做变更验证时，最多报告“live 进程已启动”，不要报告“live 处理链路已验证通过”。

## 6. 文档写回规则

当代理把结果写入 `AGENTS.md`、操作手册或本 skill 参考文档时，必须遵守：

1. 只写经本地执行验证过的信息。
2. PID、时间戳这类易变信息要注明“仅代表本次记录”。
3. 不要把一次性运行写成常驻服务。
4. 不要把 CLI 项目描述成 HTTP 服务。
5. 中文 Markdown 文档统一保存为 UTF-8；在当前 Windows 环境下优先用 `UTF-8 with BOM` 以避免 PowerShell 读出乱码。

## 7. 汇报模板约束

后续代理给用户汇报时，建议按以下顺序组织：

1. 仓库是否已正确下载
2. 安装是否完成
3. CLI 是否可用
4. 跑通的是一次性执行还是 live 常驻
5. 使用了哪个示例或项目进行验证
6. 产物、日志、进程或停止命令在哪里

## 8. 禁止性约束

后续代理在本仓库中不应做以下表述：

- “HTTP 服务已经启动”  
  前提不足时禁止使用。

- “项目已经完全可用”  
  如果只做了安装、没有做运行验证，禁止使用。

- “示例已通过验证”  
  如果没有实际输出产物，禁止使用。

- “live 已正常工作”  
  如果没有 watcher 日志或变更触发验证，禁止使用。
