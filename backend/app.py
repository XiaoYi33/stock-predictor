# -*- coding: utf-8 -*-
"""股票涨跌预测 Web 服务"""
import time

from flask import Flask, jsonify, request

import data_fetch
import indicators
import model as model_mod
import analysis as analysis_mod
from config import HORIZONS, HORIZON_NAMES, MIN_BARS

app = Flask(__name__)


@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


@app.route("/api/ping")
def api_ping():
    return jsonify({"ok": True})

# 启动时后台训练模型 (只训练一次, 后续走缓存)
model_mod.ensure_models()


@app.route("/api/search")
def api_search():
    kw = request.args.get("kw", "").strip()
    if not kw:
        return jsonify({"items": []})
    return jsonify({"items": data_fetch.search_stock(kw)})


@app.route("/api/model/status")
def api_model_status():
    return jsonify(model_mod.get_status())


@app.route("/api/model/train", methods=["POST"])
def api_model_train():
    threading_trigger()
    return jsonify(model_mod.get_status())


def threading_trigger():
    import threading
    t = threading.Thread(target=model_mod.train_models, args=(True,),
                         daemon=True)
    t.start()


@app.route("/api/stock/<code>")
def api_stock(code):
    """单只股票: 实时行情 + 技术指标 + 多周期涨跌预测"""
    code = code.strip()
    if not code.isdigit() or len(code) != 6:
        return jsonify({"error": "请输入6位股票代码"}), 400

    realtime = data_fetch.get_realtime(code)
    name = (realtime or {}).get("name") or data_fetch.get_stock_name(code)
    if not name:
        return jsonify({"error": f"未找到股票 {code}, 请检查代码"}), 404

    # 指标 + 信号
    df = data_fetch.fetch_daily(code, days=300)
    if df is None or len(df) < MIN_BARS:
        return jsonify({"error": f"{code} 历史数据不足"}), 400
    ind = indicators.compute_indicators(df)
    sig = _compute_signals(ind, df)

    # 预测 (模型未就绪时抛错)
    try:
        preds = model_mod.predict_stock(code)
    except Exception as e:
        return jsonify({"error": str(e)}), 503

    payload = {
        "code": code,
        "name": name,
        "realtime": realtime,
        "last_close": float(df["close"].iloc[-1]),
        "last_date": str(df["date"].iloc[-1].date()),
        "predictions": {
            str(h): {
                "horizon": HORIZON_NAMES[h],
                **preds[h],
            } for h in HORIZONS
        },
        "indicators": {
            "ma5": _round(ind, "ma5"),
            "ma10": _round(ind, "ma10"),
            "ma20": _round(ind, "ma20"),
            "ma60": _round(ind, "ma60"),
            "macd_dif": _round(ind, "macd_dif"),
            "macd_dea": _round(ind, "macd_dea"),
            "macd_hist": _round(ind, "macd_hist"),
            "rsi6": _round(ind, "rsi6"),
            "rsi12": _round(ind, "rsi12"),
            "rsi24": _round(ind, "rsi24"),
            "kdj_k": _round(ind, "kdj_k"),
            "kdj_d": _round(ind, "kdj_d"),
            "kdj_j": _round(ind, "kdj_j"),
            "vol_ratio": _round(ind, "vol_ratio"),
            "volatility_20": _round(ind, "volatility_20"),
        },
        "signals": sig,
    }
    return jsonify(payload)


@app.route("/api/stock/<code>/kline")
def api_kline(code):
    """K线数据, days 参数控制返回最近多少根"""
    days = request.args.get("days", 250, type=int)
    df = data_fetch.fetch_daily(code.strip(), days=days)
    if df is None or df.empty:
        return jsonify({"error": "无数据"}), 404
    dates = [str(d.date()) for d in df["date"]]
    klines = [list(map(float, r)) for r in df[["open", "close",
                                               "low", "high"]].values]
    vols = [float(v) for v in df["volume"]]
    # 附上均线, 前端画线
    ind = indicators.compute_indicators(df)
    ma5 = _na_list(ind.get("ma5", []))
    ma20 = _na_list(ind.get("ma20", []))
    ma60 = _na_list(ind.get("ma60", []))
    return jsonify({
        "code": code, "dates": dates, "klines": klines,
        "volumes": vols, "ma5": ma5, "ma20": ma20, "ma60": ma60,
    })


@app.route("/api/stock/<code>/analysis")
def api_analysis(code):
    """市场指数 + 板块涨跌 + 个股所属板块 + 综合文字分析"""
    code = code.strip()
    if not code.isdigit() or len(code) != 6:
        return jsonify({"error": "请输入6位股票代码"}), 400
    try:
        preds = model_mod.predict_stock(code)
    except Exception as e:
        return jsonify({"error": str(e)}), 503

    # 技术信号 (用于分析文本)
    df = data_fetch.fetch_daily(code, days=300)
    signals = []
    if df is not None and len(df) >= MIN_BARS:
        ind = indicators.compute_indicators(df)
        signals = _compute_signals(ind, df)

    try:
        result = analysis_mod.build_analysis(
            code, {str(h): v for h, v in preds.items()}, signals)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"分析生成失败: {e}"}), 500


@app.route("/api/stock/<code>/backtest")
def api_backtest(code):
    """近 N 日预估准确率回测 (默认近20个交易日, 1日预测周期)"""
    code = code.strip()
    days = request.args.get("days", 20, type=int)
    if not code.isdigit() or len(code) != 6:
        return jsonify({"error": "请输入6位股票代码"}), 400
    try:
        return jsonify(model_mod.backtest(code, days=days, horizon=1))
    except Exception as e:
        return jsonify({"error": str(e)}), 503


def _round(series, col):
    """取 series 最后一行的列值, 保留 2 位小数"""
    try:
        v = series[col].iloc[-1]
        if v is None or pd_isna(v):
            return 0.0
        return round(float(v), 2)
    except Exception:
        return 0.0


def _na_list(series):
    import math
    out = []
    for v in series.tolist():
        out.append(round(float(v), 2) if not math.isnan(v) else None)
    return out


def pd_isna(v):
    import pandas as pd
    try:
        return pd.isna(v)
    except Exception:
        return False


def _compute_signals(ind, df):
    """生成几条可读的技术信号, 供前端展示"""
    import numpy as np
    sig = []
    last = ind.iloc[-1]
    prev = ind.iloc[-2] if len(ind) >= 2 else last

    def add(label, value, pos, neg):
        sig.append({"label": label, "text": value, "sentiment":
                    "positive" if pos else ("negative" if neg else "neutral")})

    close = df["close"].iloc[-1]
    ma20 = last.get("ma20")
    if ma20 and not np.isnan(ma20):
        if close > ma20:
            add("均线", f"股价站上20日均线 ({ma20:.2f})", True, False)
        else:
            add("均线", f"股价跌破20日均线 ({ma20:.2f})", False, True)

    dif, dea = last.get("macd_dif"), last.get("macd_dea")
    if dif is not None and dea is not None and not np.isnan(dif):
        p_dif, p_dea = prev.get("macd_dif"), prev.get("macd_dea")
        if p_dif <= p_dea and dif > dea:
            add("MACD", "DIF 上穿 DEA (金叉)", True, False)
        elif p_dif >= p_dea and dif < dea:
            add("MACD", "DIF 下穿 DEA (死叉)", False, True)
        elif dif > dea:
            add("MACD", "DIF 位于 DEA 上方 (多头)", True, False)
        else:
            add("MACD", "DIF 位于 DEA 下方 (空头)", False, True)

    rsi6 = last.get("rsi6")
    if rsi6 is not None and not np.isnan(rsi6):
        if rsi6 > 80:
            add("RSI6", f"RSI6={rsi6:.1f} 超买区间", False, True)
        elif rsi6 < 20:
            add("RSI6", f"RSI6={rsi6:.1f} 超卖区间", True, False)
        elif rsi6 > 50:
            add("RSI6", f"RSI6={rsi6:.1f} 偏强", True, False)
        else:
            add("RSI6", f"RSI6={rsi6:.1f} 偏弱", False, True)

    k, d = last.get("kdj_k"), last.get("kdj_d")
    if k is not None and d is not None and not np.isnan(k):
        p_k, p_d = prev.get("kdj_k"), prev.get("kdj_d")
        if p_k <= p_d and k > d:
            add("KDJ", "K 上穿 D (金叉)", True, False)
        elif p_k >= p_d and k < d:
            add("KDJ", "K 下穿 D (死叉)", False, True)
        else:
            add("KDJ", f"K={k:.1f} D={d:.1f}", k > d, k < d)

    vol_ratio = last.get("vol_ratio")
    if vol_ratio is not None and not np.isnan(vol_ratio):
        if vol_ratio > 1.5:
            add("量能", f"放量 {vol_ratio:.2f}倍", True, False)
        elif vol_ratio < 0.5:
            add("量能", f"缩量 {vol_ratio:.2f}倍", False, False)
        else:
            add("量能", f"量能 {vol_ratio:.2f}倍", False, False)

    return sig


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
