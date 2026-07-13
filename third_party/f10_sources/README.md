# F10 开源接口源码备份清单

本目录保存的是**固定提交版本清单和一键备份脚本**，不是把第三方仓库的全部源码直接复制进当前仓库。

这样处理有三个好处：

1. 每个项目的许可证、提交历史和作者信息保持完整；
2. 当前仓库不会因为重复复制数万个第三方文件而迅速膨胀；
3. 根据 `sources.lock.json` 可以随时恢复同一提交版本，避免上游更新后接口代码找不到。

## 一键下载源码压缩包

Windows PowerShell：

```powershell
cd third_party\f10_sources
powershell -ExecutionPolicy Bypass -File .\download_sources.ps1
```

下载结果：

```text
archives/
├─ AKShare-fcdbf25.zip
├─ AxData-9ce545a.zip
├─ mootdx-e99ae34.zip
└─ gotdx-25c9fae.zip
```

## 一键克隆固定提交

电脑已安装 Git 时运行：

```powershell
cd third_party\f10_sources
powershell -ExecutionPolicy Bypass -File .\clone_sources.ps1
```

克隆结果位于：

```text
vendor/
```

每个目录都会检出 `sources.lock.json` 中固定的 commit，而不是不确定的最新版本。

## 使用边界

- 第三方项目仍分别受其自身 LICENSE 和网站数据条款约束。
- 当前仓库的北交所下载器是重新编写的独立工具，没有直接复制这些项目的大段实现。
- 这些源码只作为接口研究和灾备参考；公开网页接口变化后，应先查看上游项目的新提交和 issue。
