import os
import re
#import datetime
from typing import Tuple, Optional, Dict, Any, List

from flask import Flask, request, abort
from dotenv import load_dotenv

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, ImageSendMessage, FollowEvent
)

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import seaborn as sns

import yfinance as yf
import pandas as pd


# ======================
# ENV / BASIC SETTINGS
# ======================
load_dotenv()

CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.environ.get("CHANNEL_SECRET")

# 你一定要在 Render 設定 BASE_URL，例如：
# https://line-bot-stock-9881.onrender.com
BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")

if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    raise Exception("❌ 未設定 CHANNEL_ACCESS_TOKEN 或 CHANNEL_SECRET，請檢查環境變數")

if not BASE_URL:
    # 本機可先跑，但雲端沒有 BASE_URL 會導致圖片 URL 組不出來
    print("⚠️ 警告：未設定 BASE_URL。雲端部署請在 Render Environment 設定 BASE_URL。")

# seaborn style
sns.set_theme(style="ticks")

# font settings
font_path = os.path.join("fonts", "NotoSansTC-Regular.ttf")
font_prop = fm.FontProperties(fname=font_path)
plt.rcParams["font.family"] = font_prop.get_name()
plt.rcParams["axes.unicode_minus"] = False


# ======================
# Flask / LINE INIT
# ======================
app = Flask(__name__, static_url_path="/static", static_folder="static")

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ensure static folder exists
os.makedirs("static", exist_ok=True)

# alerts: { user_id: [ {stock_id, operator, target}, ... ] }
alerts: Dict[str, List[Dict[str, Any]]] = {}

# cache (optional): save stock names to avoid frequent heavy calls
name_cache: Dict[str, str] = {}


# ======================
# Helpers
# ======================
def is_valid_stock_id(stock_id: str) -> bool:
    """Taiwan stock id usually 4 digits; some are 5 digits."""
    return stock_id.isdigit() and len(stock_id) in (4, 5)


def to_yahoo_symbol(stock_id: str) -> str:
    """Convert Taiwan stock id to Yahoo Finance symbol."""
    return f"{stock_id}.TW"


def safe_get_stock_name(stock_id: str) -> str:
    """
    Best-effort name: yfinance info sometimes slow; cache after first success.
    If fails, return stock_id.
    """
    if stock_id in name_cache:
        return name_cache[stock_id]

    try:
        tk = yf.Ticker(to_yahoo_symbol(stock_id))
        info = tk.info or {}
        # possible keys: shortName / longName
        name = info.get("shortName") or info.get("longName") or stock_id
        name_cache[stock_id] = name
        return name
    except Exception:
        return stock_id


def safe_get_last_price(stock_id: str) -> Optional[float]:
    """
    Best-effort last price.
    - Try fast_info first (lightweight)
    - Fallback to recent history
    """
    symbol = to_yahoo_symbol(stock_id)
    try:
        tk = yf.Ticker(symbol)
        fi = getattr(tk, "fast_info", None)
        if fi and "last_price" in fi and fi["last_price"] is not None:
            return float(fi["last_price"])
    except Exception:
        pass

    # fallback: 1d history
    try:
        df = yf.download(symbol, period="1d", interval="1m", progress=False)
        if df is None or df.empty:
            df = yf.download(symbol, period="5d", interval="1d", progress=False)
        if df is None or df.empty:
            return None
        last_close = df["Close"].dropna().iloc[-1]
        return float(last_close)
    except Exception:
        return None


def get_stock_price_text(stock_id: str) -> Tuple[bool, str]:
    """Return (success, text)."""
    if not is_valid_stock_id(stock_id):
        return False, f"「{stock_id}」不是合法的股票代號。"

    price = safe_get_last_price(stock_id)
    if price is None:
        return False, f"⚠️ 無法取得 {stock_id} 的最新價格（資料可能暫時不可用）。"

    name = safe_get_stock_name(stock_id)
    return True, f"{name}({stock_id}) 目前價格：約 {price:.2f} 元"


def fetch_history_df(stock_id: str, days: int) -> Optional[pd.DataFrame]:
    """
    Fetch recent daily history.
    Use a buffer to avoid weekends/holidays.
    """
    if days <= 0:
        days = 5

    symbol = to_yahoo_symbol(stock_id)
    # buffer: request more days to cover holidays
    req_days = max(days * 3, days + 10)
    period = f"{req_days}d"

    try:
        df = yf.download(symbol, period=period, interval="1d", progress=False)
        if df is None or df.empty:
            return None

        df = df.dropna(subset=["Close"])
        if df.empty:
            return None

        # take last N trading days
        df = df.tail(days)
        return df
    except Exception as e:
        print("[yfinance history error]", stock_id, e)
        return None


def plot_stock_trend(stock_id: str, days: int = 5) -> Optional[str]:
    """Generate trend chart and return local filename, or None."""
    try:
        days = int(days)
    except Exception:
        days = 5

    if not is_valid_stock_id(stock_id):
        return None

    df = fetch_history_df(stock_id, days)
    if df is None or df.empty:
        return None

    dates = df.index
    prices = df["Close"].tolist()
    if not prices:
        return None

    max_price = max(prices)
    min_price = min(prices)
    max_date = dates[prices.index(max_price)]
    min_date = dates[prices.index(min_price)]

    try:
        plt.figure(figsize=(8, 4))
        plt.plot(dates, prices, marker="o")
        plt.title(f"{stock_id} 最近 {days} 日收盤價", fontsize=16, fontproperties=font_prop)
        plt.xlabel("日期", fontsize=12, fontproperties=font_prop)
        plt.ylabel("收盤價(元)", fontsize=12, fontproperties=font_prop)
        plt.grid(True, linestyle="--", alpha=0.7)
        plt.xticks(rotation=45, fontproperties=font_prop)
        plt.yticks(fontproperties=font_prop)

        # mark high/low
        plt.scatter([max_date], [max_price], color="#d62728", s=80, zorder=5, marker="v", label="最高價")
        plt.scatter([min_date], [min_price], color="#1f77b4", s=80, zorder=5, marker="^", label="最低價")

        plt.text(
            max_date, max_price,
            f"最高 {max_price:.2f}",
            color="#d62728", fontsize=10, ha="center",
            fontproperties=font_prop,
            bbox=dict(facecolor="white", alpha=0.8, edgecolor="none")
        )
        plt.text(
            min_date, min_price,
            f"最低 {min_price:.2f}",
            color="#1f77b4", fontsize=10, ha="center",
            fontproperties=font_prop,
            bbox=dict(facecolor="white", alpha=0.8, edgecolor="none")
        )

        filename = f"static/{stock_id}_trend.png"
        plt.tight_layout()
        plt.savefig(filename)
        plt.close()
        return filename
    except Exception as e:
        print("[plot error]", stock_id, e)
        try:
            plt.close()
        except Exception:
            pass
        return None


def build_stock_reply(stock_id: str, days: int = 5) -> Tuple[bool, str, Optional[str]]:
    """
    Return: (success, price_text, image_url or None)
    - price_text always returns something meaningful
    - image_url may be None
    """
    ok, price_text = get_stock_price_text(stock_id)
    if not ok:
        return False, price_text, None

    filename = plot_stock_trend(stock_id, days)
    if filename is None:
        return True, price_text + "\n⚠️ 趨勢圖資料暫時不可用（可能是資料源或交易日不足）。", None

    if not BASE_URL:
        # no base url => still return text, but no image
        return True, price_text + "\n⚠️ 尚未設定 BASE_URL，無法提供圖片連結。", None

    image_url = f"{BASE_URL}/{filename}"
    return True, price_text, image_url


def parse_user_input(user_message: str) -> Dict[str, Any]:
    """
    return:
    {
      'mode': 'single' or 'multi',
      'stock_ids': ['2330', '2317'],
      'days': 5 or 30
    }
    """
    parts = user_message.strip().split()
    result = {"mode": "single", "stock_ids": [], "days": 5}

    if not parts:
        return result

    # multi: 查 2330 2317
    if parts[0] == "查":
        result["mode"] = "multi"
        # filter to valid numeric ids
        candidates = [p.strip() for p in parts[1:]]
        result["stock_ids"] = [s for s in candidates if is_valid_stock_id(s)]
        return result

    # single: 2330 or 2330 30
    stock_id = parts[0].strip()
    result["stock_ids"] = [stock_id]

    if len(parts) > 1:
        keyword = parts[1].strip()
        if keyword in ["30", "30天", "30日", "月線"]:
            result["days"] = 30

    return result


# ======================
# Webhook
# ======================
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    app.logger.info("Request body: %s", body)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception as e:
        # keep webhook alive
        app.logger.exception("Webhook handle error: %s", e)
        return "OK", 200

    return "OK", 200


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    # private chat only
    if event.source.type != "user":
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="⚠️ 抱歉，目前僅支援私訊（1對1聊天）查詢股票。")
        )
        return

    user_id = event.source.user_id
    user_message = event.message.text.strip()

    # ===== price alert command: 設定 2330 > 800 =====
    if user_message.startswith("設定"):
        try:
            match = re.match(r"設定\s+(\d+)\s*([<>])\s*(\d+\.?\d*)", user_message)
            if not match:
                raise ValueError("格式錯誤")

            stock_id, operator, target_str = match.groups()
            stock_id = stock_id.strip()

            if not is_valid_stock_id(stock_id):
                raise ValueError("股票代號錯誤")

            target_price = float(target_str)

            if user_id not in alerts:
                alerts[user_id] = []

            alerts[user_id].append({
                "stock_id": stock_id,
                "operator": operator,
                "target": target_price,
            })

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"✅ 已設定：當 {stock_id} {operator} {target_price} 時通知你")
            )
        except Exception:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="❌ 設定格式錯誤，請輸入範例：設定 2330 > 800")
            )
        return

    parsed = parse_user_input(user_message)

    # no valid stocks in multi mode
    if parsed["mode"] == "multi" and not parsed["stock_ids"]:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="❌ 未偵測到有效的股票代號。範例：查 2330 2317")
        )
        return

    # reply once
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="正在查詢股票資料，請稍後...")
    )

    # push results
    for stock_id in parsed["stock_ids"]:
        success, price_text, image_url = build_stock_reply(stock_id, parsed["days"])

        if not success:
            line_bot_api.push_message(user_id, TextSendMessage(text=price_text))
            continue

        # text + optional image
        if image_url:
            line_bot_api.push_message(
                user_id,
                [
                    TextSendMessage(text=price_text),
                    ImageSendMessage(
                        original_content_url=image_url,
                        preview_image_url=image_url
                    )
                ]
            )
        else:
            line_bot_api.push_message(user_id, TextSendMessage(text=price_text))


@handler.add(FollowEvent)
def handle_follow(event):
    user_id = event.source.user_id
    welcome_msg = (
        "👋 歡迎加入台灣股市小幫手！\n\n"
        "以下是你可以使用的功能指令：\n"
        "📌 即時價格：輸入股票代碼，如 `2330`\n"
        "📈 趨勢圖：輸入 `2330 30天` 或 `查 2330 2317`（請用空白分隔）\n"
        "🔔 價格警示：輸入 `設定 2330 > 800`（請用空白分隔）\n"
        "🧾 可透過 /check_alerts 觸發檢查（搭配 Render Cron / 外部排程）\n\n"
        "範例：`查 2330 2881 2317`\n"
        "🚀 祝你投資順利！"
    )
    line_bot_api.push_message(user_id, TextSendMessage(text=welcome_msg))


# ======================
# Alert monitor (no twstock)
# ======================
def run_alert_monitor_once():
    print("[INFO] Running alert monitor ONCE")

    if not alerts:
        print("[INFO] 無警示設定")
        return

    # iterate a copy of keys to avoid runtime modification issues
    for user_id in list(alerts.keys()):
        user_alerts = alerts.get(user_id, [])
        for alert in user_alerts[:]:
            stock_id = alert["stock_id"]
            operator = alert["operator"]
            target = alert["target"]

            try:
                current_price = safe_get_last_price(stock_id)
                if current_price is None:
                    print(f"[DEBUG] 無法取得 {stock_id} 現價")
                    continue

                print(f"[DEBUG] 檢查 {stock_id} 現價 {current_price:.2f}, 條件 {operator} {target}")

                triggered = (operator == ">" and current_price > target) or \
                            (operator == "<" and current_price < target)

                if triggered:
                    name = safe_get_stock_name(stock_id)
                    msg = (
                        f"📈 警示觸發：{name}({stock_id}) 現在約 {current_price:.2f} 元，"
                        f"已{'高於' if operator == '>' else '低於'} {target} 元"
                    )
                    line_bot_api.push_message(user_id, TextSendMessage(text=msg))

                    # remove after triggered to avoid repeated notifications
                    user_alerts.remove(alert)

            except Exception as e:
                print(f"[警示錯誤]{stock_id}: {e}")


@app.route("/check_alerts", methods=["GET"])
def check_alerts():
    run_alert_monitor_once()
    return "✅ 價格警示已檢查", 200

@app.route("/", methods=["GET"])
def home():
    return "OK - LINE Bot server is running", 200

# ======================
# Main
# ======================
if __name__ == "__main__":
    # local run
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
