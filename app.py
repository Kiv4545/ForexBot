import streamlit as st
import plotly.graph_objects as go
import yfinance as yf
import pandas as pd

# In the cloud, we will fetch these from the Streamlit Settings dashboard later
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]

# --- SETTINGS & DATA FETCHING ---
MAJORS = ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X", "USDCAD=X", "NZDUSD=X"]

@st.cache_data(ttl=600) # Cache data for 10 minutes to stay fast
def get_data(symbol, interval, period):
    df = yf.Ticker(symbol).history(period=period, interval=interval)
    if df.empty: return pd.DataFrame()
    df = df.reset_index().rename(columns={'Datetime': 'Time', 'Date': 'Time'})
    return df

def add_indicators(df):
    if df.empty: return df
    # EMAs
    df['EMA_9'] = df['Close'].ewm(span=9, adjust=False).mean()
    df['EMA_21'] = df['Close'].ewm(span=21, adjust=False).mean()
    # Support/Resistance
    df['Resistance'] = df['High'].rolling(window=30).max()
    df['Support'] = df['Low'].rolling(window=30).min()
    return df

def create_chart(df, title, height=500):
    """Helper function to build a consistent chart"""
    fig = go.Figure()
    # Candlesticks
    fig.add_trace(go.Candlestick(x=df['Time'], open=df['Open'], high=df['High'], 
                                 low=df['Low'], close=df['Close'], name='Price'))
    # EMAs
    fig.add_trace(go.Scatter(x=df['Time'], y=df['EMA_9'], line=dict(color='orange', width=1.5), name='EMA 9'))
    fig.add_trace(go.Scatter(x=df['Time'], y=df['EMA_21'], line=dict(color='#00d1ff', width=1.5), name='EMA 21'))
    
    # Latest S/R Levels
    fig.add_hline(y=df.iloc[-1]['Resistance'], line_dash="dot", line_color="#ff4b4b", opacity=0.5)
    fig.add_hline(y=df.iloc[-1]['Support'], line_dash="dot", line_color="#00ff00", opacity=0.5)

    fig.update_layout(
        title=title,
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        height=height,
        margin=dict(l=10, r=10, t=40, b=10)
    )
    return fig

# --- UI SETUP ---
st.set_page_config(page_title="Forex Dual-Scan", layout="wide")
st.title("🏔️ Swing Trading Dashboard: 4H & 1D")

# Sidebar
symbol = st.sidebar.selectbox("Select Major Pair", MAJORS)
st.sidebar.markdown("---")
st.sidebar.write("### Strategy Status")

# Fetch and Process Data
with st.spinner('Fetching market data...'):
    # 1D Data
    df_1d = get_data(symbol, "1d", "2y")
    df_1d = add_indicators(df_1d)
    
    # 4H Data (Resampled from 1H)
    raw_1h = get_data(symbol, "1h", "1y")
    raw_1h.set_index('Time', inplace=True)
    df_4h = raw_1h.resample('4h').apply({'Open':'first','High':'max','Low':'min','Close':'last'}).dropna().reset_index()
    df_4h = add_indicators(df_4h)

if not df_1d.empty and not df_4h.empty:
    # --- TREND INDICATORS (SIDEBAR) ---
    d1_up = df_1d.iloc[-1]['EMA_9'] > df_1d.iloc[-1]['EMA_21']
    h4_up = df_4h.iloc[-1]['EMA_9'] > df_4h.iloc[-1]['EMA_21']
    
    st.sidebar.metric("Daily Trend", "BULLISH 📈" if d1_up else "BEARISH 📉")
    st.sidebar.metric("4H Trend", "UP 📈" if h4_up else "DOWN 📉")
    
    if d1_up and h4_up:
        st.sidebar.success("✅ BULLISH ALIGNMENT")
    elif not d1_up and not h4_up:
        st.sidebar.error("🚨 BEARISH ALIGNMENT")
    else:
        st.sidebar.warning("⏳ NO ALIGNMENT")

    # --- THE CHARTS ---
    # Section 1: 4-Hour Chart (Trigger Timeframe)
    st.markdown("### 1️⃣ 4-Hour Trigger Chart")
    st.plotly_chart(create_chart(df_4h, f"{symbol} 4H Chart"), use_container_width=True)

    # Section 2: Daily Chart (Filter Timeframe)
    st.markdown("### 2️⃣ Daily Filter Chart")
    st.plotly_chart(create_chart(df_1d, f"{symbol} Daily Chart"), use_container_width=True)

    # Raw Data Table (Expandable)
    with st.expander("View Raw Data Logs"):
        st.write("Latest 4H Candles")
        st.dataframe(df_4h.tail(10))
else:
    st.error("Data could not be loaded. Please check your internet connection or try again.")