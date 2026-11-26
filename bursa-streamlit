import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.linear_model import LinearRegression
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="MYX Swing Pro Screener & Chart", layout="wide")

st.title("📈 MYX Swing Pro: BOB & BOD Screener + RSI Momentum")
st.caption(
    "Imbasan automatik kaunter Bursa Malaysia dengan penapis volum, RSI,"
    " anggaran ATR Stop-Loss/TP1, carta teknikal & unjuran regresi linear."
)

# --- Sidebar: Tetapan & Penapis Lanjutan ---
st.sidebar.header("⚙️ Tetapan & Penapis Lanjutan")

sector_presets = {
    "Pembinaan & Infrastruktur (Construction)": (
        "GAMUDA.KL, SUNCON.KL, IJM.KL, MRCB.KL, WCT.KL, KERJAYA.KL"
    ),
    "Teknologi (Technology)": "INARI.KL, FRONTKN.KL, GREATEC.KL, VITROX.KL, MI.KL",
    "Tenaga & Utiliti": "TENAGA.KL, YINSON.KL, DIALOG.KL, PEKAT.KL, SAMAIDEN.KL",
    "Penjagaan Kesihatan & Lain-lain": "KPJ.KL, IHH.KL, MAXIS.KL, TOPGLOV.KL",
}

selected_sector = st.sidebar.selectbox(
    "Pilih Sektor Pasaran:", list(sector_presets.keys()), index=0
)
default_tickers_str = sector_presets[selected_sector]

raw_tickers_input = st.sidebar.text_area(
    "Senarai Kod Kaunter:",
    value=default_tickers_str,
    height=110,
    help="Pisahkan simbol dengan koma atau baris baharu, contoh: SUNCON.KL, GAMUDA.KL",
)

vol_mult_min = st.sidebar.slider(
    "Gandaan Volume Minimum (vs Purata 20H)",
    min_value=0.50,
    max_value=5.00,
    value=1.50,
    step=0.05,
)

min_price = st.sidebar.number_input(
    "Harga Minimum (RM)", min_value=0.0, max_value=100.0, value=0.20, step=0.05
)

max_rsi = st.sidebar.slider(
    "Had Maksimum RSI (Elak Overbought Ekstrem)",
    min_value=50.0,
    max_value=95.0,
    value=75.0,
    step=1.0,
)

st.sidebar.subheader("📐 Tetapan Carta & Ramalan Trend")
period = st.sidebar.selectbox(
    "Tempoh Data Sejarah", ["3mo", "6mo", "1y", "2y"], index=1
)
interval = st.sidebar.selectbox(
    "Selang Masa (Interval)", ["1d", "1h", "15m"], index=0
)
lookback_bars = st.sidebar.slider(
    "Bilangan Bar Terakhir (Fit Trend)", min_value=10, max_value=90, value=30, step=5
)
forecast_steps = st.sidebar.slider(
    "Langkah Ramalan ke Hadapan", min_value=1, max_value=15, value=5, step=1
)

run_scan = st.sidebar.button("🚀 Mula Imbas Pasaran Pro", type="primary")


def parse_tickers(text: str) -> list[str]:
  parts = [
      t.strip().upper() for t in text.replace("\n", ",").split(",") if t.strip()
  ]
  seen = []
  for p in parts:
    if p not in seen:
      seen.append(p)
  return seen


@st.cache_data(ttl=300)
def fetch_ohlcv(symbol: str, per: str, inter: str) -> pd.DataFrame:
  df = yf.download(symbol, period=per, interval=inter, progress=False)
  if df is None or df.empty:
    return pd.DataFrame()
  if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)
  required = ["Open", "High", "Low", "Close", "Volume"]
  if not all(col in df.columns for col in required):
    return pd.DataFrame()
  df = df.dropna(subset=required).copy()
  df.index = pd.to_datetime(df.index)
  return df


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
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

  # ATR (14) untuk rujukan Stop-Loss / TP1
  prev_close = out["Close"].shift(1)
  tr = pd.concat(
      [
          (out["High"] - out["Low"]).abs(),
          (out["High"] - prev_close).abs(),
          (out["Low"] - prev_close).abs(),
      ],
      axis=1,
  ).max(axis=1)
  out["ATR14"] = tr.rolling(14).mean()

  # Struktur lilin & isyarat BOB / BOD asas
  rng = (out["High"] - out["Low"]).replace(0, np.nan)
  body = (out["Close"] - out["Open"]).abs()
  out["BodyRatio"] = (body / rng).fillna(0.0)
  bullish_candle = (out["Close"] > out["Open"]) & (out["BodyRatio"] >= 0.45)

  high_20_prev = out["High"].shift(1).rolling(20).max()
  out["BOB"] = bullish_candle & (out["Close"] > high_20_prev)

  near_support = (out["Low"] <= out["EMA20"] * 1.015) & (
      out["Close"] >= out["EMA20"] * 0.99
  )
  out["BOD"] = bullish_candle & near_support & (out["Close"] >= out["EMA50"] * 0.98)

  return out


def forecast_linear_trend(
    df: pd.DataFrame, lookback: int, steps: int, inter: str
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

  if inter == "1d":
    freq = "B"
  elif inter == "1h":
    freq = "h"
  else:
    freq = "15min"

  future_dates = pd.date_range(
      start=last_ts + pd.tseries.frequencies.to_offset(freq),
      periods=steps,
      freq=freq,
  )
  return pd.DataFrame({"Date": future_dates, "Forecast_Close": future_y})


def scan_tickers(
    tickers: list[str],
    per: str,
    inter: str,
    vol_thr: float,
    price_thr: float,
    rsi_cap: float,
) -> pd.DataFrame:
  rows = []
  for sym in tickers:
    raw = fetch_ohlcv(sym, per, inter)
    if raw.empty or len(raw) < 25:
      continue
    ind = add_indicators(raw)
    last = ind.iloc[-1]
    prev = ind.iloc[-2]

    close_val = float(last["Close"])
    prev_val = float(prev["Close"]) if float(prev["Close"]) != 0 else close_val
    chg_pct = ((close_val - prev_val) / prev_val) * 100
    rvol_val = float(last["RVOL"]) if pd.notna(last["RVOL"]) else 0.0
    rsi_val = float(last["RSI14"]) if pd.notna(last["RSI14"]) else 50.0
    atr_val = (
        float(last["ATR14"]) if pd.notna(last["ATR14"]) else close_val * 0.03
    )

    if close_val < price_thr:
      continue
    if rvol_val < vol_thr:
      continue
    if rsi_val > rsi_cap:
      continue

    setup = (
        "BOB"
        if bool(last["BOB"])
        else ("BOD" if bool(last["BOD"]) else "WATCH")
    )
    stop_loss = max(0.005, close_val - (1.5 * atr_val))
    tp1 = close_val + (2.0 * atr_val)

    rows.append({
        "Kaunter": sym,
        "Harga": round(close_val, 3),
        "Perubahan %": round(chg_pct, 2),
        "RVOL": round(rvol_val, 2),
        "RSI(14)": round(rsi_val, 1),
        "Setup": setup,
        "Est. SL (1.5 ATR)": round(stop_loss, 3),
        "Est. TP1 (2.0 ATR)": round(tp1, 3),
    })

  if not rows:
    return pd.DataFrame()
  return pd.DataFrame(rows).sort_values(by="RVOL", ascending=False)


# --- Antaramuka Utama (Tab Screener & Tab Carta + Ramalan) ---
tab_scan, tab_chart = st.tabs(
    ["🔍 Screener BOB & BOD", "📊 Carta & Ramalan Trend"]
)

ticker_list = parse_tickers(raw_tickers_input)

with tab_scan:
  if run_scan:
    with st.spinner("Mengimbas kaunter yang dipilih..."):
      scan_df = scan_tickers(
          ticker_list, period, interval, vol_mult_min, min_price, max_rsi
      )
    if scan_df.empty:
      st.warning(
          "Tiada kaunter melepasi syarat penapis semasa. Cuba turunkan"
          " Gandaan Volume Minimum atau laraskan Had Maksimum RSI."
      )
    else:
      st.success(f"Ditemui {len(scan_df)} kaunter melepasi penapis.")
      st.dataframe(scan_df, use_container_width=True, hide_index=True)
  else:
    st.info(
        "Pilih sektor atau ubah senarai kaunter di sidebar, kemudian klik **Mula"
        " Imbas Pasaran Pro**."
    )

with tab_chart:
  col_sel, col_man = st.columns([2, 1])
  with col_sel:
    chosen_from_list = st.selectbox(
        "Pilih Kaunter daripada Senarai:",
        ticker_list if ticker_list else ["SUNCON.KL"],
        index=0,
    )
  with col_man:
    manual_sym = (
        st.text_input("Atau Taip Simbol Manual:", value="")
        .strip()
        .upper()
    )

  active_sym = manual_sym if manual_sym else chosen_from_list
  df_sym = fetch_ohlcv(active_sym, period, interval)

  if df_sym.empty:
    st.error(f"Tiada data carta ditemui untuk **{active_sym}**.")
  else:
    ind_df = add_indicators(df_sym)
    fc_df = forecast_linear_trend(ind_df, lookback_bars, forecast_steps, interval)

    latest = ind_df.iloc[-1]
    prev_c = (
        ind_df["Close"].iloc[-2] if len(ind_df) > 1 else latest["Close"]
    )
    chg_p = ((latest["Close"] - prev_c) / prev_c * 100) if prev_c else 0.0
    st_label = (
        "BOB"
        if bool(latest["BOB"])
        else ("BOD" if bool(latest["BOD"]) else "STANDBY")
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Harga Terakhir", f"{latest['Close']:.3f}", f"{chg_p:+.2f}%")
    m2.metric(
        "RSI (14)",
        f"{latest['RSI14']:.1f}" if pd.notna(latest["RSI14"]) else "N/A",
    )
    m3.metric(
        "RVOL", f"{latest['RVOL']:.2f}x" if pd.notna(latest["RVOL"]) else "N/A"
    )
    m4.metric("Status", st_label)

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.6, 0.2, 0.2],
        subplot_titles=(
            f"{active_sym} ({interval}) — Candlestick, EMA 20/50 & Ramalan"
            " Linear",
            "RSI (14)",
            "RVOL",
        ),
    )

    fig.add_trace(
        go.Candlestick(
            x=ind_df.index,
            open=ind_df["Open"],
            high=ind_df["High"],
            low=ind_df["Low"],
            close=ind_df["Close"],
            name="Harga",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=ind_df.index,
            y=ind_df["EMA20"],
            mode="lines",
            name="EMA 20",
            line=dict(color="orange", width=1.5),
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=ind_df.index,
            y=ind_df["EMA50"],
            mode="lines",
            name="EMA 50",
            line=dict(color="deepskyblue", width=1.5),
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=fc_df["Date"],
            y=fc_df["Forecast_Close"],
            mode="lines+markers",
            name="Unjuran Linear",
            line=dict(color="mediumpurple", width=2, dash="dash"),
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=ind_df.index,
            y=ind_df["RSI14"],
            mode="lines",
            name="RSI(14)",
            line=dict(color="gold", width=1.5),
        ),
        row=2,
        col=1,
    )
    fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1)
    fig.add_hline(y=50, line_dash="dash", line_color="gray", row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="green", row=2, col=1)

    fig.add_trace(
        go.Bar(
            x=ind_df.index,
            y=ind_df["RVOL"],
            name="RVOL",
            marker_color="teal",
        ),
        row=3,
        col=1,
    )
    fig.add_hline(
        y=vol_mult_min, line_dash="dash", line_color="orange", row=3, col=1
    )

    fig.update_layout(
        height=760,
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Jadual Unjuran Regresi Linear")
    fc_show = fc_df.copy()
    fc_show["Date"] = fc_show["Date"].dt.strftime("%Y-%m-%d %H:%M")
    fc_show["Forecast_Close"] = fc_show["Forecast_Close"].round(3)
    st.dataframe(fc_show, use_container_width=True, hide_index=True)
