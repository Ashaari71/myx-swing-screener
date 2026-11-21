import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="Bursa Volume Footprint (15m)",
    layout="wide",
)

st.title("📊 Anggaran Volume Footprint 15-Minit — Bursa Malaysia")
st.caption(
    "Menggunakan data intraday 1-minit (yfinance) untuk menganggarkan Bid vs"
    " Ask Volume, POC, dan Delta setiap selang 15 minit."
)

# --- SIDEBAR: KAWALAN PENGGUNA ---
with st.sidebar:
  st.header("⚙️ Tetapan Carta")

  watchlist = {
      "Maybank (1155.KL)": "1155.KL",
      "Tenaga Nasional (5347.KL)": "5347.KL",
      "CIMB Group (1023.KL)": "1023.KL",
      "Frontken (0128.KL)": "0128.KL",
      "Sunway Construction (5263.KL)": "5263.KL",
      "Samaiden (0223.KL)": "0223.KL",
      "Pekat Group (0233.KL)": "0233.KL",
      "KPJ Healthcare (5878.KL)": "5878.KL",
      "Maxis (6012.KL)": "6012.KL",
      "Top Glove (7113.KL)": "7113.KL",
      "Input Manual...": "MANUAL",
  }

  pilihan = st.selectbox("Pilih Kaunter Bursa:", list(watchlist.keys()))
  if watchlist[pilihan] == "MANUAL":
    ticker = (
        st.text_input("Masukkan Simbol (.KL):", value="0128.KL").strip().upper()
    )
    if ticker and not ticker.endswith(".KL"):
      ticker = f"{ticker}.KL"
  else:
    ticker = watchlist[pilihan]

  period = st.selectbox("Tempoh Data 1m:", ["1d", "2d", "5d", "7d"], index=2)
  price_step = st.select_slider(
      "Julat Harga / Tick Aggregation (RM):",
      options=[0.005, 0.01, 0.02, 0.05, 0.10],
      value=0.01,
  )
  last_n_bars = st.slider(
      "Bilangan Bar 15-Minit Dipaparkan:", min_value=6, max_value=32, value=16
  )
  show_text = st.checkbox(
      "Papar Label Bid x Ask di Carta",
      value=True,
      help="Nyahaktifkan jika carta terlalu padat.",
  )


@st.cache_data(ttl=120)
def fetch_1m_bursa(symbol: str, lookback: str) -> pd.DataFrame:
  df = yf.download(symbol, interval="1m", period=lookback, progress=False)
  if df.empty:
    return pd.DataFrame()

  if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

  df = df[["Open", "High", "Low", "Close", "Volume"]].dropna().copy()
  df.index = pd.to_datetime(df.index)

  if df.index.tz is not None:
    df.index = df.index.tz_convert("Asia/Kuala_Lumpur")
  return df


def build_15m_footprint(df_1m: pd.DataFrame, step: float, n_bars: int):
  work = df_1m.copy()
  work["ask_vol"] = np.where(work["Close"] >= work["Open"], work["Volume"], 0.0)
  work["bid_vol"] = np.where(work["Close"] < work["Open"], work["Volume"], 0.0)
  work["bar_15m"] = work.index.floor("15min")

  ohlc_15m = (
      work.groupby("bar_15m")
      .agg(
          Open=("Open", "first"),
          High=("High", "max"),
          Low=("Low", "min"),
          Close=("Close", "last"),
          Volume=("Volume", "sum"),
          Ask_Vol=("ask_vol", "sum"),
          Bid_Vol=("bid_vol", "sum"),
      )
      .dropna()
  )
  ohlc_15m["Delta"] = ohlc_15m["Ask_Vol"] - ohlc_15m["Bid_Vol"]
  ohlc_15m["Cumulative_Delta"] = ohlc_15m["Delta"].cumsum()

  ohlc_15m = ohlc_15m.tail(n_bars)
  active_bars = set(ohlc_15m.index)
  work = work[work["bar_15m"].isin(active_bars)].copy()

  work["price_level"] = (np.round(work["Close"] / step) * step).round(4)

  fp = (
      work.groupby(["bar_15m", "price_level"], as_index=False)
      .agg(
          bid=("bid_vol", "sum"),
          ask=("ask_vol", "sum"),
          vol=("Volume", "sum"),
      )
      .assign(delta=lambda x: x["ask"] - x["bid"])
  )

  poc_map = (
      fp.sort_values("vol", ascending=False)
      .groupby("bar_15m", as_index=False)
      .first()[["bar_15m", "price_level"]]
      .rename(columns={"price_level": "POC_Price"})
  )

  summary_df = ohlc_15m.reset_index().merge(poc_map, on="bar_15m", how="left")
  return ohlc_15m, fp, poc_map, summary_df


def plot_footprint(
    symbol: str,
    ohlc_15m: pd.DataFrame,
    fp: pd.DataFrame,
    poc_map: pd.DataFrame,
    display_labels: bool,
):
  fig = go.Figure()

  fig.add_trace(
      go.Candlestick(
          x=ohlc_15m.index,
          open=ohlc_15m["Open"],
          high=ohlc_15m["High"],
          low=ohlc_15m["Low"],
          close=ohlc_15m["Close"],
          name=f"{symbol} (15m)",
          increasing_line_color="#16a34a",
          decreasing_line_color="#dc2626",
      )
  )

  annotations = []
  if display_labels:
    for _, row in fp.iterrows():
      if row["vol"] <= 0:
        continue
      delta_val = int(row["delta"])
      sign = "+" if delta_val > 0 else ""
      label_text = (
          f"{int(row['bid']):,}x{int(row['ask']):,} ({sign}{delta_val:,})"
      )
      font_color = "#15803d" if delta_val >= 0 else "#b91c1c"

      annotations.append(
          dict(
              x=row["bar_15m"],
              y=row["price_level"],
              text=label_text,
              showarrow=False,
              font=dict(size=9, color=font_color),
              bgcolor="rgba(255,255,255,0.8)",
              borderpad=1,
          )
      )

  fig.add_trace(
      go.Scatter(
          x=poc_map["bar_15m"],
          y=poc_map["POC_Price"],
          mode="markers",
          name="POC (15m)",
          marker=dict(
              symbol="diamond",
              size=10,
              color="#f59e0b",
              line=dict(color="#111827", width=1),
          ),
      )
  )

  fig.update_layout(
      title=f"Anggaran Volume Footprint 15-Minit — {symbol}",
      xaxis_title="Masa (MYT)",
      yaxis_title="Harga (RM)",
      xaxis_rangeslider_visible=False,
      annotations=annotations,
      template="plotly_white",
      height=680,
      margin=dict(l=20, r=20, t=50, b=20),
  )

  fig.update_xaxes(
      rangebreaks=[
          dict(bounds=["sat", "mon"]),
          dict(bounds=[17.5, 9.0], pattern="hour"),
      ]
  )
  return fig


# --- PAPARAN UTAMA ---
if not ticker:
  st.warning("Sila masukkan simbol saham Bursa Malaysia yang sah.")
  st.stop()

with st.spinner(f"Memuat turun data intraday 1-minit untuk {ticker}..."):
  df_1m = fetch_1m_bursa(ticker, period)

if df_1m.empty:
  st.error(
      f"Tiada data 1-minit dijumpai untuk **{ticker}**. Pastikan kod saham"
      " betul (contoh: `1155.KL`) dan kaunter aktif didagangkan."
  )
  st.stop()

ohlc_15m, fp, poc_map, summary_df = build_15m_footprint(
    df_1m, price_step, last_n_bars
)

# Kad Metrik Ringkas di Bahagian Atas
latest_bar = summary_df.iloc[-1]
total_period_delta = int(summary_df["Delta"].sum())

c1, c2, c3, c4 = st.columns(4)
c1.metric("Harga Terakhir", f"RM {latest_bar['Close']:.3f}")
c2.metric("POC Bar Terkini", f"RM {latest_bar['POC_Price']:.3f}")
c3.metric("Delta Bar Terkini", f"{int(latest_bar['Delta']):+,}")
c4.metric(f"Jumlah Delta ({last_n_bars} Bar)", f"{total_period_delta:+,}")

# Plot Carta Utama
fig = plot_footprint(ticker, ohlc_15m, fp, poc_map, show_text)
st.plotly_chart(fig, use_container_width=True)

# --- JADUAL RINGKASAN DELTA PER BAR ---
st.subheader("📋 Ringkasan Delta & POC Setiap Bar (15-Minit)")

display_table = summary_df[[
    "bar_15m",
    "Open",
    "High",
    "Low",
    "Close",
    "POC_Price",
    "Bid_Vol",
    "Ask_Vol",
    "Delta",
    "Cumulative_Delta",
]].copy()

display_table["bar_15m"] = display_table["bar_15m"].dt.strftime("%Y-%m-%d %H:%M")
display_table.columns = [
    "Masa (MYT)",
    "Open",
    "High",
    "Low",
    "Close",
    "POC (RM)",
    "Bid Vol",
    "Ask Vol",
    "Bar Delta",
    "Cum. Delta",
]

# Susun dari bar paling terkini di atas
display_table = display_table.iloc[::-1].reset_index(drop=True)

st.dataframe(
    display_table.style.format({
        "Open": "{:.3f}",
        "High": "{:.3f}",
        "Low": "{:.3f}",
        "Close": "{:.3f}",
        "POC (RM)": "{:.3f}",
        "Bid Vol": "{:,.0f}",
        "Ask Vol": "{:,.0f}",
        "Bar Delta": "{:+,.0f}",
        "Cum. Delta": "{:+,.0f}",
    }),
    use_container_width=True,
    hide_index=True,
)
