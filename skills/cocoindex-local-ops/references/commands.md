# CocoIndex Local Ops 命令参考

适用目录：

`D:\knowledgeBase\cocoindex\cocoindex_repo`

## 1. 基础命令

进入仓库：

```powershell
cd D:\knowledgeBase\cocoindex\cocoindex_repo
```

本地开发安装：

```powershell
pip install -e .
```

查看版本：

```powershell
cocoindex --version
```

查看帮助：

```powershell
cocoindex --help
```

## 2. 快速验证命令

初始化一个测试项目：

```powershell
cocoindex init quickstart_demo --dir quickstart_demo
```

运行测试项目：

```powershell
cd D:\knowledgeBase\cocoindex\cocoindex_repo\quickstart_demo
cocoindex update .\main.py
```

## 3. 官方示例命令

进入 `files_transform` 示例：

```powershell
cd D:\knowledgeBase\cocoindex\cocoindex_repo\examples\files_transform
```

安装示例额外依赖：

```powershell
pip install "markdown-it-py[linkify,plugins]"
```

执行示例：

```powershell
cocoindex update .\main.py
```

以 live 模式运行：

```powershell
cocoindex update .\main.py --live
```

## 4. 进程管理命令

查询运行中的 `cocoindex`：

```powershell
Get-Process | Where-Object { $_.ProcessName -eq 'cocoindex' }
```

停止指定 PID：

```powershell
Stop-Process -Id <PID>
```

## 5. 日志查看命令

查看 stdout 日志尾部：

```powershell
Get-Content .\cocoindex-live.stdout.log -Tail 50
```

查看 stderr 日志尾部：

```powershell
Get-Content .\cocoindex-live.stderr.log -Tail 50
```

## 6. 代理环境命令

临时设置代理：

```powershell
$env:HTTP_PROXY="http://127.0.0.1:端口"
$env:HTTPS_PROXY="http://127.0.0.1:端口"
```

查看当前代理相关环境变量：

```powershell
Get-ChildItem Env: | Where-Object { $_.Name -match 'PROXY|proxy|HTTP|HTTPS' }
```
