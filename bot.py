import yfinance as yf
import pandas as pd
import time
import requests

# --- TELEGRAM CONFIG ---
# Replace these with your actual IDs or use a .env file locally
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
MAJORS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X", "USDCAD=X", "NZDUSD=X"]

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"})

def get_data(symbol, interval, period):
    df = yf.Ticker(symbol).history(period=period, interval=interval)
    if df.empty: return df
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df = df.reset_index().rename(columns={'Datetime': 'Time', 'Date': 'Time'})
    return df[['Time', 'Open', 'High', 'Low', 'Close']]

def add_indicators(df):
    df['EMA_9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
    tr = pd.concat([(df['High']-df['Low']), (df['High']-df['Close'].shift(1)).abs(), (df['Low']-df['Close'].shift(1)).abs()], axis=1).max(axis=1)
    df['ATR'] = tr.ewm(alpha=1/14, adjust=False).mean()
    df['Res'] = df['High'].rolling(window=30).max()
    df['Sup'] = df['Low'].rolling(window=30).min()
    return df.dropna()

if __name__ == "__main__":
    print("Scanner Active...")
    send_telegram("🚀 <b>Multi-Pair Swing Bot Started</b>")
    last_alerts = {}

    while True:
        for sym in MAJORS:
            try:
                # Process H4
                raw_1h = get_data(sym, "1h", "1y")
                raw_1h.set_index('Time', inplace=True)
                df_4h = add_indicators(raw_1h.resample('4h').apply({'Open':'first','High':'max','Low':'min','Close':'last'}).dropna().reset_index())
                
                # Process D1
                df_1d = add_indicators(get_data(sym, "1d", "2y"))
                
                # Logic
                last_4h, prev_4h = df_4h.iloc[-2], df_4h.iloc[-3]
                daily_up = df_1d.iloc[-2]['EMA_9'] > df_1d.iloc[-2]['EMA_21']
                daily_down = df_1d.iloc[-2]['EMA_9'] < df_1d.iloc[-2]['EMA_21']
                
                msg = None
                if prev_4h['EMA_9'] <= prev_4h['EMA_21'] and last_4h['EMA_9'] > prev_4h['EMA_21'] and daily_up:
                    if last_4h['Close'] < (last_4h['Res'] - last_4h['ATR']):
                        msg = f"🟢 <b>BUY {sym}</b>\nPrice: {last_4h['Close']:.4f}\nDaily Trend: UP"
                
                elif prev_4h['EMA_9'] >= prev_4h['EMA_21'] and last_4h['EMA_9'] < prev_4h['EMA_21'] and daily_down:
                    if last_4h['Close'] > (last_4h['Sup'] + last_4h['ATR']):
                        msg = f"🔴 <b>SELL {sym}</b>\nPrice: {last_4h['Close']:.4f}\nDaily Trend: DOWN"

                if msg and last_alerts.get(sym) != last_4h['Time']:
                    send_telegram(msg)
                    last_alerts[sym] = last_4h['Time']
                
                time.sleep(2) # Politeness
            except Exception as e: print(f"Error {sym}: {e}")
        
        print(f"Scan Finished at {pd.Timestamp.now()}. Waiting 15m...")
        time.sleep(900)
