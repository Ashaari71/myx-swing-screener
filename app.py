import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from statsmodels.tsa.holtwinters import Holt
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="MYX Swing Pro Screener", page_icon="📈", layout="wide"
)

st.title("📈 MYX Swing Pro: BOB & BOD Screener + RSI Momentum")
st.markdown(
    "Sistem imbasan automatik lanjutan lengkap dengan penapis RSI, pengiraan"
    " ATR Stop-Loss, sasaran untung (TP1), carta teknikal & unjuran Holt's Trend."
)

# --- KAMUS SEKTOR BERPOTENSI DI BURSA MALAYSIA ---
sector_dict = {
    "🔥 Pembinaan & Infrastruktur (Construction)": (
        "GAMUDA.KL, SUNCON.KL, IJM.KL, MRCB.KL, WCT.KL, KERJAYA.KL"
    ),
    "⚡ Tenaga Boleh Baharu & Utiliti (Energy/RE)": (
        "SAMAIDEN.KL, PEKAT.KL, TENAGA.KL, YTLPOWR.KL, MEGAFB.KL"
    ),
    "💻 Teknologi & Semikonduktor (Tech)": (
        "FRONTKN.KL, INARI.KL, KGB.KL, MYEG.KL, PENTA.KL, MPI.KL, UNISEM.KL"
    ),
    "🏥 Penjagaan Kesihatan (Healthcare)": (
        "KPJ.KL, IHH.KL, TOPGLOV.KL, HARTALEGA.KL"
    ),
    "🌾 Perladangan & Komoditi (Plantation)": (
        "KLK.KL, SDG.KL, IOICORP.KL, FGV.KL, HAPSENG.KL"
    ),
    "⚙️ Perindustrian & Telco (Industrial/Telco)": (
        "TMK.KL, CDB.KL, MAXIS.KL, SIME.KL, PMETAL.KL"
    ),
    "✨ Watchlist Utama Saya": (
        "TMK.KL, PEKAT.KL, KPJ.KL, SUNCON.KL, SAMAIDEN.KL, MAXIS.KL, TOPGLOV.KL, PJBUMI.KL"
    ),
}

# --- SIDEBAR: TETAPAN ---
st.sidebar.header("⚙️ Tetapan & Penapis Lanjutan")

selected_sector = st.sidebar.selectbox(
    "Pilih Sektor Pasaran:", list(sector_dict.keys())
)
default_tickers_for_sector = sector_dict[selected_sector]
ticker_input = st.sidebar.text_area(
    "Senarai Kod Kaunter:", default_tickers_for_sector
)

vol_mult = st.sidebar.slider(
    "Gandaan Volume Minimum (vs Purata 20H)", 0.8, 3.0, 1.2, 0.1
)
min_price = st.sidebar.number_input(
    "Harga Minimum (RM)", value=0.20, step=0.05
)
max_rsi = st.sidebar.slider(
    "Had Maksimum RSI (Elak Overbought Ekstrem)", 50, 95, 85, 1
)
include_watch = st.sidebar.checkbox(
    "Sertakan Kaunter WATCH (Jika Volum/Breakout Belum Penuh)", value=True
)

st.sidebar.subheader("📈 Tetapan Carta & Kaedah Ramalan")
forecast_method = st.sidebar.selectbox(
    "Kaedah Unjuran Harga:",
    ["Holt's Exponential Smoothing (Damped)", "Holt's Linear Trend", "EMA Momentum Projection"],
    index=0,
    help="Holt's Damped lebih selamat untuk saham kerana meredakan unjuran yang terlalu ekstrem."
)
lookback_trend = st.sidebar.slider(
    "Bilangan Hari Sejarah untuk Model", 20, 120, 45, 5
)
forecast_days = st.sidebar.slider(
    "Unjuran Hari ke Hadapan", 1, 15, 5, 1
)

run_scan = st.sidebar.button("🚀 Mula Imbas Pasaran Pro", type="primary")


@st.cache_data(ttl=300)
def get_stock_df(ticker: str) -> pd.DataFrame:
  df = yf.download(ticker, period="6mo", interval="1d", progress=False)
  if df is None or df.empty or len(df) < 30:
    return pd.DataFrame()
  if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)
  df = df.dropna(subset=["Open", "High", "Low", "Close", "Volume"]).copy()
  df.index = pd.to_datetime(df.index)
  return df


def enrich_indicators(df: pd.DataFrame) -> pd.DataFrame:
  out = df.copy()
  out["EMA20"] = out["Close"].ewm(span=20, adjust=False).mean()
  out["EMA50"] = out["Close"].ewm(span=50, adjust=False).mean()
  out["SMA200"] = (
      out["Close"].rolling(window=200).mean()
      if len(out) >= 200
      else out["Close"].rolling(window=len(out)).mean()
  )
  out["AvgVol20"] = out["Volume"].rolling(window=20).mean()
  out["RVOL"] = out["Volume"] / out["AvgVol20"].replace(0, np.nan)

  high_low = out["High"] - out["Low"]
  high_close = np.abs(out["High"] - out["Close"].shift())
  low_close = np.abs(out["Low"] - out["Close"].shift())
  true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
  out["ATR"] = true_range.rolling(window=14).mean()

  delta = out["Close"].diff()
  gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
  loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
  rs = gain / loss.replace(0, np.nan)
  out["RSI"] = 100 - (100 / (1 + rs))
  return out


def forecast_prices(
    df: pd.DataFrame, lookback: int, steps: int, method: str
) -> pd.DataFrame:
  sub = df.tail(lookback).copy()
  y = sub["Close"].to_numpy(dtype=float)

  if "Holt's" in method:
    is_damped = "Damped" in method
    model = Holt(y, damped_trend=is_damped, initialization_method="estimated")
    fit = model.fit(optimized=True)
    future_y = fit.forecast(steps)
  else:
    # EMA Momentum Projection: unjurkan berdasarkan purata perubahan harian EMA20 terkini
    ema_series = sub["EMA20"].to_numpy(dtype=float)
    slope = (ema_series[-1] - ema_series[-5]) / 5.0 if len(ema_series) >= 5 else 0.0
    future_y = np.array([y[-1] + (slope * (i + 1)) for i in range(steps)])

  # Pastikan unjuran tidak jatuh ke paras negatif
  future_y = np.maximum(0.005, future_y)

  last_date = df.index[-1]
  future_dates = pd.date_range(
      start=last_date + pd.tseries.frequencies.to_offset("B"),
      periods=steps,
      freq="B",
  )
  return pd.DataFrame({"Tarikh": future_dates, "Ramalan (RM)": future_y})


tickers = [
    t.strip().upper().replace(" ", "")
    for t in ticker_input.replace("\n", ",").split(",")
    if t.strip()
]

tab_screener, tab_chart = st.tabs(
    ["📋 Hasil Imbasan Screener", "📊 Carta & Ramalan Trend"]
)

with tab_screener:
  if run_scan:
    scan_results = []
    skipped_tickers = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    total = max(1, len(tickers))
    for idx, ticker in enumerate(tickers):
      status_text.text(f"Sedang mengimbas [{idx+1}/{total}]: {ticker}...")

      try:
        raw_df = get_stock_df(ticker)
        if raw_df.empty:
          skipped_tickers.append(ticker)
          continue

        df = enrich_indicators(raw_df)
        last_close = float(df["Close"].iloc[-1])
        last_vol = float(df["Volume"].iloc[-1])
        avg_vol = (
            float(df["AvgVol20"].iloc[-1])
            if pd.notna(df["AvgVol20"].iloc[-1])
            else 0.0
        )
        rvol = float(df["RVOL"].iloc[-1]) if pd.notna(df["RVOL"].iloc[-1]) else 0.0
        ema20 = float(df["EMA20"].iloc[-1])
        ema50 = float(df["EMA50"].iloc[-1])
        sma200 = (
            float(df["SMA200"].iloc[-1])
            if not np.isnan(df["SMA200"].iloc[-1])
            else ema50
        )
        atr = (
            float(df["ATR"].iloc[-1])
            if pd.notna(df["ATR"].iloc[-1])
            else last_close * 0.03
        )
        rsi = float(df["RSI"].iloc[-1]) if pd.notna(df["RSI"].iloc[-1]) else 50.0

        if last_close < min_price or rsi > max_rsi:
          continue

        is_uptrend = (
            (last_close > ema20)
            and (ema20 > ema50)
            and (last_close >= sma200 * 0.98)
        )
        vol_spike = avg_vol > 0 and (last_vol >= avg_vol * vol_mult)

        highest_base = float(df["High"].iloc[-21:-1].max())
        lowest_base = float(df["Low"].iloc[-21:-1].min())
        base_range_pct = (
            (highest_base - lowest_base) / lowest_base
            if lowest_base > 0
            else 1.0
        )

        is_bob = (
            is_uptrend
            and (base_range_pct <= 0.25)
            and (last_close >= highest_base * 0.995)
            and vol_spike
        )
        recent_high = float(df["High"].iloc[-10:-2].max())
        is_bod = (
            (last_close > ema50)
            and (last_close > recent_high)
            and vol_spike
            and not is_bob
        )

        signal = "-"
        if is_bob:
          signal = "🔥 BOB (Breakout of Base)"
        elif is_bod:
          signal = "⚡ BOD (Breakout of Downtrend)"
        elif is_uptrend and vol_spike:
          signal = "✨ Volume Spike (Potensi)"
        elif include_watch:
          signal = "👀 WATCH (Pantauan)"

        if signal != "-":
          stop_loss = round(max(0.005, last_close - (atr * 1.5)), 3)
          tp1 = round(
              last_close + (max(0.01, last_close - stop_loss) * 1.5), 3
          )

          scan_results.append({
              "Kaunter": ticker.replace(".KL", ""),
              "Harga (RM)": round(last_close, 3),
              "RVOL": round(rvol, 2),
              "Status Isyarat": signal,
              "RSI (14)": round(rsi, 1),
              "Volume Terkini": int(last_vol),
              "Cadangan Stop-Loss (RM)": stop_loss,
              "Sasaran Untung (TP1)": tp1,
          })
      except Exception:
        skipped_tickers.append(ticker)

      progress_bar.progress((idx + 1) / total)

    status_text.text("Imbasan selesai!")

    if scan_results:
      st.success(
          f"Berjaya memaparkan {len(scan_results)} kaunter mengikut tetapan"
          " semasa!"
      )
      result_df = pd.DataFrame(scan_results)
      st.dataframe(result_df, use_container_width=True, hide_index=True)

      csv_data = result_df.to_csv(index=False).encode("utf-8")
      st.download_button(
          label="📥 Muat Turun Laporan Pro (CSV)",
          data=csv_data,
          file_name=f"bursa_pro_{selected_sector[:10].strip()}.csv",
          mime="text/csv",
      )
    else:
      st.warning(
          "Tiada kaunter yang memenuhi kriteria dengan penapis semasa."
      )

    if skipped_tickers:
      st.caption(
          "Kaunter tiada data / dilangkau: " + ", ".join(skipped_tickers)
      )
  else:
    st.info(
        "👈 Pilih sektor, laraskan tetapan di sidebar, dan klik **Mula Imbas"
        " Pasaran Pro**."
    )

with tab_chart:
  col_a, col_b = st.columns([2, 1])
  with col_a:
    selected_sym = st.selectbox(
        "Pilih Kaunter untuk Carta & Ramalan:",
        tickers if tickers else ["SUNCON.KL"],
        index=0,
    )
  with col_b:
    custom_sym = (
        st.text_input("Atau Masukkan Simbol Manual:", value="")
        .strip()
        .upper()
    )

  target_sym = custom_sym if custom_sym else selected_sym
  raw_c = get_stock_df(target_sym)

  if raw_c.empty:
    st.error(f"Tiada data carta ditemui untuk **{target_sym}**.")
  else:
    c_df = enrich_indicators(raw_c)
    fc_df = forecast_prices(c_df, lookback_trend, forecast_days, forecast_method)

    # Sambungkan titik terakhir sebenar ke titik pertama ramalan supaya garis bersambung kemas
    last_actual_row = pd.DataFrame({
        "Tarikh": [c_df.index[-1]],
        "Ramalan (RM)": [float(c_df["Close"].iloc[-1])],
    })
    plot_fc_df = pd.concat([last_actual_row, fc_df], ignore_index=True)

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.6, 0.2, 0.2],
        subplot_titles=(
            f"{target_sym} (1D) — Candlestick, EMA 20/50 & {forecast_method}",
            "RSI (14)",
            "RVOL",
        ),
    )

    fig.add_trace(
        go.Candlestick(
            x=c_df.index,
            open=c_df["Open"],
            high=c_df["High"],
            low=c_df["Low"],
            close=c_df["Close"],
            name="Harga",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=c_df.index,
            y=c_df["EMA20"],
            mode="lines",
            name="EMA 20",
            line=dict(color="orange", width=1.5),
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=c_df.index,
            y=c_df["EMA50"],
            mode="lines",
            name="EMA 50",
            line=dict(color="deepskyblue", width=1.5),
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=plot_fc_df["Tarikh"],
            y=plot_fc_df["Ramalan (RM)"],
            mode="lines+markers",
            name="Unjuran Harga",
            line=dict(color="mediumpurple", width=2.2, dash="dash"),
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=c_df.index,
            y=c_df["RSI"],
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
            x=c_df.index,
            y=c_df["RVOL"],
            name="RVOL",
            marker_color="teal",
        ),
        row=3,
        col=1,
    )
    fig.add_hline(
        y=vol_mult, line_dash="dash", line_color="orange", row=3, col=1
    )

    fig.update_layout(
        height=760,
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader(f"Jadual Unjuran Harga ({forecast_method})")
    fc_out = fc_df.copy()
    fc_out["Tarikh"] = fc_out["Tarikh"].dt.strftime("%Y-%m-%d")
    fc_out["Ramalan (RM)"] = fc_out["Ramalan (RM)"].round(3)
    st.dataframe(fc_out, use_container_width=True, hide_index=True)
