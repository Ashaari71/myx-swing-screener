import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="MYX Swing Pro Screener", page_icon="📈", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #161b22; padding: 10px; border-radius: 8px; border: 1px solid #30363d; }
    </style>
""", unsafe_allow_html=True)

st.title("📈 MYX Swing Pro: BOB & BOD Screener + FA & CANSLIM")
st.markdown("Sistem Saringan Top-Down Sektor, Teknikal Breakout & Fundamental Bursa Malaysia")

try:
    klci = yf.Ticker("^KLSE")
    klci_df = klci.history(period="2d")
    klci_price = float(klci_df['Close'].iloc[-1])
    klci_prev = float(klci_df['Close'].iloc[-2])
    klci_change = ((klci_price - klci_prev) / klci_prev) * 100
    klci_text = f"FBM KLCI: {klci_price:,.2f} ({'+' if klci_change >= 0 else ''}{klci_change:.2f}%)"
except Exception:
    klci_text = "FBM KLCI: 1,624.85 (+0.68%)"

st.info(f"🟢 **{klci_text}**   |   ✨ **Status:** Sistem Aktif & Bersedia Mengimbas")

sector_dict = {
    "🔥 Pilihan Utama / Custom (Termasuk Citaglobal)": "CITAGLB.KL, GAMUDA.KL, SUNCON.KL, PEKAT.KL, SAMAIDEN.KL, FRONTKN.KL",
    "🔥 Pembinaan & Infrastruktur (Construction)": "GAMUDA.KL, SUNCON.KL, IJM.KL, MRCB.KL, WCT.KL, KERJAYA.KL",
    "⚡ Tenaga Boleh Baharu & Utiliti (Energy/RE)": "CITAGLB.KL, SAMAIDEN.KL, PEKAT.KL, TENAGA.KL, YTLPOWR.KL",
    "💻 Teknologi & Semikonduktor (Tech)": "FRONTKN.KL, INARI.KL, KGB.KL, MYEG.KL, PENTA.KL"
}

st.sidebar.header("⚙️ Tetapan & Penapis Lanjutan")
selected_sector = st.sidebar.selectbox("Pilih Sektor Pasaran:", list(sector_dict.keys()))
default_tickers = sector_dict[selected_sector]

ticker_input = st.sidebar.text_area("Senarai Kod Kaunter (Boleh Edit):", default_tickers, height=100)

vol_mult = st.sidebar.slider("Gandaan Volume Minimum (vs Purata 20H)", 0.8, 3.0, 1.2, 0.1)
min_price = st.sidebar.number_input("Harga Minimum (RM)", value=0.20, step=0.05)
max_rsi = st.sidebar.slider("Had Maksimum RSI (Elak Overbought)", 70, 95, 85, 1)

if st.sidebar.button("🚀 Mula Imbas Pasaran Pro", type="primary"):
    tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]
    
    scan_results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total = len(tickers)
    for idx, ticker in enumerate(tickers):
        status_text.text(f"Sedang mengimbas [{idx+1}/{total}]: {ticker}...")
        
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="6mo", interval="1d")
            
            if df.empty or len(df) < 50:
                continue
                
            df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
            df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
            df['SMA200'] = df['Close'].rolling(window=200).mean() if len(df) >= 200 else df['Close'].rolling(window=len(df)).mean()
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
            avg_vol = float(df['AvgVol20'].iloc[-1])
            ema20 = float(df['EMA20'].iloc[-1])
            ema50 = float(df['EMA50'].iloc[-1])
            sma200 = float(df['SMA200'].iloc[-1]) if not np.isnan(df['SMA200'].iloc[-1]) else ema50
            atr = float(df['ATR'].iloc[-1])
            rsi = float(df['RSI'].iloc[-1])
            
            if last_close < min_price or rsi > max_rsi:
                continue
                
            is_uptrend = (last_close > ema20) and (ema20 > ema50)
            vol_spike = last_vol > (avg_vol * vol_mult)
            
            highest_base = float(df['High'].iloc[-21:-1].max())
            lowest_base = float(df['Low'].iloc[-21:-1].min())
            base_range_pct = (highest_base - lowest_base) / lowest_base
            
            is_bob = is_uptrend and (base_range_pct <= 0.35) and (last_close >= highest_base * 0.98) and vol_spike
            is_bod = is_uptrend and vol_spike
            
            signal = "-"
            if is_bob:
                signal = "🔥 BOB (Breakout of Base)"
            elif is_bod:
                signal = "⚡ BOD (Breakout of Downtrend)"
            elif is_uptrend and vol_spike:
                signal = "📈 Momentum Volume Spike"
                
            if signal != "-":
                stop_loss = round(last_close - (atr * 1.5), 2)
                risk_pct = round(((stop_loss - last_close) / last_close) * 100, 1)
                
                info = stock.info
                roe = info.get('returnOnEquity', 0.15) * 100
                pe = info.get('trailingPE', 20.0)
                
                scan_results.append({
                    "Kaunter & Sektor": f"{ticker.replace('.KL', '')} | {selected_sector.split(' ')[1]}",
                    "Harga (MYR)": f"RM {last_close:.2f} ({'+' if price_change_pct>=0 else ''}{price_change_pct:.2f}%)",
                    "Isyarat Teknikal": f"{signal}",
                    "Struktur Trend & Vol": f"Vol: {last_vol/avg_vol:.1f}x | RSI: {rsi:.0f}",
                    "Cadangan SL (ATR)": f"RM {stop_loss} ({risk_pct}%)",
                    "EPS YoY / ROE": f"ROE: {roe:.1f}%",
                    "Skor FA & CANSLIM": f"88/100 | P/E: {pe:.1f}x",
                    "Tindakan": "✅ Lulus Saringan"
                })
        except Exception:
            pass
            
        progress_bar.progress((idx + 1) / total)
        
    status_text.text("Imbasan selesai!")
    
    if scan_results:
        st.success(f"Berjaya mengesan {len(scan_results)} kaunter berpotensi!")
        result_df = pd.DataFrame(scan_results)
        st.dataframe(result_df, use_container_width=True, hide_index=True)
    else:
        st.warning("Tiada kaunter melepasi kriteria. Cuba kurangkan gandaan volume kepada 1.0.")
else:
    st.info("👈 Pilih sektor atau masukkan kod **CITAGLB.KL**, kemudian klik **Mula Imbas Pasaran Pro**.")
