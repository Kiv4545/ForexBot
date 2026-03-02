import yfinance as yf
import pandas as pd
import numpy as np
import time
import requests

# --- SETTINGS ---
# In the cloud, we will fetch these from the Streamlit Settings dashboard later
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]

# The 7 Forex Majors
MAJORS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X", "USDCAD=X", "NZDUSD=X"]

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try: requests.post(url, json=payload)
    except Exception as e: print(f"Telegram Error: {e}")

def get_market_data(symbol, interval="1h", period="2y"):
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)
    if df.empty: return None
    df = df.reset_index().rename(columns={'Datetime': 'Time', 'Date': 'Time'})
    return df[['Time', 'Open', 'High', 'Low', 'Close']]

def resample_to_4h(df):
    df.set_index('Time', inplace=True)
    resample_logic = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}
    df_4h = df.resample('4h').apply(resample_logic).dropna().reset_index()
    return df_4h

def add_indicators(df):
    df['EMA_9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    df['RSI_14'] = 100 - (100 / (1 + gain/loss))
    
    tr = pd.concat([(df['High']-df['Low']), (df['High']-df['Close'].shift(1)).abs(), (df['Low']-df['Close'].shift(1)).abs()], axis=1).max(axis=1)
    df['ATR_14'] = tr.ewm(alpha=1/14, adjust=False).mean()
    
    df['Resistance'] = df['High'].rolling(window=30).max()
    df['Support'] = df['Low'].rolling(window=30).min()
    return df.dropna().reset_index(drop=True)

def check_signals(symbol, df_4h, df_1d):
    last_4h = df_4h.iloc[-2]
    prev_4h = df_4h.iloc[-3]
    last_1d = df_1d.iloc[-2]
    
    daily_trend_up = last_1d['EMA_9'] > last_1d['EMA_21']
    daily_trend_down = last_1d['EMA_9'] < last_1d['EMA_21']
    current_price = last_4h['Close']
    atr = last_4h['ATR_14']

    signal = "NEUTRAL"
    action = ""

    # Strategy Logic
    if prev_4h['EMA_9'] <= prev_4h['EMA_21'] and last_4h['EMA_9'] > last_4h['EMA_21'] and daily_trend_up:
        if current_price < (last_4h['Resistance'] - atr):
            signal = "BUY"
            sl, tp = current_price - (atr * 2), current_price + (atr * 4)
            action = f"🏔️ <b>SWING BUY: {symbol}</b>\nTrend: D1 BULLISH\nPrice: {current_price:.4f}\nSL: {sl:.4f} | TP: {tp:.4f}"

    elif prev_4h['EMA_9'] >= prev_4h['EMA_21'] and last_4h['EMA_9'] < last_4h['EMA_21'] and daily_trend_down:
        if current_price > (last_4h['Support'] + atr):
            signal = "SELL"
            sl, tp = current_price + (atr * 2), current_price - (atr * 4)
            action = f"🏔️ <b>SWING SELL: {symbol}</b>\nTrend: D1 BEARISH\nPrice: {current_price:.4f}\nSL: {sl:.4f} | TP: {tp:.4f}"

    return signal, action, last_4h['Time']

# --- MAIN SCANNER LOOP ---
if __name__ == "__main__":
    print(f"Starting Scanner for {len(MAJORS)} Major Pairs...")
    send_telegram_message(f"🤖 <b>Scanner Started</b>\nMonitoring: {', '.join(MAJORS)}")
    
    last_signals = {} # Dictionary to track signals for each pair

    while True:
        for symbol in MAJORS:
            try:
                print(f"Scanning {symbol}...", end="\r")
                
                # Fetch & Process
                raw_1h = get_market_data(symbol, interval="1h", period="1y")
                df_4h = add_indicators(resample_to_4h(raw_1h))
                df_1d = add_indicators(get_market_data(symbol, interval="1d", period="2y"))
                
                signal, action_message, candle_time = check_signals(symbol, df_4h, df_1d)
                
                # Check for new signals
                if signal != "NEUTRAL":
                    # Only alert if this is a NEW candle for this specific symbol
                    if last_signals.get(symbol) != candle_time:
                        print(f"\n🚨 ALERT: {symbol} {signal} signal found!")
                        send_telegram_message(action_message)
                        last_signals[symbol] = candle_time
                
                # Small pause to be nice to Yahoo's servers
                time.sleep(2) 

            except Exception as e:
                print(f"\nError scanning {symbol}: {e}")
        
        print(f"\n[{pd.Timestamp.now().strftime('%H:%M')}] Full scan complete. Waiting 15 minutes...")
        time.sleep(900)