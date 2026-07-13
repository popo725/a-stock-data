# -*- coding: utf-8 -*-
"""北交所 F10 公开接口适配层。"""

from __future__ import annotations

import json
import logging
import random
import re
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterator, Mapping, Sequence

import requests

LOGGER = logging.getLogger("bse_f10")
EASTMONEY_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
BSE_LIST_URL = "https://www.bse.cn/nqxxController/nqxxCnzq.do"
BSE_MARKET_CODE = "069001017"


@dataclass(frozen=True)
class DatasetSpec:
    report_name: str
    mode: str
    sort_columns: str
    sort_types: str
    columns: str = "ALL"
    quote_columns: str = ""


DATASET_SPECS: dict[str, DatasetSpec] = {
    "balance_sheet": DatasetSpec(
        "RPT_DMSK_FN_BALANCE", "quarter", "NOTICE_DATE,SECURITY_CODE", "-1,-1"
    ),
    "income_statement": DatasetSpec(
        "RPT_DMSK_FN_INCOME", "quarter", "NOTICE_DATE,SECURITY_CODE", "-1,-1"
    ),
    "cashflow_statement": DatasetSpec(
        "RPT_DMSK_FN_CASHFLOW", "quarter", "NOTICE_DATE,SECURITY_CODE", "-1,-1"
    ),
    "top10_holders": DatasetSpec(
        "RPT_CUSTOM_DMSK_HOLDERS_JOIN_HOLDER_SHAREANALYSIS",
        "stock", "END_DATE,RANK", "-1,1",
        "ALL;D10_ADJCHRATE,D30_ADJCHRATE,D60_ADJCHRATE",
    ),
    "top10_float_holders": DatasetSpec(
        "RPT_CUSTOM_F10_EH_FREEHOLDERS_JOIN_FREEHOLDER_SHAREANALYSIS",
        "stock", "END_DATE,HOLDER_RANK", "-1,1",
        "ALL;D10_ADJCHRATE,D30_ADJCHRATE,D60_ADJCHRATE",
    ),
    "holder_count": DatasetSpec(
        "RPT_HOLDERNUM_DET", "stock", "END_DATE", "-1",
        (
            "SECURITY_CODE,SECURITY_NAME_ABBR,CHANGE_SHARES,CHANGE_REASON,END_DATE,"
            "INTERVAL_CHRATE,AVG_MARKET_CAP,AVG_HOLD_NUM,TOTAL_MARKET_CAP,"
            "TOTAL_A_SHARES,HOLD_NOTICE_DATE,HOLDER_NUM,PRE_HOLDER_NUM,"
            "HOLDER_NUM_CHANGE,HOLDER_NUM_RATIO,PRE_END_DATE"
        ),
        "f2,f3",
    ),
    "dividends": DatasetSpec(
        "RPT_SHAREBONUS_DET", "stock", "REPORT_DATE", "-1"
    ),
    "restricted_shares": DatasetSpec(
        "RPT_LIFT_STAGE", "stock", "FREE_DATE", "-1"
    ),
}


class DownloadError(RuntimeError):
    pass


class RateLimitedSession:
    def __init__(self, delay: float = 1.1, timeout: float = 20, retries: int = 4):
        self.delay = max(0.0, delay)
        self.timeout = max(1.0, timeout)
        self.retries = max(1, retries)
        self.last_at = 0.0
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/150.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })

    def _wait(self):
        target = self.delay + random.uniform(0, min(0.35, self.delay / 3 if self.delay else 0))
        elapsed = time.monotonic() - self.last_at
        if elapsed < target:
            time.sleep(target - elapsed)

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        last_error: Exception | None = None
        timeout = kwargs.pop("timeout", self.timeout)
        for attempt in range(1, self.retries + 1):
            self._wait()
            try:
                response = self.session.request(method, url, timeout=timeout, **kwargs)
                self.last_at = time.monotonic()
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_error = exc
                self.last_at = time.monotonic()
                if attempt == self.retries:
                    break
                pause = min(20.0, 1.8 ** attempt) + random.uniform(0, 0.5)
                LOGGER.warning("请求失败 %s/%s，%.1f 秒后重试：%s", attempt, self.retries, pause, exc)
                time.sleep(pause)
        raise DownloadError(f"请求最终失败：{url}；{last_error}") from last_error

    def get_json(self, url: str, **kwargs: Any) -> dict[str, Any]:
        response = self.request("GET", url, **kwargs)
        try:
            payload = response.json()
        except ValueError as exc:
            raise DownloadError(f"返回内容不是 JSON：{response.text[:300]}") from exc
        if not isinstance(payload, dict):
            raise DownloadError(f"JSON 顶层结构异常：{type(payload).__name__}")
        return payload


def extract_json_array(text: str) -> list[Any]:
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end < start:
        raise DownloadError(f"未找到 JSON 数组：{text[:200]}")
    try:
        payload = json.loads(text[start:end + 1])
    except json.JSONDecodeError as exc:
        raise DownloadError(f"北交所列表解析失败：{text[:200]}") from exc
    if not isinstance(payload, list):
        raise DownloadError("北交所列表不是数组")
    return payload


def normalize_bse_row(row: Any) -> dict[str, Any]:
    if isinstance(row, Mapping):
        def pick(*keys: str) -> Any:
            for key in keys:
                if row.get(key) not in (None, ""):
                    return row.get(key)
            return None
        result = {
            "security_code": str(pick("xxzqdm", "securityCode", "code", "证券代码") or "").strip(),
            "security_name": str(pick("xxzqjc", "securityName", "name", "证券简称") or "").strip(),
            "list_date": pick("xxssrq", "listDate", "上市日期"),
            "total_shares": pick("xxzgb", "totalShares", "总股本"),
            "float_shares": pick("xxltgb", "floatShares", "流通股本"),
            "industry": pick("xxhymc", "industry", "所属行业"),
            "region": pick("xxdq", "region", "地区"),
            "sponsor": pick("xxzqgs", "sponsor", "券商"),
            "report_date": pick("xxbgrq", "reportDate", "报告日期"),
        }
    elif isinstance(row, Sequence) and not isinstance(row, (str, bytes, bytearray)):
        values = list(row)
        at = lambda i: values[i] if i < len(values) else None
        result = {
            "security_code": str(at(38) or "").strip(),
            "security_name": str(at(40) or "").strip(),
            "list_date": at(0), "float_shares": at(11), "industry": at(17),
            "report_date": at(23), "region": at(29), "sponsor": at(35),
            "total_shares": at(36),
        }
    else:
        result = {"security_code": "", "security_name": ""}
    result["raw_json"] = json.dumps(row, ensure_ascii=False, default=str)
    return result


def fetch_bse_stock_list(client: RateLimitedSession) -> list[dict[str, Any]]:
    page, total_pages = 0, None
    rows: list[dict[str, Any]] = []
    while total_pages is None or page < total_pages:
        response = client.request(
            "POST", BSE_LIST_URL,
            data={
                "page": str(page), "typejb": "T", "xxfcbj[]": "2",
                "xxzqdm": "", "sortfield": "xxzqdm", "sorttype": "asc",
            },
            headers={"Referer": "https://www.bse.cn/nq/listedcompany.html"},
        )
        payload = extract_json_array(response.text)
        if not payload or not isinstance(payload[0], Mapping):
            raise DownloadError("北交所列表结构异常")
        root = payload[0]
        total_pages = int(root.get("totalPages") or 0)
        content = root.get("content") or []
        if not isinstance(content, list):
            raise DownloadError("北交所列表 content 结构异常")
        rows.extend(normalize_bse_row(item) for item in content)
        page += 1
        LOGGER.info("股票列表：第 %s/%s 页，累计 %s 条", page, total_pages, len(rows))

    unique = {
        row["security_code"]: row
        for row in rows
        if re.fullmatch(r"\d{6}", str(row.get("security_code", "")))
    }
    result = sorted(unique.values(), key=lambda x: x["security_code"])
    if not result:
        raise DownloadError("北交所股票列表为空")
    return result


def eastmoney_pages(client: RateLimitedSession, params: Mapping[str, Any]) -> list[dict[str, Any]]:
    query = {
        "pageSize": "500", "pageNumber": "1", "source": "WEB", "client": "WEB",
        **dict(params),
    }
    first = client.get_json(EASTMONEY_URL, params=query)
    result = first.get("result")
    if result is None:
        return []
    if not isinstance(result, Mapping):
        raise DownloadError("东方财富 result 结构异常")
    pages = int(result.get("pages") or 0)
    rows: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        if page == 1:
            current = result
        else:
            query["pageNumber"] = str(page)
            current = client.get_json(EASTMONEY_URL, params=query).get("result") or {}
        data = current.get("data") if isinstance(current, Mapping) else []
        if data:
            rows.extend(item for item in data if isinstance(item, dict))
    return rows


def quarter_ends(start_year: int, end_day: date) -> Iterator[str]:
    for year in range(start_year, end_day.year + 1):
        for suffix in ("0331", "0630", "0930", "1231"):
            value = f"{year}{suffix}"
            if datetime.strptime(value, "%Y%m%d").date() <= end_day:
                yield value


def iso_date(value: str) -> str:
    return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
