param(
    [string]$OutputDir = (Join-Path $PSScriptRoot "archives")
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$lockPath = Join-Path $PSScriptRoot "sources.lock.json"
$lock = Get-Content -Raw -Encoding UTF8 $lockPath | ConvertFrom-Json
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

foreach ($source in $lock.sources) {
    $short = $source.commit.Substring(0, 7)
    $safeName = ($source.name -replace '[^A-Za-z0-9._-]', '_')
    $target = Join-Path $OutputDir "$safeName-$short.zip"
    $url = "https://github.com/$($source.repository)/archive/$($source.commit).zip"

    Write-Host "下载 $($source.name) $short ..."
    Invoke-WebRequest -Uri $url -OutFile $target -UseBasicParsing
    Write-Host "已保存：$target"
}

Write-Host ""
Write-Host "全部源码压缩包下载完成。"
