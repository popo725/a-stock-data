#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""北交所 F10 下载器：断点续传、CSV、SQLite。"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from bse_f10_api import (
    BSE_MARKET_CODE,
    DATASET_SPECS,
    RateLimitedSession,
    eastmoney_pages,
    fetch_bse_stock_list,
    iso_date,
    quarter_ends,
)

VERSION = "0.1.0"
LOGGER = logging.getLogger("bse_f10")
DEFAULT_DATASETS = [
    "stock_list", "balance_sheet", "income_statement", "cashflow_statement",
    "top10_holders", "top10_float_holders", "holder_count",
    "dividends", "restricted_shares",
]


def setup_logging(output_dir: Path, verbose: bool) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(output_dir / "download.log", encoding="utf-8"),
        ],
        force=True,
    )


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    count = 0
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, default=str) + "\n")
            count += 1
    temp.replace(path)
    return count


def read_jsonl_files(files: Sequence[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in files:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    LOGGER.warning("忽略损坏的 JSONL 行：%s", path)
                    continue
                if isinstance(value, dict):
                    rows.append(value)
    return pd.DataFrame(rows)


def write_outputs(output_dir: Path, dataset: str, frame: pd.DataFrame, sqlite_enabled: bool) -> None:
    merged = output_dir / "merged"
    merged.mkdir(parents=True, exist_ok=True)
    csv_path = merged / f"{dataset}.csv"
    frame.to_csv(csv_path, index=False, encoding="utf-8-sig")
    if sqlite_enabled and len(frame.columns):
        with sqlite3.connect(output_dir / "bse_f10.sqlite") as connection:
            frame.to_sql(dataset, connection, if_exists="replace", index=False)
    LOGGER.info("%s：合并 %s 行，输出 %s", dataset, len(frame), csv_path)


def save_stock_list(
    output_dir: Path,
    rows: Sequence[Mapping[str, Any]],
    sqlite_enabled: bool,
) -> pd.DataFrame:
    part = output_dir / "parts" / "stock_list" / "stock_list.jsonl"
    write_jsonl(part, rows)
    frame = pd.DataFrame(rows)
    write_outputs(output_dir, "stock_list", frame, sqlite_enabled)
    return frame


def run_quarter_dataset(
    client: RateLimitedSession,
    name: str,
    quarters: Sequence[str],
    output_dir: Path,
    refresh: bool,
    sqlite_enabled: bool,
) -> dict[str, Any]:
    spec = DATASET_SPECS[name]
    part_dir = output_dir / "parts" / name
    part_dir.mkdir(parents=True, exist_ok=True)
    failures: list[dict[str, str]] = []

    for index, quarter in enumerate(quarters, 1):
        part = part_dir / f"{quarter}.jsonl"
        if part.exists() and not refresh:
            LOGGER.info("%s %s 已存在，跳过", name, quarter)
            continue
        try:
            rows = eastmoney_pages(client, {
                "sortColumns": spec.sort_columns,
                "sortTypes": spec.sort_types,
                "reportName": spec.report_name,
                "columns": spec.columns,
                "quoteColumns": spec.quote_columns,
                "filter": (
                    f'(TRADE_MARKET_CODE="{BSE_MARKET_CODE}")'
                    f"(REPORT_DATE='{iso_date(quarter)}')"
                ),
            })
            now = datetime.now().isoformat(timespec="seconds")
            stamped = [
                {
                    **row,
                    "_dataset": name,
                    "_report_date": quarter,
                    "_source": "eastmoney_datacenter",
                    "_downloaded_at": now,
                }
                for row in rows
            ]
            write_jsonl(part, stamped)
            LOGGER.info("%s：%s（%s/%s）%s 行", name, quarter, index, len(quarters), len(stamped))
        except Exception as exc:
            LOGGER.exception("%s %s 下载失败", name, quarter)
            failures.append({"key": quarter, "error": str(exc)})

    frame = read_jsonl_files(sorted(part_dir.glob("*.jsonl")))
    write_outputs(output_dir, name, frame, sqlite_enabled)
    return {"rows": len(frame), "failures": failures}


def run_stock_dataset(
    client: RateLimitedSession,
    name: str,
    stocks: Sequence[Mapping[str, Any]],
    output_dir: Path,
    refresh: bool,
    sqlite_enabled: bool,
) -> dict[str, Any]:
    spec = DATASET_SPECS[name]
    part_dir = output_dir / "parts" / name
    part_dir.mkdir(parents=True, exist_ok=True)
    failures: list[dict[str, str]] = []

    for index, stock in enumerate(stocks, 1):
        code = str(stock.get("security_code") or "")
        stock_name = str(stock.get("security_name") or "")
        part = part_dir / f"{code}.jsonl"
        if part.exists() and not refresh:
            LOGGER.info("%s %s 已存在，跳过", name, code)
            continue
        try:
            rows = eastmoney_pages(client, {
                "sortColumns": spec.sort_columns,
                "sortTypes": spec.sort_types,
                "reportName": spec.report_name,
                "columns": spec.columns,
                "quoteColumns": spec.quote_columns,
                "filter": f'(SECURITY_CODE="{code}")',
            })
            now = datetime.now().isoformat(timespec="seconds")
            stamped = [
                {
                    **row,
                    "_download_code": code,
                    "_download_name": stock_name,
                    "_dataset": name,
                    "_source": "eastmoney_datacenter",
                    "_downloaded_at": now,
                }
                for row in rows
            ]
            write_jsonl(part, stamped)
            LOGGER.info(
                "%s：%s %s（%s/%s）%s 行",
                name, code, stock_name, index, len(stocks), len(stamped),
            )
        except Exception as exc:
            LOGGER.exception("%s %s 下载失败", name, code)
            failures.append({"key": code, "name": stock_name, "error": str(exc)})

    frame = read_jsonl_files(sorted(part_dir.glob("*.jsonl")))
    write_outputs(output_dir, name, frame, sqlite_enabled)
    return {"rows": len(frame), "failures": failures}


def choose_stocks(
    rows: Sequence[Mapping[str, Any]],
    codes: Sequence[str],
    max_stocks: int | None,
) -> list[dict[str, Any]]:
    selected = [dict(row) for row in rows]
    if codes:
        wanted = {code.strip() for code in codes if code.strip()}
        selected = [row for row in selected if row.get("security_code") in wanted]
        missing = sorted(wanted - {str(row.get("security_code")) for row in selected})
        if missing:
            LOGGER.warning("未在当前北交所列表中找到：%s", ",".join(missing))
    if max_stocks is not None:
        selected = selected[:max(0, max_stocks)]
    return selected


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="下载北交所核心 F10 数据到 CSV/SQLite")
    parser.add_argument("--output", default="data/bse_f10")
    parser.add_argument("--datasets", default=",".join(DEFAULT_DATASETS))
    parser.add_argument("--list-datasets", action="store_true")
    parser.add_argument("--start-year", type=int, default=2010)
    parser.add_argument("--end-date", default=date.today().strftime("%Y%m%d"))
    parser.add_argument("--codes", default="")
    parser.add_argument("--max-stocks", type=int)
    parser.add_argument("--delay", type=float, default=1.1)
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--retries", type=int, default=4)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--no-sqlite", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser.parse_args()


def validate_datasets(raw: str) -> list[str]:
    supported = {"stock_list", *DATASET_SPECS}
    result: list[str] = []
    for item in raw.split(","):
        name = item.strip()
        if not name:
            continue
        if name not in supported:
            raise SystemExit(f"未知数据集 {name}；支持：{', '.join(sorted(supported))}")
        if name not in result:
            result.append(name)
    return result


def main() -> int:
    args = parse_args()
    supported = ["stock_list", *DATASET_SPECS]
    if args.list_datasets:
        print("\n".join(supported))
        return 0

    output_dir = Path(args.output).expanduser().resolve()
    setup_logging(output_dir, args.verbose)
    try:
        end_day = datetime.strptime(args.end_date, "%Y%m%d").date()
    except ValueError:
        LOGGER.error("--end-date 必须使用 YYYYMMDD")
        return 2
    if not 1990 <= args.start_year <= end_day.year:
        LOGGER.error("--start-year 不合理")
        return 2

    datasets = validate_datasets(args.datasets)
    client = RateLimitedSession(args.delay, args.timeout, args.retries)
    sqlite_enabled = not args.no_sqlite
    manifest: dict[str, Any] = {
        "version": VERSION,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "datasets": datasets,
        "results": {},
    }

    try:
        stock_rows = fetch_bse_stock_list(client)
    except Exception:
        LOGGER.exception("北交所股票列表下载失败")
        return 1

    stock_frame = save_stock_list(output_dir, stock_rows, sqlite_enabled)
    stocks = choose_stocks(
        stock_rows,
        args.codes.split(",") if args.codes else [],
        args.max_stocks,
    )
    manifest["stock_count"] = len(stock_frame)
    LOGGER.info("本次处理 %s 只股票", len(stocks))
    quarters = list(quarter_ends(args.start_year, end_day))

    for name in datasets:
        if name == "stock_list":
            manifest["results"][name] = {"rows": len(stock_frame), "failures": []}
        elif DATASET_SPECS[name].mode == "quarter":
            manifest["results"][name] = run_quarter_dataset(
                client, name, quarters, output_dir, args.refresh, sqlite_enabled
            )
        else:
            manifest["results"][name] = run_stock_dataset(
                client, name, stocks, output_dir, args.refresh, sqlite_enabled
            )

    manifest["finished_at"] = datetime.now().isoformat(timespec="seconds")
    manifest["failure_count"] = sum(
        len(value.get("failures", []))
        for value in manifest["results"].values()
        if isinstance(value, Mapping)
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    LOGGER.info("任务完成，失败项：%s", manifest["failure_count"])
    return 0 if manifest["failure_count"] == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
