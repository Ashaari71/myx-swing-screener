import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.linear_model import LinearRegression
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="Carta & Ramalan Saham (BOB / BOD)", layout="wide"
)

st.title("📈 Sistem Carta, Indikator & Ramalan Saham")
st.caption(
    "Menyokong carta candlestick, EMA 20/50, RSI(14), RVOL, isyarat BOB/BOD"
    " asas, dan unjuran regresi linear."
)

# --- Sidebar: Kawalan & Input ---
st.sidebar.header("Tetapan Kaunter & Carta")

default_tickers = [
    "YINSON.KL",
    "PEKAT.KL",
    "SUNCON.KL",
    "KPJ.KL",
    "SAMAIDEN.KL",
    "MAXIS.KL",
    "TOPGLOV.KL",
    "PJBUMI.KL",
]
selected_preset = st.sidebar.selectbox(
    "Senarai Pantauan Pantas", default_tickers, index=0
)
ticker = (
    st.sidebar.text_input("Atau Masukkan Simbol Saham", value=selected_preset)
    .strip()
    .upper()
)

period = st.sidebar.selectbox(
    "Tempoh Data Sejarah", ["3mo", "6mo", "1y", "2y"], index=1
)
interval = st.sidebar.selectbox(
    "Selang Masa (Interval)", ["1d", "1h", "15m"], index=0
)

st.sidebar.subheader("Tetapan Indikator & BOB/BOD")
rvol_min = st.sidebar.slider("RVOL Minimum", 0.5, 3.0, 1.25, 0.05)
rsi_min = st.sidebar.slider("RSI(14) Minimum BOB", 30.0, 75.0, 50.0, 1.0)
body_ratio_min = st.sidebar.slider(
    "Nisbah Badan Lilin Minimum", 0.10, 0.90, 0.50, 0.05
)

st.sidebar.subheader("Tetapan Ramalan (Linear Regression)")
lookback_days = st.sidebar.slider(
    "Bilangan Bar Terakhir untuk Fit Trend", 10, 90, 30, 5
)
forecast_steps = st.sidebar.slider(
    "Bilangan Langkah Ramalan ke Hadapan", 1, 15, 5, 1
)


@st.cache_data(ttl=300)
def load_stock_data(sym: str, per: str, inter: str) -> pd.DataFrame:
  df = yf.download(sym, period=per, interval=inter, progress=False)
  if df.empty:
    return pd.DataFrame()
  if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)
  df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"]).copy()
  df.index = pd.to_datetime(df.index)
  return df


def compute_indicators(
    df: pd.DataFrame, rvol_thr: float, rsi_thr: float, body_thr: float
) -> pd.DataFrame:
  out = df.copy()
  out["EMA20"] = out["Close"].ewm(span=20, adjust=False).mean()
  out["EMA50"] = out["Close"].ewm(span=50, adjust=False).mean()

  # RSI (14)
  delta = out["Close"].diff()
  gain = delta.clip(lower=0).rolling(14).mean()
  loss = (-delta.clip(upper=0)).rolling(14).mean()
  rs = gain / loss.replace(0, np.nan)
  out["RSI14"] = 100 - (100 / (1 + rs))

  # RVOL (20)
  vol_avg20 = out["Volume"].rolling(20).mean()
  out["RVOL"] = out["Volume"] / vol_avg20.replace(0, np.nan)

  # Struktur Lilin
  rng = (out["High"] - out["Low"]).replace(0, np.nan)
  body = (out["Close"] - out["Open"]).abs()
  out["BodyRatio"] = (body / rng).fillna(0.0)
  out["IsBullish"] = (out["Close"] > out["Open"]) & (
      out["BodyRatio"] >= body_thr
  )

  # Isyarat BOB & BOD asas
  prev_high_20 = out["High"].shift(1).rolling(20).max()
  out["BOB_Signal"] = (
      (out["Close"] > prev_high_20)
      & out["IsBullish"]
      & (out["RVOL"] >= rvol_thr)
      & (out["RSI14"] >= rsi_thr)
  )

  near_ema20 = (out["Low"] <= out["EMA20"] * 1.01) & (
      out["Close"] >= out["EMA20"] * 0.99
  )
  out["BOD_Signal"] = (
      near_ema20
      & out["IsBullish"]
      & (out["RVOL"] >= rvol_thr)
      & (out["RSI14"] >= 40.0)
  )

  return out


def forecast_linear(
    df: pd.DataFrame, lookback: int, steps: int
) -> pd.DataFrame:
  sub = df.tail(lookback).copy()
  x = np.arange(len(sub)).reshape(-1, 1)
  y = sub["Close"].to_numpy(dtype=float)

  model = LinearRegression()
  model.fit(x, y)

  future_x = np.arange(len(sub), len(sub) + steps).reshape(-1, 1)
  future_y = model.predict(future_x)

  last_ts = df.index[-1]
  if isinstance(last_ts, pd.DatetimeIndex):
    last_ts = last_ts[-1]

  if interval == "1d":
    freq = "B"  # Hari bekerja
  elif interval == "1h":
    freq = "h"
  else:
    freq = "15min"

  future_dates = pd.date_range(
      start=last_ts + pd.tseries.frequencies.to_offset(freq),
      periods=steps,
      freq=freq,
  )
  return pd.DataFrame({"Date": future_dates, "Forecast_Close": future_y})


# --- Proses Utama ---
if not ticker:
  st.warning("Sila masukkan simbol saham terlebih dahulu.")
  st.stop()

raw_df = load_stock_data(ticker, period, interval)
if raw_df.empty:
  st.error(
      f"Tiada data ditemui untuk '{ticker}' ({period}, {interval}). Semak"
      " simbol atau sambungan internet."
  )
  st.stop()

data = compute_indicators(raw_df, rvol_min, rsi_min, body_ratio_min)
fc_df = forecast_linear(data, lookback_days, forecast_steps)

latest = data.iloc[-1]
prev_close = data["Close"].iloc[-2] if len(data) > 1 else latest["Close"]
chg_pct = (
    ((latest["Close"] - prev_close) / prev_close * 100) if prev_close else 0.0
)

status_label = (
    "BOB AKTIF"
    if latest["BOB_Signal"]
    else ("BOD AKTIF" if latest["BOD_Signal"] else "STANDBY")
)

# --- Metrik Ringkasan ---
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Harga Terakhir", f"{latest['Close']:.3f}", f"{chg_pct:+.2f}%")
c2.metric(
    "RSI (14)",
    f"{latest['RSI14']:.1f}" if pd.notna(latest["RSI14"]) else "N/A",
)
c3.metric(
    "RVOL", f"{latest['RVOL']:.2f}x" if pd.notna(latest["RVOL"]) else "N/A"
)
c4.metric("Badan Lilin", f"{latest['BodyRatio']*100:.0f}%")
c5.metric("Status Setup", status_label)

# --- Carta Candlestick + EMA + Unjuran + RSI + RVOL ---
fig = make_subplots(
    rows=3,
    cols=1,
    shared_xaxes=True,
    vertical_spacing=0.04,
    row_heights=[0.6, 0.2, 0.2],
    subplot_titles=(
        f"{ticker} ({interval}) — Harga, EMA & Ramalan Linear",
        "RSI (14)",
        "RVOL (Relative Volume)",
    ),
)

fig.add_trace(
    go.Candlestick(
        x=data.index,
        open=data["Open"],
        high=data["High"],
        low=data["Low"],
        close=data["Close"],
        name="Harga",
    ),
    row=1,
    col=1,
)

fig.add_trace(
    go.Scatter(
        x=data.index,
        y=data["EMA20"],
        mode="lines",
        name="EMA 20",
        line=dict(color="orange", width=1.5),
    ),
    row=1,
    col=1,
)
fig.add_trace(
    go.Scatter(
        x=data.index,
        y=data["EMA50"],
        mode="lines",
        name="EMA 50",
        line=dict(color="deepskyblue", width=1.5),
    ),
    row=1,
    col=1,
)

# Garis Ramalan Regresi Linear
fig.add_trace(
    go.Scatter(
        x=fc_df["Date"],
        y=fc_df["Forecast_Close"],
        mode="lines+markers",
        name="Unjuran (Linear)",
        line=dict(color="mediumpurple", width=2, dash="dash"),
    ),
    row=1,
    col=1,
)

# Penanda BOB & BOD
bob_pts = data[data["BOB_Signal"]]
if not bob_pts.empty:
  fig.add_trace(
      go.Scatter(
          x=bob_pts.index,
          y=bob_pts["Low"] * 0.99,
          mode="markers",
          name="Isyarat BOB",
          marker=dict(symbol="triangle-up", size=11, color="lime"),
      ),
      row=1,
      col=1,
  )

bod_pts = data[data["BOD_Signal"]]
if not bod_pts.empty:
  fig.add_trace(
      go.Scatter(
          x=bod_pts.index,
          y=bod_pts["Low"] * 0.985,
          mode="markers",
          name="Isyarat BOD",
          marker=dict(symbol="diamond", size=9, color="cyan"),
      ),
      row=1,
      col=1,
  )

# Panel RSI
fig.add_trace(
    go.Scatter(
        x=data.index,
        y=data["RSI14"],
        mode="lines",
        name="RSI (14)",
        line=dict(color="gold", width=1.5),
    ),
    row=2,
    col=1,
)
fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1)
fig.add_hline(y=50, line_dash="dash", line_color="gray", row=2, col=1)
fig.add_hline(y=30, line_dash="dot", line_color="green", row=2, col=1)

# Panel RVOL
fig.add_trace(
    go.Bar(x=data.index, y=data["RVOL"], name="RVOL", marker_color="teal"),
    row=3,
    col=1,
)
fig.add_hline(
    y=rvol_min, line_dash="dash", line_color="orange", row=3, col=1
)

fig.update_layout(
    height=780,
    xaxis_rangeslider_visible=False,
    template="plotly_dark",
    hovermode="x unified",
)
st.plotly_chart(fig, use_container_width=True)

# --- Jadual Ramalan & Data Terkini ---
col_left, col_right = st.columns([1, 1.5])
with col_left:
  st.subheader("Jadual Unjuran Trend")
  fc_display = fc_df.copy()
  fc_display["Date"] = fc_display["Date"].dt.strftime("%Y-%m-%d %H:%M")
  fc_display["Forecast_Close"] = fc_display["Forecast_Close"].round(3)
  st.dataframe(fc_display, use_container_width=True, hide_index=True)

with col_right:
  st.subheader("10 Bar Terakhir")
  tail_cols = [
      "Open",
      "High",
      "Low",
      "Close",
      "Volume",
      "EMA20",
      "EMA50",
      "RSI14",
      "RVOL",
  ]
  st.dataframe(
      data[tail_cols].tail(10).round(3), use_container_width=True
  )
