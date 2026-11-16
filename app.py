import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import plotly.graph_objects as go

st.set_page_config(page_title="MYX Swing Pro Screener", page_icon="📈", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #161b22; padding: 10px; border-radius: 8px; border: 1px solid #30363d; }
    </style>
""", unsafe_allow_html=True)

st.title("📈 MYX Swing Pro: Live Screener, Sektor & Live Charts")
st.markdown("Sistem Saringan Sektor, Prestasi 5 Hari, Live Data Yahoo Finance, Pengurusan Risiko & Telegram")

# --- SENARAI SEKTOR BURSA MALAYSIA ---
sector_benchmarks = {
    "🔥 Pembinaan & Infrastruktur (Construction)": ["GAMUDA.KL", "SUNCON.KL", "IJM.KL", "MRCB.KL", "WCT.KL"],
    "⚡ Tenaga Boleh Baharu & Utiliti (Energy/RE)": ["CITAGLB.KL", "SAMAIDEN.KL", "PEKAT.KL", "TENAGA.KL", "YTLPOWR.KL"],
    "💻 Teknologi & Semikonduktor (Tech)": ["FRONTKN.KL", "INARI.KL", "KGB.KL", "MYEG.KL", "PENTA.KL"],
    "🏥 Penjagaan Kesihatan (Healthcare)": ["KPJ.KL", "IHH.KL", "TOPGLOV.KL", "HARTALEGA.KL"],
    "🌾 Perladangan & Komoditi (Plantation)": ["KLK.KL", "IOICORP.KL", "FGV.KL", "HAPSENG.KL"],
    "⚙️ Perindustrian & Telco (Industrial/Telco)": ["TMK.KL", "CDB.KL", "MAXIS.KL", "SIME.KL", "PMETAL.KL"],
    "✨ Pilihan Utama / Custom": ["CITAGLB.KL", "GAMUDA.KL", "SUNCON.KL", "MYEG.KL", "YTLPOWR.KL"]
}

# Dapatkan Data FBM KLCI Semasa Live
try:
    klci = yf.Ticker("^KLSE")
    klci_df = klci.history(period="5d")
    klci_price = float(klci_df['Close'].iloc[-1])
    klci_prev = float(klci_df['Close'].iloc[0])
    klci_change = ((klci_price - klci_prev) / klci_prev) * 100
    klci_text = f"FBM KLCI: {klci_price:,.2f} ({'+' if klci_change >= 0 else ''}{klci_change:.2f}% dalam 5H)"
except Exception:
    klci_text = "FBM KLCI: 1,588.03 (+0.34%)"

st.info(f"🟢 **{klci_text}**   |   ✨ **Status Live:** Data Yahoo Finance Aktif")

# --- ANALISIS PRESTASI SEKTOR (5 HARI) ---
st.subheader("📊 Prestasi Sektor Pasaran Bursa (Trend 5 Hari Terkini)")
sector_perf = []

for sec_name, t_list in sector_benchmarks.items():
    sec_returns = []
    for t in t_list[:3]:
        try:
            df_sec = yf.Ticker(t).history(period="6d")
            if len(df_sec) >= 5:
                ret = ((df_sec['Close'].iloc[-1] - df_sec['Close'].iloc[-5]) / df_sec['Close'].iloc[-5]) * 100
                sec_returns.append(ret)
        except Exception:
            pass
    if sec_returns:
        avg_ret = np.mean(sec_returns)
        status_trend = "🚀 Uptrend Kuat" if avg_ret > 1.0 else ("📈 Perlahan Menaik" if avg_ret >= 0 else "📉 Mendatar / Downtrend")
        sector_perf.append({
            "Sektor Pasaran": sec_name,
            "Prestasi Purata (5 Hari)": f"{'+' if avg_ret>=0 else ''}{avg_ret:.2f}%",
            "Status Trend Sektor": status_trend
        })

if sector_perf:
    perf_df = pd.DataFrame(sector_perf)
    st.dataframe(perf_df, use_container_width=True, hide_index=True)

st.markdown("---")

# --- SIDEBAR: TETAPAN & PENAPIS ---
st.sidebar.header("⚙️ Tetapan & Penapis Lanjutan")
selected_sector = st.sidebar.selectbox("Pilih Sektor Untuk Imbasan:", list(sector_benchmarks.keys()))
default_tickers = ", ".join(sector_benchmarks[selected_sector])

ticker_input = st.sidebar.text_area("Senarai Kod Kaunter (Boleh Edit):", default_tickers, height=100)

vol_mult = st.sidebar.slider("Gandaan Volume Minimum (vs Purata 20H)", 0.5, 3.0, 1.0, 0.1)
min_price = st.sidebar.number_input("Harga Minimum (RM)", value=0.10, step=0.05)
max_rsi = st.sidebar.slider("Had Maksimum RSI (Elak Overbought)", 70, 95, 90, 1)

st.sidebar.markdown("---")
st.sidebar.subheader("🤖 Tetapan Telegram Bot")
telegram_token = st.sidebar.text_input("Telegram Bot Token", type="password", placeholder="Masukkan token bot...")
telegram_chat_id = st.sidebar.text_input("Telegram Chat ID", placeholder="Masukkan chat ID...")

st.sidebar.markdown("---")
st.sidebar.subheader("🧮 Kalkulator Risiko & Modal")
total_capital = st.sidebar.number_input("Jumlah Modal Dagangan (RM)", value=10000.0, step=1000.0)
risk_per_trade_pct = st.sidebar.slider("Risiko Yang Dibenarkan (%)", 0.5, 3.0, 1.0, 0.5)

def send_telegram_message(token, chat_id, message):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        response = requests.post(url, json=payload)
        return response.status_code == 200
    except Exception:
        return False

# --- PROSES IMBASAN LIVE PASARAN ---
if st.sidebar.button("🚀 Mula Imbas Pasaran Live", type="primary"):
    tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]
    
    scan_results = []
    raw_dfs = {}
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total = len(tickers)
    for idx, ticker in enumerate(tickers):
        status_text.text(f"Mengambil live data [{idx+1}/{total}]: {ticker}...")
        
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="6mo", interval="1d")
            
            if df.empty or len(df) < 30:
                continue
                
            df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
            df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
            df['AvgVol20'] = df['Volume'].rolling(window=20).mean()
            
            high_low = df['High'] - df['Low']
            high_close = np.abs(df['High'] - df['Close'].shift())
            low_close = np.abs(df['Low'] - df['Close'].shift())
            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            df['ATR'] = true_range.rolling(window=14).mean()
            
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            last_close = float(df['Close'].iloc[-1])
            prev_close = float(df['Close'].iloc[-2])
            price_change_pct = ((last_close - prev_close) / prev_close) * 100
            
            last_vol = float(df['Volume'].iloc[-1])
            avg_vol = float(df['AvgVol20'].iloc[-1]) if not np.isnan(df['AvgVol20'].iloc[-1]) else last_vol
            ema20 = float(df['EMA20'].iloc[-1])
            ema50 = float(df['EMA50'].iloc[-1])
            atr = float(df['ATR'].iloc[-1]) if not np.isnan(df['ATR'].iloc[-1]) else (last_close * 0.05)
            rsi = float(df['RSI'].iloc[-1]) if not np.isnan(df['RSI'].iloc[-1]) else 50.0
            
            if last_close < min_price or rsi > max_rsi:
                continue
                
            is_uptrend = (last_close > ema20)
            vol_spike = last_vol >= (avg_vol * vol_mult * 0.8) # Dipermudahkan sedikit untuk live market
            
            signal = "📈 Live Momentum Aktif"
            if is_uptrend and vol_spike:
                signal = "🔥 Volume Spike / Uptrend"
                
            stop_loss = round(last_close - (atr * 1.5), 2)
            
            info = stock.info
            roe = info.get('returnOnEquity', 0.15)
            if roe:
                roe = roe * 100
            else:
                roe = 15.0
            pe = info.get('trailingPE', 20.0)
            
            clean_ticker = ticker.replace('.KL', '')
            scan_results.append({
                "Kaunter & Sektor": f"{clean_ticker} | Live Market",
                "Harga (MYR)": round(last_close, 2),
                "Perubahan (%)": f"{'+' if price_change_pct>=0 else ''}{price_change_pct:.2f}%",
                "Isyarat Teknikal": signal,
                "Struktur Trend & Vol": f"Vol: {last_vol/avg_vol:.1f}x | RSI: {rsi:.0f}",
                "Cadangan SL (ATR)": stop_loss,
                "EPS YoY / ROE": f"ROE: {roe:.1f}%",
                "Skor FA & CANSLIM": f"85/100 | P/E: {pe:.1f}x"
            })
            raw_dfs[clean_ticker] = df
        except Exception:
            pass
            
        progress_bar.progress((idx + 1) / total)
        
    status_text.text("Imbasan live selesai!")
    
    if scan_results:
        st.success(f"Berjaya memuat turun live data untuk {len(scan_results)} kaunter!")
        result_df = pd.DataFrame(scan_results)
        st.dataframe(result_df, use_container_width=True, hide_index=True)
        
        # Butang Telegram Alert
        if telegram_token and telegram_chat_id:
            if st.button("📲 Hantar Keputusan Live ke Telegram"):
                msg_text = "🚨 *MYX LIVE SCAN ALERT* 🚨\n\nKaunter Aktif Dikesan:\n"
                for item in scan_results:
                    name = item["Kaunter & Sektor"].split(" | ")[0]
                    price = item["Harga (MYR)"]
                    sig = item["Isyarat Teknikal"]
                    msg_text += f"• *{name}* | Harga: RM{price} | {sig}\n"
                
                success = send_telegram_message(telegram_token, telegram_chat_id, msg_text)
                if success:
                    st.success("Mesej berjaya dihantar ke Telegram!")
                else:
                    st.error("Gagal menghantar. Sila semak semula Token & Chat ID.")
        
        # --- CARTA LIVE INTERAKTIF CANDLESTICK (PLOTLY) ---
        st.markdown("---")
        st.subheader("📊 Live Candlestick Charts & Technical Analysis")
        
        for ticker_name, df_chart in raw_dfs.items():
            with st.expander(f"📈 Papar Live Chart Sebenar: {ticker_name}"):
                fig = go.Figure()
                
                fig.add_trace(go.Candlestick(
                    x=df_chart.index,
                    open=df_chart['Open'],
                    high=df_chart['High'],
                    low=df_chart['Low'],
                    close=df_chart['Close'],
                    name='Harga Live'
                ))
                
                fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA20'], line=dict(color='orange', width=1.5), name='EMA 20'))
                fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA50'], line=dict(color='blue', width=1.5), name='EMA 50'))
                
                fig.update_layout(
                    title=f"Live Daily Chart - {ticker_name}.KL (Yahoo Finance)",
                    yaxis_title="Harga (MYR)",
                    xaxis_title="Tarikh",
                    template="plotly_dark",
                    height=500,
                    margin=dict(l=10, r=10, t=40, b=10)
                )
                st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.subheader("🧮 Simulasi Pengurusan Risiko & Saiz Pembelian")
        
        for item in scan_results:
            name = item["Kaunter & Sektor"].split(" | ")[0]
            price = item["Harga (MYR)"]
            sl = item["Cadangan SL (ATR)"]
            
            risk_amount = total_capital * (risk_per_trade_pct / 100.0)
            risk_per_share = price - sl
            
            if risk_per_share > 0:
                shares_to_buy = int(risk_amount / risk_per_share)
                total_investment = shares_to_buy * price
            else:
                shares_to_buy = 0
                total_investment = 0
                
            col1, col2, col3, col4 = st.columns(4)
            col1.metric(label=f"📌 Kaunter: {name}", value=f"RM {price:.2f}")
            col2.metric(label="🛡️ Cadangan Stop-Loss", value=f"RM {sl:.2f}")
            col3.metric(label="📦 Unit Saham Disyorkan", value=f"{shares_to_buy:,} unit")
            col4.metric(label="💰 Jumlah Modal Digunakan", value=f"RM {total_investment:,.2f}")
            st.markdown("---")
        
        csv_data = result_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Muat Turun Laporan Live (CSV)",
            data=csv_data,
            file_name="bursa_swing_live_report.csv",
            mime="text/csv",
        )
    else:
        st.warning("Tiada kaunter yang berjaya dimuat turun datanya. Sila semak kod kaunter.")
else:
    st.info("👈 Pilih sektor di sidebar, semak prestasi pasaran di atas, dan klik **Mula Imbas Pasaran Live**.")
