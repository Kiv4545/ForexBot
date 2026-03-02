import streamlit as st
import plotly.graph_objects as go
import yfinance as yf
import pandas as pd

TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]

# --- SETTINGS & SECRETS ---
MAJORS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X", "USDCAD=X", "NZDUSD=X"]

# Function to fetch and clean data
@st.cache_data(ttl=900)
def get_clean_data(symbol, interval, period):
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)
    if df.empty: return pd.DataFrame()

    # 1. Fix the MultiIndex issue (Removes those diagonal lines)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # 2. Reset index and fix Time column
    df = df.reset_index()
    df = df.rename(columns={'Datetime': 'Time', 'Date': 'Time'})

    # 3. Ensure price columns are pure numbers
    for col in ['Open', 'High', 'Low', 'Close']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    return df[['Time', 'Open', 'High', 'Low', 'Close']].dropna()

def resample_to_4h(df):
    if df.empty: return df
    df = df.set_index('Time')
    resample_logic = {'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last'}
    df_4h = df.resample('4h').apply(resample_logic).dropna().reset_index()
    return df_4h

def add_indicators(df):
    if df.empty: return df
    # EMAs
    df['EMA_9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
    # Support & Resistance (30 periods)
    df['Resistance'] = df['High'].rolling(window=30).max()
    df['Support'] = df['Low'].rolling(window=30).min()
    return df.dropna()

def create_chart(df, title):
    fig = go.Figure()
    # Candlesticks
    fig.add_trace(go.Candlestick(x=df['Time'], open=df['Open'], high=df['High'], 
                low=df['Low'], close=df['Close'], name='Price'))
    # EMAs
    fig.add_trace(go.Scatter(x=df['Time'], y=df['EMA_9'], line=dict(color='orange', width=1.5), name='EMA 9'))
    fig.add_trace(go.Scatter(x=df['Time'], y=df['EMA_21'], line=dict(color='#00d1ff', width=1.5), name='EMA 21'))
    
    # Clean up layout
    fig.update_layout(title=title, template="plotly_dark", xaxis_rangeslider_visible=False, height=500)
    # Hide weekends
    fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    return fig

# --- UI ---
st.set_page_config(page_title="Forex Dual-Scan", layout="wide")
st.title("🏔️ Swing Trading: 4H & 1D Dashboard")

symbol = st.sidebar.selectbox("Select Pair", MAJORS)

with st.spinner('Loading Data...'):
    # Daily Data
    df_1d = add_indicators(get_clean_data(symbol, "1d", "2y"))
    # 4H Data
    raw_1h = get_clean_data(symbol, "1h", "1y")
    df_4h = add_indicators(resample_to_4h(raw_1h))

if not df_1d.empty and not df_4h.empty:
    # Sidebar Metrics
    d1_up = df_1d.iloc[-1]['EMA_9'] > df_1d.iloc[-1]['EMA_21']
    h4_up = df_4h.iloc[-1]['EMA_9'] > df_4h.iloc[-1]['EMA_21']
    
    st.sidebar.metric("Daily Trend", "BULLISH 📈" if d1_up else "BEARISH 📉")
    st.sidebar.metric("4H Trend", "UP 📈" if h4_up else "DOWN 📉")

    # Charts
    st.plotly_chart(create_chart(df_4h, f"{symbol} 4-Hour Trigger Chart"), use_container_width=True)
    st.plotly_chart(create_chart(df_1d, f"{symbol} Daily Filter Chart"), use_container_width=True)
else:
    st.error("No data found for this pair.")
