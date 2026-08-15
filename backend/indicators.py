# -*- coding: utf-8 -*-
"""技术指标计算 (纯 pandas, 无第三方依赖)"""
import numpy as np
import pandas as pd


def _ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def compute_indicators(df):
    """输入日线 df (需含 open/close/high/low/volume/turnover),
    计算技术指标列并返回带指标的新 DataFrame (去 NaN 行)。"""
    df = df.copy()
    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]

    # --- 收益率 ---
    df["ret_1"] = c.pct_change() * 100
    df["ret_3"] = c.pct_change(3) * 100
    df["ret_5"] = c.pct_change(5) * 100
    df["ret_10"] = c.pct_change(10) * 100
    df["ret_20"] = c.pct_change(20) * 100

    # --- 均线及乖离率 ---
    for n in (5, 10, 20, 60):
        df[f"ma{n}"] = c.rolling(n).mean()
    df["ma5_ratio"] = c / df["ma5"] - 1
    df["ma10_ratio"] = c / df["ma10"] - 1
    df["ma20_ratio"] = c / df["ma20"] - 1
    df["ma60_ratio"] = c / df["ma60"] - 1

    # --- MACD (12,26,9) ---
    dif = _ema(c, 12) - _ema(c, 26)
    dea = _ema(dif, 9)
    df["macd_dif"] = dif
    df["macd_dea"] = dea
    df["macd_hist"] = (dif - dea) * 2

    # --- RSI (6/12/24) ---
    delta = c.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    for n in (6, 12, 24):
        avg_g = gain.ewm(alpha=1 / n, adjust=False).mean()
        avg_l = loss.ewm(alpha=1 / n, adjust=False).mean()
        rs = avg_g / avg_l.replace(0, np.nan)
        df[f"rsi{n}"] = 100 - 100 / (1 + rs)
    df["rsi6"] = df["rsi6"].fillna(50)

    # --- KDJ (9,3,3) ---
    low9 = l.rolling(9).min()
    high9 = h.rolling(9).max()
    rsv = (c - low9) / (high9 - low9).replace(0, np.nan) * 100
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    df["kdj_k"] = k
    df["kdj_d"] = d
    df["kdj_j"] = 3 * k - 2 * d

    # --- 量能 ---
    df["vol_ratio"] = v / v.rolling(5).mean().replace(0, np.nan)

    # --- 波动率 (20日收益标准差) ---
    df["volatility_20"] = df["ret_1"].rolling(20).std()

    # --- 价格在 20 日区间的位置 (0~1) ---
    rng = h.rolling(20).max() - l.rolling(20).min()
    df["close_pos_20"] = ((c - l.rolling(20).min()) / rng.replace(0, np.nan))

    # --- 价格距 52 周高/低的位置 ---
    hi52 = h.rolling(250).max()
    lo52 = l.rolling(250).min()
    df["price_position"] = ((c - lo52) / (hi52 - lo52).replace(0, np.nan))

    # --- 新增指标 (v3) ---
    # ATR(14) 平均真实波幅
    tr = pd.concat([
        h - l,
        (h - c.shift()).abs(),
        (l - c.shift()).abs(),
    ], axis=1).max(axis=1)
    df["atr14"] = tr.rolling(14).mean()

    # Williams %R(14)
    h14 = h.rolling(14).max()
    l14 = l.rolling(14).min()
    df["willr14"] = ((h14 - c) / (h14 - l14).replace(0, np.nan) * (-100))

    # CCI(20) 商品通道指数
    tp = (c + h + l) / 3
    ma20_tp = tp.rolling(20).mean()
    md = tp.rolling(20).std()
    df["cci20"] = (tp - ma20_tp) / md.replace(0, np.nan) / 0.015

    # Bollinger Band 宽度 (20,2)
    bb_mid = c.rolling(20).mean()
    bb_std = c.rolling(20).std()
    upper = bb_mid + 2 * bb_std
    lower = bb_mid - 2 * bb_std
    df["bb_width"] = ((upper - lower) / bb_mid)

    # ROC(12) 变动率
    df["roc12"] = c.pct_change(12) * 100

    # Donchian Channel (20) 位置
    dc20_h = h.rolling(20).max()
    dc20_l = l.rolling(20).min()
    df["dc_ratio"] = ((c - dc20_l) / (dc20_h - dc20_l).replace(0, np.nan))

    # OBV 信号 (On-Balance Volume 与 MA 的关系)
    obv = (v * ((c.diff() > 0).astype(int) * 2 - 1)).cumsum()
    df["obv_signal"] = (obv - obv.rolling(20).mean()) / obv.rolling(20).std().replace(0, np.nan)

    return df


def latest_feature_vector(df):
    """取 df 最后一行的特征向量, 返回 (features dict, ok)"""
    d = compute_indicators(df)
    if len(d) < 1:
        return None, False
    row = d.iloc[-1]
    feat = {}
    for col in _feature_list():
        val = row.get(col)
        if val is None or pd.isna(val):
            return None, False
        feat[col] = float(val)
    return feat, True


def _feature_list():
    from config import FEATURES
    return FEATURES
