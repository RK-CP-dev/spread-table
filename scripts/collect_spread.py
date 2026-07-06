#!/usr/bin/env python3
"""取引所スプレッド率 収集スクリプト.

4社のパブリックAPI（認証不要）からBTC/JPYのask/bidを取得し、
スプレッド率(%) = (ask - bid) / ask * 100 を計算して docs/spread.json に出力する。

- Python 3.12 想定（3.9以降で動作）。標準ライブラリのみ使用。
- APIキー等の秘匿情報は一切使用しない。
- 1社の取得失敗が全体を止めない（失敗した社はスキップしてwarnログ）。
"""

import json
import logging
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# 調整可能な定数
# ---------------------------------------------------------------------------
SAMPLE_COUNT = 3        # 1回の実行で取得するサンプル数
SAMPLE_INTERVAL_SEC = 2  # サンプル間の待機秒数
REQUEST_TIMEOUT_SEC = 10  # 各APIリクエストのタイムアウト秒数

JST = timezone(timedelta(hours=9))  # 日本標準時（実行環境のローカルタイムに依存しない）

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "docs" / "spread.json"

USER_AGENT = "coinpost-spread-collector/1.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 各社パーサー: APIレスポンス(dict) -> (ask, bid) のタプルを返す
# ---------------------------------------------------------------------------
def parse_gmo(payload):
    """GMOコイン: data[0].ask / data[0].bid"""
    item = payload["data"][0]
    return float(item["ask"]), float(item["bid"])


def parse_bitflyer(payload):
    """bitFlyer: best_ask / best_bid"""
    return float(payload["best_ask"]), float(payload["best_bid"])


def parse_coincheck(payload):
    """Coincheck: ask / bid"""
    return float(payload["ask"]), float(payload["bid"])


def parse_bitbank(payload):
    """bitbank: data.sell（購入=ask相当） / data.buy（売却=bid相当）"""
    data = payload["data"]
    return float(data["sell"]), float(data["buy"])


# name には「（取引所）」「（販売所）」の区別を含める。
# bitbankのtickerは板（=取引所）の値であり、販売所レートと混同させないため。
EXCHANGES = [
    {
        "name": "GMOコイン（取引所）",
        "url": "https://api.coin.z.com/public/v1/ticker?symbol=BTC",
        "parser": parse_gmo,
    },
    {
        "name": "bitFlyer（取引所）",
        "url": "https://api.bitflyer.com/v1/ticker?product_code=BTC_JPY",
        "parser": parse_bitflyer,
    },
    {
        "name": "Coincheck（取引所）",
        "url": "https://coincheck.com/api/ticker",
        "parser": parse_coincheck,
    },
    {
        "name": "bitbank（取引所）",
        "url": "https://public.bitbank.cc/btc_jpy/ticker",
        "parser": parse_bitbank,
    },
]


# ---------------------------------------------------------------------------
# 取得処理
# ---------------------------------------------------------------------------
def fetch_json(url):
    """URLからJSONを取得してdictを返す。失敗時は例外を送出する。"""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SEC) as response:
        body = response.read().decode("utf-8")
    return json.loads(body)


def fetch_one_sample(exchange):
    """1社の1サンプル（ask, bid）を取得する。失敗時は例外を送出する。"""
    payload = fetch_json(exchange["url"])
    ask, bid = exchange["parser"](payload)
    if ask <= 0 or bid <= 0:
        raise ValueError(
            "invalid price: ask=%r bid=%r" % (ask, bid)
        )
    return ask, bid


def collect_samples():
    """全社×SAMPLE_COUNT回のサンプルを収集する。

    戻り値: {name: [(ask, bid), ...]} — 失敗したサンプルは含まれない。
    """
    samples = {exchange["name"]: [] for exchange in EXCHANGES}

    for i in range(SAMPLE_COUNT):
        if i > 0:
            time.sleep(SAMPLE_INTERVAL_SEC)
        for exchange in EXCHANGES:
            name = exchange["name"]
            try:
                ask, bid = fetch_one_sample(exchange)
                samples[name].append((ask, bid))
                logger.info(
                    "sample %d/%d %s: ask=%.0f bid=%.0f",
                    i + 1, SAMPLE_COUNT, name, ask, bid,
                )
            except (urllib.error.URLError, ValueError, KeyError,
                    IndexError, TypeError, json.JSONDecodeError) as exc:
                logger.warning(
                    "sample %d/%d %s: fetch failed (%s) — skipping this sample",
                    i + 1, SAMPLE_COUNT, name, exc,
                )

    return samples


def build_rows(samples):
    """サンプルの平均からJSON出力用のrowsを構築する（新しいlistを返す）。"""
    rows = []
    for exchange in EXCHANGES:
        name = exchange["name"]
        pairs = samples.get(name, [])
        if not pairs:
            logger.warning("%s: no valid samples — excluded from output", name)
            continue
        avg_ask = sum(pair[0] for pair in pairs) / len(pairs)
        avg_bid = sum(pair[1] for pair in pairs) / len(pairs)
        spread_pct = (avg_ask - avg_bid) / avg_ask * 100
        rows.append({
            "name": name,
            "ask": round(avg_ask),
            "bid": round(avg_bid),
            "spread": round(spread_pct, 3),
        })
    return rows


def build_output(rows):
    """出力用dictを構築する。updatedは毎回必ずJSTの当日日付になる。"""
    today_jst = datetime.now(JST).strftime("%Y-%m-%d")
    return {
        "updated": today_jst,
        "base_currency": "BTC/JPY",
        "rows": rows,
    }


def main():
    samples = collect_samples()
    rows = build_rows(samples)

    if not rows:
        logger.error("all exchanges failed — spread.json not updated")
        return 1

    output = build_output(rows)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    logger.info(
        "wrote %s (%d/%d exchanges)", OUTPUT_PATH, len(rows), len(EXCHANGES)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
