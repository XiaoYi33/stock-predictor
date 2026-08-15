# -*- coding: utf-8 -*-
"""市场与板块分析: 大盘指数 + 板块涨跌 + 个股所属板块 + 规则化分析"""

import time

import requests

import data_fetch

# 大盘指数 (腾讯代码, 显示名)
MARKET_INDICES = [
    ("sh000001", "上证指数"),
    ("sz399001", "深证成指"),
    ("sz399006", "创业板指"),
    ("sh000688", "科创50"),
    ("sh000300", "沪深300"),
]

_THS_CACHE = {"ts": 0, "data": []}
_F10_CACHE = {}
_INDEX_CACHE = {"ts": 0, "data": None}


def fetch_market_indices():
    """腾讯: 各大盘指数今日涨跌 (缓存60秒)"""
    now = time.time()
    if _INDEX_CACHE["data"] is not None and now - _INDEX_CACHE["ts"] < 60:
        return _INDEX_CACHE["data"]
    symbols = ",".join(s for s, _ in MARKET_INDICES)
    resp = data_fetch._http_get(data_fetch.TENCENT_QUOTE.format(symbols=symbols), None)
    resp.encoding = "gbk"
    out = []
    for line in resp.text.strip().split("\n"):
        s = line.find('"')
        e = line.rfind('"')
        if s == -1 or e == -1:
            continue
        parts = line[s + 1:e].split("~")
        if len(parts) < 33:
            continue
        code = parts[2]
        full = [sym for sym, _ in MARKET_INDICES if sym.endswith(code)]
        if not full:
            continue
        name = dict(MARKET_INDICES)[full[0]]
        try:
            out.append({"name": name, "price": float(parts[3]),
                        "change_pct": float(parts[32])})
        except (ValueError, IndexError):
            continue
    _INDEX_CACHE["ts"] = now
    _INDEX_CACHE["data"] = out
    return out


def fetch_sector_summary():
    """同花顺: 全部行业板块今日涨跌 (缓存5分钟)。返回 [{name, change_pct}]"""
    now = time.time()
    if _THS_CACHE["data"] and now - _THS_CACHE["ts"] < 300:
        return _THS_CACHE["data"]
    try:
        import akshare as ak
        df = ak.stock_board_industry_summary_ths()
        name_col = df.columns[1]
        chg_col = df.columns[2]
        rows = []
        for _, r in df.iterrows():
            try:
                rows.append({"name": str(r[name_col]),
                             "change_pct": float(r[chg_col])})
            except (ValueError, TypeError):
                continue
        if rows:
            _THS_CACHE["data"] = rows
            _THS_CACHE["ts"] = now
        return rows
    except Exception:
        return _THS_CACHE["data"]


def get_stock_industry(code):
    """东财F10: 个股所属行业 (EM2016 三级分类)。返回 {'full','primary'} 或 None"""
    if code in _F10_CACHE:
        return _F10_CACHE[code]
    prefix = "SH" if code.startswith(("6", "9")) else "SZ"
    url = (f"https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/"
           f"PageAjax?code={prefix}{code}")
    result = None
    try:
        r = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://emweb.securities.eastmoney.com/"})
        d = r.json()
        jbzl = d.get("jbzl") or []
        if jbzl:
            em = str(jbzl[0].get("EM2016", "") or "")
            if em:
                parts = [p.strip() for p in em.split("-") if p.strip()]
                result = {"full": em,
                          "primary": parts[-1] if parts else em}
    except Exception:
        result = None
    _F10_CACHE[code] = result
    return result


def match_sector(industry, sector_rows):
    """把个股行业匹配到同花顺板块涨跌。返回 dict 或 None"""
    if not industry:
        return None
    primary = industry["primary"]
    if not primary:
        return None
    for r in sector_rows:
        if r["name"] == primary:
            return {"name": primary, "change_pct": r["change_pct"]}
    for r in sector_rows:
        if primary in r["name"] or r["name"] in primary:
            return {"name": primary, "change_pct": r["change_pct"]}
    return {"name": primary, "change_pct": None}


def _avg_change(items):
    vals = [i["change_pct"] for i in items if i.get("change_pct") is not None]
    return sum(vals) / len(vals) if vals else 0.0


def generate_analysis(market, sector_of_stock, sector_rows, predictions, signals):
    """规则化生成分析文本。返回 dict: {summary, points[], sentiment}"""
    points = []
    sentiment = 0.0

    # 1. 大盘氛围
    if market:
        avg = _avg_change(market)
        strong = sum(1 for m in market if m["change_pct"] > 0)
        if avg > 0.3 and strong >= 3:
            points.append(f"今日大盘整体偏强, {strong}/{len(market)} 个主要指数上涨 (平均 +{avg:.2f}%)")
            sentiment += 1
        elif avg < -0.3 and strong <= 2:
            points.append(f"今日大盘整体偏弱, 仅 {strong}/{len(market)} 个主要指数上涨 (平均 {avg:.2f}%)")
            sentiment -= 1
        else:
            points.append(f"今日大盘窄幅震荡, {strong}/{len(market)} 个主要指数上涨 (平均 {avg:+.2f}%)")

    # 2. 所属板块
    if sector_of_stock and sector_of_stock.get("change_pct") is not None:
        chg = sector_of_stock["change_pct"]
        if chg > 1:
            points.append(f"所属板块「{sector_of_stock['name']}」今日 +{chg:.2f}%, 明显跑赢大盘")
            sentiment += 1
        elif chg < -1:
            points.append(f"所属板块「{sector_of_stock['name']}」今日 {chg:.2f}%, 弱于大盘")
            sentiment -= 1
        else:
            points.append(f"所属板块「{sector_of_stock['name']}」今日 {chg:+.2f}%, 与大盘同步")
    elif sector_of_stock:
        points.append(f"该股属于「{sector_of_stock['name']}」板块")

    # 3. 板块热点
    if sector_rows:
        gainers = sorted(sector_rows, key=lambda r: r["change_pct"], reverse=True)[:3]
        losers = sorted(sector_rows, key=lambda r: r["change_pct"])[:3]
        if gainers and gainers[0]["change_pct"] > 1:
            hot = "、".join(f"{g['name']}({g['change_pct']:+.1f}%)" for g in gainers)
            points.append(f"今日领涨板块: {hot}")
        if losers and losers[0]["change_pct"] < -1:
            weak = "、".join(f"{g['name']}({g['change_pct']:+.1f}%)" for g in losers)
            points.append(f"今日领跌板块: {weak}")

    # 4. 技术信号
    if signals:
        pos = [s for s in signals if s["sentiment"] == "positive"]
        neg = [s for s in signals if s["sentiment"] == "negative"]
        if pos and not neg:
            points.append(f"技术面偏多: {pos[0]['text']}等")
            sentiment += 1
        elif neg and not pos:
            points.append(f"技术面偏空: {neg[0]['text']}等")
            sentiment -= 1
        elif pos or neg:
            points.append(f"技术面多空交织 (多头信号{len(pos)}个, 空头信号{len(neg)}个)")

    # 5. 模型预测
    if predictions:
        def _p(key):
            item = predictions.get(key) or predictions.get(str(key)) or {}
            return item.get("prob_up")
        p1 = _p(1)
        p5 = _p(5)
        p20 = _p(20)
        if p1 is not None:
            points.append(f"模型预测: 未来1日上涨概率 {p1:.0f}%, "
                          f"5日 {p5:.0f}%, 20日 {p20:.0f}%")
        if p20 is not None and p20 >= 60:
            points.append("中期(20日)模型信号偏多")
            sentiment += 1
        elif p20 is not None and p20 <= 40:
            points.append("中期(20日)模型信号偏空")
            sentiment -= 1

    # 综合结论
    if sentiment >= 3:
        summary = "综合来看, 市场氛围、所属板块与技术面共振偏多, 短期走势或偏强。"
        verdict = "偏多"
    elif sentiment <= -2:
        summary = "综合来看, 大盘与板块偏弱且技术面承压, 短期需谨慎。"
        verdict = "偏空"
    elif sentiment >= 1:
        summary = "综合来看, 多因素略偏积极, 但需注意板块轮动风险。"
        verdict = "中性偏多"
    elif sentiment <= -1:
        summary = "综合来看, 多因素略偏消极, 建议观望。"
        verdict = "中性偏空"
    else:
        summary = "综合来看, 多空因素均衡, 短期或以震荡为主。"
        verdict = "中性"

    return {
        "summary": summary,
        "points": points,
        "sentiment": verdict,
        "sentiment_score": sentiment,
    }


def build_analysis(code, predictions, signals):
    """组装 /analysis 接口所需完整数据"""
    market = fetch_market_indices()
    sector_rows = fetch_sector_summary()
    industry = get_stock_industry(code)
    sector_of_stock = match_sector(industry, sector_rows)
    analysis = generate_analysis(
        market, sector_of_stock, sector_rows, predictions, signals)
    return {
        "market": market,
        "industry": industry,
        "sector": sector_of_stock,
        "sector_top": sorted(sector_rows, key=lambda r: r["change_pct"],
                             reverse=True)[:5] if sector_rows else [],
        "sector_bottom": sorted(sector_rows, key=lambda r: r["change_pct"])[:5]
                         if sector_rows else [],
        "analysis": analysis,
    }
