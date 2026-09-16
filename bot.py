
import os
import time
import requests
import pandas as pd

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SYMBOL = "BTCUSDT"
INTERVAL = "15m"

last_signal = None


def get_candles():
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "limit": 100
    }

    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    columns = [
        "time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore"
    ]

    df = pd.DataFrame(response.json(), columns=columns)

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)

    return df


def calculate_signal(df):
    df["ema9"] = df["close"].ewm(span=9, adjust=False).mean()
    df["ema21"] = df["close"].ewm(span=21, adjust=False).mean()

    change = df["close"].diff()
    gain = change.clip(lower=0).rolling(14).mean()
    loss = (-change.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, 0.000001)
    df["rsi"] = 100 - (100 / (1 + rs))

    last = df.iloc[-2]
    previous = df.iloc[-3]

    bullish = (
        last["ema9"] > last["ema21"]
        and last["rsi"] >= 55
        and last["close"] > previous["high"]
        and last["volume"] > df["volume"].iloc[-12:-2].mean()
    )

    bearish = (
        last["ema9"] < last["ema21"]
        and last["rsi"] <= 45
        and last["close"] < previous["low"]
        and last["volume"] > df["volume"].iloc[-12:-2].mean()
    )

    price = last["close"]

    if bullish:
        sl = price * 0.995
        tp = price * 1.01
        return "STRONG BUY", price, sl, tp

    if bearish:
        sl = price * 1.005
        tp = price * 0.99
        return "STRONG SELL", price, sl, tp

    return None


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    data = {
        "chat_id": CHAT_ID,
        "text": message
    }

    requests.post(url, data=data, timeout=20)


def main():
    global last_signal

    while True:
        try:
            df = get_candles()
            signal = calculate_signal(df)

            if signal:
                signal_type, entry, sl, tp = signal

                unique_signal = f"{signal_type}-{round(entry, 2)}"

                if unique_signal != last_signal:
                    message = (
                        f"🚨 {signal_type}\n\n"
                        f"Symbol: {SYMBOL}\n"
                        f"Timeframe: {INTERVAL}\n"
                        f"Entry: {entry:.2f}\n"
                        f"Stop Loss: {sl:.2f}\n"
                        f"Take Profit: {tp:.2f}\n\n"
                        f"⚠️ Educational signal only. "
                        f"Risk management zaroori hai."
                    )

                    send_telegram(message)
                    last_signal = unique_signal

            time.sleep(60)

        except Exception as error:
            print("Error:", error)
            time.sleep(60)


if __name__ == "__main__":
    main()