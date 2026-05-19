# CocoIndex Local Ops 排障参考

## 1. 安装后找不到 cocoindex

现象：

- `cocoindex --help` 报命令不存在

排查顺序：

1. 重新执行 `pip install -e .`
2. 检查 `pip --version` 和 `python --version` 是否来自同一环境
3. 执行 `Get-Command cocoindex`

## 2. 误把项目当成 Web 服务

现象：

- 用户要求启动服务
- 但根目录找不到 `serve` 或 `server`

正确处理：

1. 先说明这是库/CLI 项目
2. 当前常用入口是 `cocoindex update`
3. 如果需要常驻运行，用 `cocoindex update --live`

## 3. 示例运行时报缺少依赖

现象：

- 运行某个示例时报 Python 模块缺失

正确处理：

1. 先看示例目录下自己的 `pyproject.toml`
2. 缺什么装什么，不要盲目安装全部 optional dependencies
3. `files_transform` 示例已知可能需要：

```powershell
pip install "markdown-it-py[linkify,plugins]"
```

## 4. Git 克隆中断或目录损坏

现象：

- 克隆超时
- 只生成 `.git` 目录
- 后续 `git fetch`、`git status` 异常

建议处理：

1. 先检查是否有残留 `git` 进程
2. 如存在，先停止残留进程
3. 删除不完整目录
4. 重新克隆

## 5. 中文文档乱码

现象：

- PowerShell `Get-Content` 打开中文 Markdown 出现乱码

建议处理：

1. 统一使用 UTF-8 编码保存
2. 在当前 Windows 环境下，优先保存为 `UTF-8 with BOM`
3. 修改后重新回读验证

## 6. Live 模式看起来无输出

现象：

- `--live` 已启动，但用户不确定是否正在监听

验证方式：

1. 查看 stdout 日志是否包含 `Watching for changes`
2. 向输入目录新增或修改一个文件
3. 检查输出目录是否生成或更新目标文件

## 7. 停止后台进程失败

现象：

- 不知道 PID
- 多个 `cocoindex` 进程并存

建议处理：

1. 先执行：

```powershell
Get-Process | Where-Object { $_.ProcessName -eq 'cocoindex' }
```

2. 结合启动时间判断目标进程
3. 再执行：

```powershell
Stop-Process -Id <PID>
```
