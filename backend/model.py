# -*- coding: utf-8 -*-
"""特征工程 + 多模型堆叠训练 + 预测"""
import os
import time
import pickle
import threading

import numpy as np
import pandas as pd
from sklearn.ensemble import (StackingClassifier, RandomForestClassifier,
                              ExtraTreesClassifier, AdaBoostClassifier)
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import xgboost as xgb

from config import (HORIZONS, MODEL_DIR, MODEL_TTL_SECONDS, MODEL_VERSION,
                    FEATURES, TRAIN_BASKET, MIN_BARS, BASE_MODELS)
import indicators
import data_fetch

_lock = threading.Lock()
_train_lock = threading.Lock()
_model_status = {"trained": False, "training": False,
                 "message": "未训练", "updated_at": 0}
_models = {}  # horizon -> StackingClassifier
_backtest_cache = {}  # (code, days, horizon) -> (timestamp, result)

_VERSION_FILE = os.path.join(MODEL_DIR, ".version")


def _model_path(horizon):
    return os.path.join(MODEL_DIR, f"stack_{horizon}d.pkl")


def _build_stacker():
    """构建堆叠模型: 5 个基础模型 (XGBoost GPU + 随机森林 + 极端随机树 + AdaBoost + 逻辑回归) + 逻辑回归元模型"""
    device = "cuda"
    base_estimators = [
        ("xgboost", xgb.XGBClassifier(
            n_estimators=100, max_depth=6, learning_rate=0.08,
            subsample=0.8, colsample_bytree=0.8,
            reg_lambda=1.0, reg_alpha=0.3,
            tree_method="hist", device=device,
            random_state=42, verbosity=0)),
        ("random_forest", RandomForestClassifier(
            n_estimators=100, max_depth=7, min_samples_leaf=30,
            n_jobs=-1, random_state=42)),
        ("extra_trees", ExtraTreesClassifier(
            n_estimators=100, max_depth=7, min_samples_leaf=30,
            n_jobs=-1, random_state=42)),
        ("adaboost", AdaBoostClassifier(
            n_estimators=100, learning_rate=0.5, random_state=42)),
        ("linear", Pipeline([
            ("scale", StandardScaler()),
            ("logit", LogisticRegression(C=1.0, max_iter=1000)),
        ])),
    ]
    return StackingClassifier(
        estimators=base_estimators,
        final_estimator=LogisticRegression(C=1.0, max_iter=1000),
        stack_method="predict_proba",
        cv=2, n_jobs=1, verbose=0,
    )


def _is_fresh():
    """磁盘上的模型是否齐全、未过期且版本一致"""
    now = time.time()
    if not os.path.exists(_VERSION_FILE):
        return False
    try:
        with open(_VERSION_FILE, "r") as f:
            if int(f.read().strip()) != MODEL_VERSION:
                return False
    except Exception:
        return False
    for h in HORIZONS:
        p = _model_path(h)
        if not os.path.exists(p):
            return False
        if now - os.path.getmtime(p) > MODEL_TTL_SECONDS:
            return False
    return True


def _build_samples(df):
    """从单只股票的日线构造样本: 每个交易日一行特征 + 各 horizon 的上涨标签。
    返回 (features, labels_per_horizon), features 为 list[list[float]]。"""
    d = indicators.compute_indicators(df)
    closes = d["close"].values
    n = len(d)
    max_h = max(HORIZONS)
    samples = []
    for i in range(0, n - max_h):
        row = d.iloc[i]
        feats = []
        ok = True
        for col in FEATURES:
            val = row.get(col)
            if val is None or pd.isna(val):
                ok = False
                break
            feats.append(float(val))
        if not ok:
            continue
        cur = closes[i]
        labels = {}
        for h in HORIZONS:
            fut = closes[i + h]
            labels[h] = 1 if fut > cur else 0
        samples.append((feats, labels))
    return samples


def train_models(force=False):
    """训练所有 horizon 的模型。篮子数据全部拉取后训练并保存。"""
    with _train_lock:
        if _model_status["training"]:
            return
        if not force and _is_fresh():
            return

        _model_status.update(trained=False, training=True,
                             message="正在拉取训练数据...")
        try:
            baskets = data_fetch.safe_fetch_basket()
            all_x, all_y = {h: [] for h in HORIZONS}, {h: [] for h in HORIZONS}

            for code, df in baskets.items():
                _model_status["message"] = f"正在处理 {code} 的历史数据..."
                for feats, labels in _build_samples(df):
                    for h in HORIZONS:
                        all_x[h].append(feats)
                        all_y[h].append(labels[h])

            total = len(all_x[1])
            if total < 5000:
                _model_status.update(training=False, trained=False,
                                     message=f"样本不足({total}), 训练失败")
                return

            os.makedirs(MODEL_DIR, exist_ok=True)
            # 清理旧版本模型文件
            for old in os.listdir(MODEL_DIR):
                if old.endswith(".pkl"):
                    try:
                        os.remove(os.path.join(MODEL_DIR, old))
                    except OSError:
                        pass

            for h in HORIZONS:
                _model_status["message"] = \
                    f"GPU 堆叠训练 {h} 日模型 ({total} 样本, XGBoost+RF+LR)..."
                clf = _build_stacker()
                X = np.array(all_x[h], dtype=np.float64)
                y = np.array(all_y[h])
                clf.fit(X, y)
                # 将 XGBoost 模型设为 CPU 模式, 避免预测时占用 GPU 显存
                for name, est in clf.named_estimators_.items():
                    if "xgboost" in name and hasattr(est, "set_params"):
                        try:
                            est.set_params(device="cpu")
                        except Exception:
                            pass
                with open(_model_path(h), "wb") as f:
                    pickle.dump(clf, f)
                _models[h] = clf
                _model_status["message"] = f"{h}日模型训练完成"

            with open(_VERSION_FILE, "w") as f:
                f.write(str(MODEL_VERSION))

            _model_status.update(
                trained=True, training=False,
                message=f"堆叠训练完成: {total} 个样本, {len(baskets)} 只股票",
                updated_at=time.time())
        except Exception as e:
            _model_status.update(training=False, trained=False,
                                 message=f"训练失败: {e}")
            raise


def ensure_models():
    """懒加载: 从磁盘加载或触发后台训练。"""
    if _is_fresh():
        try:
            for h in HORIZONS:
                with open(_model_path(h), "rb") as f:
                    _models[h] = pickle.load(f)
            _model_status.update(trained=True, training=False,
                                 message="模型已加载 (磁盘缓存)")
            return
        except Exception:
            pass
    if not _model_status["training"] and not _models:
        threading.Thread(target=train_models, daemon=True).start()


def get_status():
    info = dict(_model_status)
    info["model_info"] = get_model_info()
    return info


def get_model_info():
    """返回堆叠模型构成信息"""
    return {
        "type": "stacking",
        "base_models": [
            {"key": "xgboost", "name": "XGBoost(GPU)"},
            {"key": "random_forest", "name": "随机森林"},
            {"key": "extra_trees", "name": "极端随机树"},
            {"key": "adaboost", "name": "AdaBoost"},
            {"key": "linear", "name": "逻辑回归"},
        ],
        "meta_model": "逻辑回归",
        "stack_method": "概率加权融合 (GPU加速)",
        "features": len(FEATURES),
        "training_basket_size": 60,
    }


def predict_stock(code):
    """预测单只股票未来 1/5/20 日涨跌。返回 dict 或 None。"""
    ensure_models()
    if not _models:
        # 模型还在训练, 等最多 90 秒
        deadline = time.time() + 90
        while time.time() < deadline:
            if _models:
                break
            time.sleep(1)
    if not _models:
        raise RuntimeError("模型尚未训练完成, 请稍后重试")

    df = data_fetch.fetch_daily(code, days=400)
    if df is None or len(df) < MIN_BARS:
        raise RuntimeError("历史数据不足, 无法预测")

    feat, ok = indicators.latest_feature_vector(df)
    if not ok:
        raise RuntimeError("指标计算失败, 历史数据不足")

    X = np.array([[feat[c] for c in FEATURES]], dtype=np.float64)
    result = {}
    for h in HORIZONS:
        clf = _models[h]
        prob = float(clf.predict_proba(X)[0][1])  # 上涨概率
        direction = "up" if prob >= 0.5 else "down"
        result[h] = {
            "prob_up": round(prob * 100, 1),
            "direction": direction,
            "confidence": _confidence(prob),
        }
    return result


def _confidence(prob):
    """概率越极端, 置信度越高"""
    p = abs(prob - 0.5) * 2
    if p >= 0.8:
        return "high"
    if p >= 0.5:
        return "medium"
    return "low"


def backtest(code, days=20, horizon=1):
    """回测: 用"截止每个交易日"的特征预测下一个交易日涨跌, 与真实涨跌对比。
    返回 近 N 日预估准确率 + 逐日明细 + 最近一次(昨日预估 vs 今日实际)。
    结果缓存 5 分钟, 避免重复计算。"""
    ensure_models()
    if not _models:
        raise RuntimeError("模型尚未训练完成, 请稍后重试")
    if horizon not in _models:
        raise RuntimeError("该预测周期模型不可用")
    key = (code, days, horizon)
    now = time.time()
    if key in _backtest_cache and now - _backtest_cache[key][0] < 300:
        return _backtest_cache[key][1]
    df = data_fetch.fetch_daily(code, days=400)
    if df is None or len(df) < MIN_BARS:
        raise RuntimeError("历史数据不足, 无法回测")
    clf = _models[horizon]
    n = len(df)
    start = max(MIN_BARS, n - horizon - days)
    results = []
    for i in range(start, n - horizon):
        sub = df.iloc[:i + 1]
        feat, ok = indicators.latest_feature_vector(sub)
        if not ok:
            continue
        X = np.array([[feat[c] for c in FEATURES]], dtype=np.float64)
        prob = float(clf.predict_proba(X)[0][1])
        pred = "up" if prob >= 0.5 else "down"
        cur = df.iloc[i]["close"]
        fut = df.iloc[i + horizon]["close"]
        ret = (fut / cur - 1) * 100
        actual = "up" if ret > 0 else "down"
        results.append({
            "date": str(df.iloc[i]["date"].date()),
            "target_date": str(df.iloc[i + horizon]["date"].date()),
            "pred": pred,
            "prob_up": round(prob * 100, 1),
            "actual": actual,
            "ret": round(ret, 2),
            "correct": pred == actual,
        })
    correct = sum(1 for r in results if r["correct"])
    result = {
        "horizon": horizon,
        "accuracy": round(correct / len(results) * 100, 1) if results else None,
        "total": len(results),
        "results": results,
        "last": results[-1] if results else None,
    }
    _backtest_cache[key] = (time.time(), result)
    return result
