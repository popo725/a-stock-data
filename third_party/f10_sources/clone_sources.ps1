param(
    [string]$OutputDir = (Join-Path $PSScriptRoot "vendor")
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "没有找到 Git。请先安装 Git for Windows。"
}

$lockPath = Join-Path $PSScriptRoot "sources.lock.json"
$lock = Get-Content -Raw -Encoding UTF8 $lockPath | ConvertFrom-Json
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

foreach ($source in $lock.sources) {
    $target = Join-Path $OutputDir $source.name
    if (Test-Path $target) {
        Write-Host "删除旧目录：$target"
        Remove-Item -Recurse -Force $target
    }

    Write-Host "克隆 $($source.repository) ..."
    git clone --filter=blob:none --no-checkout "https://github.com/$($source.repository).git" $target
    if ($LASTEXITCODE -ne 0) { throw "git clone 失败：$($source.repository)" }

    git -C $target fetch --depth 1 origin $source.commit
    if ($LASTEXITCODE -ne 0) { throw "git fetch 失败：$($source.repository)" }

    git -C $target checkout --detach $source.commit
    if ($LASTEXITCODE -ne 0) { throw "git checkout 失败：$($source.repository)" }

    Write-Host "完成：$($source.name) $($source.commit.Substring(0, 7))"
}

Write-Host ""
Write-Host "全部固定版本源码已克隆到：$OutputDir"
