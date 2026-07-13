# 北交所 F10 下载器

这是一个面向个人研究的北交所 F10 数据下载工具，直接调用公开数据接口，不依赖 AKShare。

## 当前覆盖

| 数据集 | 内容 | 主要来源 |
|---|---|---|
| `stock_list` | 北交所股票代码、简称、上市日期、股本、行业、地区等 | 北交所官网 |
| `balance_sheet` | 各季度资产负债表公开字段（原始字段完整保留） | 东方财富数据中心 |
| `income_statement` | 各季度利润表公开字段（原始字段完整保留） | 东方财富数据中心 |
| `cashflow_statement` | 各季度现金流量表公开字段（原始字段完整保留） | 东方财富数据中心 |
| `top10_holders` | 历史十大股东 | 东方财富数据中心 |
| `top10_float_holders` | 历史十大流通股东 | 东方财富数据中心 |
| `holder_count` | 历史股东户数、户均持股等 | 东方财富数据中心 |
| `dividends` | 历史分红、送股、转增、股权登记日等 | 东方财富数据中心 |
| `restricted_shares` | 限售股解禁记录 | 东方财富数据中心 |

> “F10”不是统一标准。本工具先覆盖财务、股东、分红、股本解禁等核心结构化栏目。公告全文、主营构成、管理层、机构调研等可继续作为插件增加。

## 安装

在 Windows PowerShell 中进入仓库目录：

```powershell
cd tools\bse_f10_downloader
py -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\pip install -r requirements.txt
```

## 先做小规模测试

交易日或非交易日均可运行。第一次先测试 3 只股票：

```powershell
.\.venv\Scripts\python bse_f10_downloader.py `
  --output .\data_test `
  --max-stocks 3 `
  --start-year 2023
```

只测试指定股票：

```powershell
.\.venv\Scripts\python bse_f10_downloader.py `
  --output .\data_test `
  --codes 920002,920008 `
  --datasets stock_list,holder_count,dividends
```

## 全量下载

```powershell
.\.venv\Scripts\python bse_f10_downloader.py `
  --output D:\BSE_F10 `
  --start-year 2010
```

首次全量下载耗时取决于北交所股票数量和接口响应速度。程序默认每次请求间隔约 1.1 秒，避免给公开网站造成过大压力。

## 断点续传

程序按“股票/季度”保存独立 JSONL 分片：

```text
D:\BSE_F10
├─ parts
│  ├─ balance_sheet
│  │  ├─ 20240331.jsonl
│  │  └─ 20240630.jsonl
│  ├─ holder_count
│  │  ├─ 920002.jsonl
│  │  └─ 920008.jsonl
│  └─ ...
├─ merged
│  ├─ stock_list.csv
│  ├─ balance_sheet.csv
│  ├─ holder_count.csv
│  └─ ...
├─ bse_f10.sqlite
├─ manifest.json
└─ download.log
```

中途中断后重新运行，已经存在的分片会自动跳过。需要重新抓取时加：

```powershell
--refresh
```

## 常用参数

```text
--list-datasets       查看全部数据集
--datasets            只下载指定数据集，逗号分隔
--codes               只下载指定股票代码，逗号分隔
--max-stocks          限制股票数量，适合测试
--start-year          财务数据起始年份
--end-date            截止日期，格式 YYYYMMDD
--delay               请求间隔秒数，默认 1.1
--retries             失败重试次数，默认 4
--no-sqlite           只生成 CSV/JSONL，不生成 SQLite
--refresh             重新下载已有分片
--verbose             显示详细日志
```

查看完整帮助：

```powershell
python bse_f10_downloader.py --help
```

## 数据库使用

SQLite 数据库文件为：

```text
bse_f10.sqlite
```

表名与数据集名称一致，例如：

```sql
SELECT *
FROM holder_count
WHERE _download_code = '920002'
ORDER BY END_DATE DESC;
```

Python 查询示例：

```python
import sqlite3
import pandas as pd

with sqlite3.connect(r"D:\BSE_F10\bse_f10.sqlite") as conn:
    df = pd.read_sql_query(
        """
        SELECT *
        FROM top10_float_holders
        WHERE _download_code = ?
        """,
        conn,
        params=["920002"],
    )

print(df.head())
```

## 注意事项

1. 公开网页接口可能改字段或临时限制访问；原始 JSONL 会完整保留上游字段，便于以后重新解析。
2. 北交所证券代码曾经历代码切换，建议在正式合并维赛特数据库前建立新旧代码映射表。
3. 个别股票或历史季度可能确实没有数据；空结果不一定代表程序错误。
4. 请仅用于个人研究，遵守数据源网站条款，不要高频并发、转售或公开分发行情/财务数据。
5. 若东方财富出现空响应或连接重置，请降低速度，例如 `--delay 2.0`，稍后重试。
