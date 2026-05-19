# CocoIndex Local Ops 完成检查清单

本文档用于后续代理在 `D:\knowledgeBase\cocoindex\cocoindex_repo` 中执行任务后的收口检查。

## 1. 下载检查

在报告“仓库已下载”前，确认：

- [ ] 目标目录存在
- [ ] 目录不是只有 `.git` 的半成品
- [ ] 根目录能看到 `README.md`、`pyproject.toml`、`python/`、`rust/` 等主要内容

## 2. 安装检查

在报告“安装完成”前，确认：

- [ ] 已在仓库根目录执行 `pip install -e .`
- [ ] `cocoindex --version` 成功
- [ ] `cocoindex --help` 成功
- [ ] `cocoindex --help` 输出中能看到 `init`、`ls`、`show`、`update`、`drop`

## 3. CLI 识别检查

在解释运行方式前，确认：

- [ ] 已核实当前仓库根 CLI 没有 `serve` 或 `server`
- [ ] 已明确说明该项目是库/CLI 项目
- [ ] 已明确说明常驻运行通常使用 `cocoindex update --live`

## 4. 一次性运行检查

在报告“已跑通”前，确认：

- [ ] 至少执行过一次 `cocoindex update .\main.py`
- [ ] 命令返回成功
- [ ] 没有未处理的致命报错
- [ ] 汇报时使用“已执行一次”或“处理链路已跑通”，而不是“服务已启动”

## 5. 示例验证检查

如果使用 `quickstart_demo` 验证，确认：

- [ ] 已执行 `cocoindex init quickstart_demo --dir quickstart_demo`
- [ ] 已在 `quickstart_demo` 中执行 `cocoindex update .\main.py`
- [ ] 已说明这是模板项目验证

如果使用 `examples/files_transform` 验证，确认：

- [ ] 已进入 `examples\files_transform`
- [ ] 若缺依赖，已按需安装
- [ ] 已执行 `cocoindex update .\main.py`
- [ ] `output_html` 中确实生成了 HTML 文件

## 6. Live 模式检查

在报告“live 已启动”前，确认：

- [ ] 已执行 `cocoindex update .\main.py --live` 或等价后台命令
- [ ] 存在正在运行的 `cocoindex` 进程
- [ ] 日志或前台输出中可见 `Ready` 或 `Watching for changes`

在报告“live 已验证通过”前，额外确认：

- [ ] 已对输入目录做一次新增或修改
- [ ] watcher 已响应
- [ ] 输出目录出现了新增或更新产物
- [ ] 若使用临时验证文件，已清理临时输入和对应产物

## 7. 日志与进程检查

在报告后台运行状态前，确认：

- [ ] 已记录日志文件路径
- [ ] 已记录工作目录
- [ ] 已记录 PID 或给出查询 PID 的命令
- [ ] 已给出停止进程命令

## 8. 文档写回检查

如果本次任务涉及更新文档，确认：

- [ ] 写入内容来自实际执行结果，不是凭空推断
- [ ] 易变信息已标明“仅代表本次记录”
- [ ] 中文文档使用 UTF-8 编码
- [ ] 在当前 Windows 环境下已验证不会乱码

## 9. 最终汇报检查

在向用户结束汇报前，确认：

- [ ] 说明了实际完成了什么
- [ ] 说明了验证做到哪一步
- [ ] 区分了一次性运行和常驻运行
- [ ] 给出了关键路径、日志或输出位置
- [ ] 如果存在未做事项，已明确说明

## 10. 禁止项复核

结束前再复核一次，不要出现以下误报：

- [ ] 没有把一次性 `update` 说成服务常驻运行
- [ ] 没有把 CLI 项目说成 HTTP 服务
- [ ] 没有在无产物时说“示例验证通过”
- [ ] 没有在无 watcher 证据时说“live 正常工作”
