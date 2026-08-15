# -*- coding: utf-8 -*-
"""A股数据获取。

优先使用腾讯行情 (K线/实时), 与东财接口分离:
- 腾讯 push2his/东财 push2his 历史K线接口可能被限流, 腾讯更稳定
- 搜索用东财股票代码表 (stock_info_a_code_name), 该接口稳定可用
"""
import time
import traceback
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache

import pandas as pd
import requests

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
       "Referer": "https://gu.qq.com/"}
TENCENT_KLINE = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
TENCENT_QUOTE = "https://qt.gtimg.cn/q={symbols}"

_lock = threading.Semaphore(4)  # 允许多线程并发获取, 限流4个并发


def _http_get(url, params):
    """带重试的 GET。每次新建 Session 并关闭 keep-alive,
    避免腾讯接口偶发的 SSL EOF (复用连接被服务端关闭)。"""
    last_err = None
    for attempt in range(4):
        try:
            with _lock:
                session = requests.Session()
                session.headers.update(_UA)
                session.headers["Connection"] = "close"
                try:
                    resp = session.get(url, params=params, timeout=12)
                finally:
                    session.close()
            if resp.status_code == 200:
                return resp
            last_err = RuntimeError(f"HTTP {resp.status_code}")
        except Exception as e:
            last_err = e
        time.sleep(0.8 * (attempt + 1))
    raise last_err


def _tencent_symbol(code):
    """6位代码 → 腾讯前缀 sh/sz/bj"""
    if code.startswith(("6", "688", "9")):
        return "sh" + code
    elif code.startswith(("0", "3", "1", "2")):
        return "sz" + code
    elif code.startswith(("4", "8", "92")):
        return "bj" + code
    return "sh" + code


@lru_cache(maxsize=256)
def fetch_daily(code, days=700):
    """获取前复权日线, 返回标准 df: date/open/close/high/low/volume/amount。
    优先使用 Sina (数据全、25年, 无严格限流), 腾讯备选。
    days 为拉取的最近交易日数量。"""
    # 转 Sina 前缀
    if code.startswith(("6", "688", "9")):
        sym = "sh" + code
    elif code.startswith(("0", "3", "1", "2")):
        sym = "sz" + code
    elif code.startswith(("4", "8", "92")):
        sym = "bj" + code
    else:
        sym = "sh" + code
    try:
        import akshare as ak
        df = ak.stock_zh_a_daily(symbol=sym, adjust="qfq")
    except Exception:
        df = None
    if df is not None and not df.empty:
        df = df[["date", "open", "high", "low", "close", "volume", "amount"]]
        df["date"] = pd.to_datetime(df["date"])
        for col in ["open", "close", "high", "low", "volume", "amount"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df.sort_values("date").reset_index(drop=True)
        if days is not None and len(df) > days:
            df = df.tail(days).reset_index(drop=True)
        return df

    # 备选: 腾讯 (仅当 Sina 失败时)
    return _fetch_tencent_daily(code, days)


def _fetch_tencent_daily(code, days):
    """腾讯 K线 (备选数据源)"""
    sym = _tencent_symbol(code)
    params = {"param": f"{sym},day,,,{max(days, 100)},qfq"}
    try:
        resp = _http_get(TENCENT_KLINE, params)
    except Exception:
        return pd.DataFrame()
    d = resp.json()
    node = (d.get("data") or {}).get(sym) or {}
    rows = node.get("qfqday") or node.get("day") or []
    if not rows:
        return pd.DataFrame()
    records = []
    for r in rows:
        try:
            amount = 0.0
            if len(r) > 6 and not isinstance(r[6], dict):
                try:
                    amount = float(r[6])
                except (ValueError, TypeError):
                    amount = 0.0
            records.append({
                "date": pd.Timestamp(r[0]),
                "open": float(r[1]), "close": float(r[2]),
                "high": float(r[3]), "low": float(r[4]),
                "volume": float(r[5]),
                "amount": amount,
            })
        except (ValueError, IndexError):
            continue
    df = pd.DataFrame(records)
    if df.empty:
        return df
    df = df.sort_values("date").reset_index(drop=True)
    if days is not None and len(df) > days:
        df = df.tail(days).reset_index(drop=True)
    return df


_code_name_cache = {"ts": 0, "df": None}


def _code_name_table():
    """全市场 代码→名称 表 (缓存 6 小时), 用于搜索和名称反查"""
    now = time.time()
    if _code_name_cache["df"] is None or now - _code_name_cache["ts"] > 6 * 3600:
        try:
            import akshare as ak
            df = ak.stock_info_a_code_name()
        except Exception:
            df = None
        _code_name_cache["df"] = df
        _code_name_cache["ts"] = now
    return _code_name_cache["df"]


def get_stock_name(code):
    df = _code_name_table()
    if df is not None and not df.empty:
        m = df[df["code"].astype(str) == str(code)]
        if not m.empty:
            return str(m.iloc[0]["name"])
    return ""


def search_stock(kw):
    """按代码关键字搜索 A 股 (仅匹配代码, 不匹配名称), 返回 [{code,name}]"""
    df = _code_name_table()
    if df is None or df.empty:
        return []
    df = df.astype(str)
    mask = df["code"].str.contains(kw, na=False)
    out = df[mask].head(15)
    return [{"code": r["code"], "name": r["name"]}
            for _, r in out.iterrows()]


def get_realtime(code):
    """获取实时行情快照 (腾讯), 返回 dict 或 None"""
    sym = _tencent_symbol(code)
    try:
        resp = _http_get(TENCENT_QUOTE.format(symbols=sym), None)
        resp.encoding = "gbk"
        line = resp.text.strip()
        s = line.find('"')
        e = line.rfind('"')
        if s == -1 or e == -1:
            return None
        parts = line[s + 1:e].split("~")
        if len(parts) < 38:
            return None

        def _f(i, default=0.0):
            try:
                return float(parts[i])
            except (ValueError, IndexError):
                return default

        return {
            "name": parts[1],
            "code": parts[2],
            "price": _f(3),
            "prev_close": _f(4),
            "open": _f(5),
            "change": _f(31),
            "change_pct": _f(32),
            "high": _f(33),
            "low": _f(34),
            "volume": _f(36),
            "amount": _f(37),
        }
    except Exception:
        return None


def safe_fetch_basket():
    """拉取训练篮子所有股票的日线, 并行拉取加速。返回 {code: df}"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    codes = get_training_basket()
    result = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {}
        for code in codes:
            fut = pool.submit(fetch_daily, code, 2000)
            futures[fut] = code
        for fut in as_completed(futures):
            code = futures[fut]
            try:
                df = fut.result()
                if df is not None and len(df) >= 100:
                    result[code] = df
            except Exception:
                pass
    return result


def get_training_basket():
    """返回训练用的股票代码列表 (沪深300成分股, 取前60只, 去重)。缓存 6 小时。"""
    import akshare as ak
    now = time.time()
    if (_basket_cache["ts"] and now - _basket_cache["ts"] < 6 * 3600
            and _basket_cache["codes"]):
        return _basket_cache["codes"]
    try:
        df = ak.index_stock_cons_csindex("000300")
        codes = sorted(set(str(c) for c in df["成分券代码"].tolist()))[:60]
    except Exception:
        from config import TRAIN_BASKET
        codes = list(TRAIN_BASKET)
    _basket_cache["codes"] = codes
    _basket_cache["ts"] = time.time()
    return codes


_basket_cache = {"ts": 0, "codes": []}
MAX_WORKERS = 2
