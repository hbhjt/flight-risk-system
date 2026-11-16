$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$Drive = $ProjectRoot.Substring(0, 1).ToLower()
$LinuxRoot = '/mnt/' + $Drive + ($ProjectRoot.Substring(2) -replace '\\', '/')
Write-Host '使用默认 WSL 发行版启动本地演示。按 Ctrl+C 关闭。'
& wsl.exe --cd $LinuxRoot -- bash scripts/start_demo.sh
if ($LASTEXITCODE -ne 0) { throw '演示启动失败，请检查终端提示及 README 中的环境步骤。' }
