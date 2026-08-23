# 本仓库增强说明

本仓库以 `simonlin1212/a-stock-data` 为上游数据工具主体，并保留本仓库已经新增的研究增强。

## 保留的本地增强

### 1. 北交所 F10 下载器

目录：`tools/bse_f10_downloader/`

覆盖北交所股票列表、资产负债表、利润表、现金流量表、十大股东、十大流通股东、股东户数、分红送转、限售解禁等结构化数据；支持断点续传、JSONL、CSV、SQLite、日志与失败记录。

### 2. F10 开源接口源码固定版本备份

目录：`third_party/f10_sources/`

保存 AKShare、AxData、mootdx、gotdx 的固定提交清单及一键下载/克隆脚本，用于接口研究、灾备和复现；第三方项目仍分别受其自身许可证约束。

## 上游同步基线

- 上游：`simonlin1212/a-stock-data`
- 同步版本：V3.7.1
- 上游提交：`f90d67853b8108f13d286e1df20b357e2c5198a9`

同步原则：上游 `README.md`、`README_en.md`、`SKILL.md`、`CHANGELOG.md` 与新增核心资源保持最新；本仓库 `tools/`、`third_party/` 等本地增强不被覆盖。
