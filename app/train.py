"""Walk-forward test + final training of a LightGBM next-candle direction model.

Usage: python -m app.train [15m|1h|1d] [stocks|forex]
"""
import json
import sys
from datetime import datetime

import lightgbm as lgb
import numpy as np
import pandas as pd

from .chitragupta import IST, final_day
from .config import MARKETS, MODELS_DIR, ROOT
from .db import connect
from .features import FEATURES, build

PARAMS = dict(
    objective="binary", learning_rate=0.03, num_leaves=15, min_data_in_leaf=200,
    feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, lambda_l2=5.0, verbose=-1,
)
ROUNDS = 300
CONF = 0.05  # "confident" = prob_up >= 0.55 or <= 0.45
FOLDS = 5


def load_dataset(conn, interval: str, market: str = "stocks") -> pd.DataFrame:
    """Every candle of one market's symbols at this interval, with features and labels. A daily candle still
    forming is left out: the day before's label would otherwise come from a close that isn't final yet."""
    symbols = list(MARKETS[market])
    raw = pd.read_sql(f"SELECT * FROM candles WHERE interval = ? AND symbol IN ({','.join('?' * len(symbols))}) "
                      "ORDER BY symbol, ts", conn, params=(interval, *symbols))
    if interval == "1d" and not raw.empty:
        now = datetime.now(IST)
        days = pd.to_datetime(raw["ts"], unit="ms", utc=True).dt.tz_convert("Asia/Kolkata").dt.strftime("%Y-%m-%d")
        raw = raw[[final_day(s, d, now) for s, d in zip(raw["symbol"], days)]]
    parts = [build(g.reset_index(drop=True), interval).assign(symbol=s) for s, g in raw.groupby("symbol")]
    df = pd.concat(parts, ignore_index=True)
    return df.dropna(subset=["label", "rsi_14", "volatility_12", "ret_12"])


def evaluate(y: np.ndarray, p: np.ndarray, next_ret: np.ndarray) -> dict:
    conf = np.abs(p - 0.5) >= CONF
    pred = (p >= 0.5).astype(int)
    # Gross move captured if we traded every confident signal (before brokerage/charges).
    signed = np.where(pred == 1, next_ret, -next_ret)
    return {
        "n": int(len(y)),
        "accuracy": round(float((pred == y).mean()) * 100, 2),
        "baseline_up_rate": round(float(y.mean()) * 100, 2),
        "confident_share": round(float(conf.mean()) * 100, 2),
        "confident_accuracy": round(float((pred[conf] == y[conf]).mean()) * 100, 2) if conf.any() else None,
        "confident_avg_move_bps": round(float(signed[conf].mean()) * 1e4, 2) if conf.any() else None,
    }


def walk_forward(df: pd.DataFrame, params: dict, log=print, features: list[str] = FEATURES) -> dict:
    """Out-of-sample metrics: train only on days BEFORE each test block, never on the future."""
    oos = out_of_sample(df, params, log, features)
    return evaluate(oos["label"].to_numpy(), oos["prob_up"].to_numpy(), oos["next_ret"].to_numpy())


def out_of_sample(df: pd.DataFrame, params: dict, log=print, features: list[str] = FEATURES) -> pd.DataFrame:
    """The rows of the second half of days, each block with the prob_up of a model trained only on days before it."""
    days = np.array(sorted(df["date"].unique()))
    blocks = np.array_split(days[len(days) // 2:], FOLDS)
    preds = []
    for i, test_days in enumerate(blocks, 1):
        train = df[df["date"] < test_days[0]]
        test = df[df["date"].isin(test_days)]
        model = lgb.train(params, lgb.Dataset(train[features], train["label"]), ROUNDS)
        p = model.predict(test[features])
        m = evaluate(test["label"].to_numpy(), p, test["next_ret"].to_numpy())
        log(f"  fold {i}: {test_days[0]}..{test_days[-1]}  acc {m['accuracy']}%  "
            f"confident {m['confident_accuracy']}% on {m['confident_share']}% of candles")
        preds.append(test.assign(prob_up=p))
    return pd.concat(preds)


def save(conn, df: pd.DataFrame, interval: str, params: dict, metrics: dict, market: str = "stocks") -> int:
    """Train on ALL rows, write the model file and register it. Returns the model id."""
    final = lgb.train(params, lgb.Dataset(df[FEATURES], df["label"]), ROUNDS)
    name = f"lgbm_{'' if market == 'stocks' else market + '_'}{interval}_{datetime.now():%Y%m%d_%H%M%S}"
    path = MODELS_DIR / f"{name}.txt"
    final.save_model(str(path))

    importance = dict(sorted(zip(FEATURES, final.feature_importance("gain").round(1).tolist()),
                             key=lambda kv: -kv[1]))
    metrics = {**metrics, "top_features": dict(list(importance.items())[:6]), "params": params}
    cur = conn.execute("INSERT INTO models (name, interval, path, metrics, market) VALUES (?,?,?,?,?)",
                       (name, interval, str(path.relative_to(ROOT)), json.dumps(metrics), market))
    conn.commit()
    return cur.lastrowid


def main(interval: str, market: str = "stocks") -> None:
    conn = connect()
    df = load_dataset(conn, interval, market)
    if df.empty:
        sys.exit(f"No {market} {interval} candles in DB. Run: python -m app.fetch {interval}")
    print(f"{interval}: {len(df):,} rows, {df['symbol'].nunique()} symbols, {df['date'].nunique()} trading days")

    metrics = walk_forward(df, PARAMS)
    print("Out-of-sample:", json.dumps(metrics))
    model_id = save(conn, df, interval, PARAMS, metrics, market)
    # A hand-run training replaces whatever the auto-learner had made active
    conn.execute("UPDATE models SET active = (id = ?) WHERE interval = ? AND market = ?", (model_id, interval, market))
    conn.commit()
    conn.close()
    print(f"Saved model #{model_id}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "15m", sys.argv[2] if len(sys.argv) > 2 else "stocks")
