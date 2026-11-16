import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="MYX Swing Pro Screener", page_icon="📈", layout="wide")

st.title("📈 MYX Swing Pro: BOB & BOD Screener & Sector Rotation (Bursa Malaysia)")
st.markdown("Sistem imbasan automatik mengikut sektor berpotensi, mengesan kaunter *Breakout of Base (BOB)* & *Breakout of Downtrend (BOD)* lengkap ATR Stop-Loss.")

# --- KAMUS SEKTOR BERPOTENSI DI BURSA MALAYSIA ---
sector_dict = {
    "🔥 Pembinaan & Infrastruktur (Construction)": "GAMUDA.KL, SUNCON.KL, IJM.KL, MRCB.KL, WCT.KL, KERJAYA.KL, EBP.KL",
    "⚡ Tenaga Boleh Baharu & Utiliti (Energy/RE)": "SAMAIDEN.KL, PEKAT.KL, TENAGA.KL, YTLPOWR.KL, MEGAFB.KL, CYPARK.KL",
    "💻 Teknologi & Semikonduktor (Tech)": "FRONTKN.KL, INARI.KL, KGB.KL, MYEG.KL, PENTA.KL, MPI.KL, UNISEM.KL",
    "🏥 Penjagaan Kesihatan (Healthcare)": "KPJ.KL, IHH.KL, TOPGLOV.KL, HARTALEGA.KL, SUPERMAX.KL",
    "⚙️ Perindustrian & Komunikasi (Industrial/Telco)": "TMK.KL, CDB.KL, MAXIS.KL, SIME.KL, PMETAL.KL, HAPSENG.KL",
    "✨ Custom / Masukkan Sendiri": "TMK.KL, PEKAT.KL, KPJ.KL, SUNCON.KL, SAMAIDEN.KL, FRONTKN.KL"
}

# --- SIDEBAR: PILIHAN SEKTOR & TETAPAN ---
st.sidebar.header("⚙️ Tetapan & Sektor Pasaran")

selected_sector = st.sidebar.selectbox("Pilih Sektor Berpotensi:", list(sector_dict.keys()))

# Automatik isi senarai kaunter berdasarkan pilihan sektor
default_tickers_for_sector = sector_dict[selected_sector]
ticker_input = st.sidebar.text_area("Senarai Kod Kaunter (Boleh ubah jika perlu):", default_tickers_for_sector)

vol_mult = st.sidebar.slider("Gandaan Volume Minimum (vs Purata 20H)", 1.0, 3.0, 1.5, 0.1)
min_price = st.sidebar.number_input("Harga Minimum (RM)", value=0.20, step=0.05)

if st.sidebar.button("🚀 Mula Imbas Sektor Terpilih", type="primary"):
    tickers = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]
    
    scan_results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total = len(tickers)
    for idx, ticker in enumerate(tickers):
        status_text.text(f"Sedang mengimbas [{idx+1}/{total}]: {ticker}...")
        
        try:
            df = yf.download(ticker, period="6mo", interval="1d", progress=False)
            
            if df.empty or len(df) < 50:
                continue
                
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            df['EMA20'] = df['Close'].ewm(span=20, adjust=False).mean()
            df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
            df['SMA200'] = df['Close'].rolling(window=200).mean() if len(df) >= 200 else df['Close'].rolling(window=len(df)).mean()
            df['AvgVol20'] = df['Volume'].rolling(window=20).mean()
            
            high_low = df['High'] - df['Low']
            high_close = np.abs(df['High'] - df['Close'].shift())
            low_close = np.abs(df['Low'] - df['Close'].shift())
            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            df['ATR'] = true_range.rolling(window=14).mean()
            
            last_close = float(df['Close'].iloc[-1])
            last_vol = float(df['Volume'].iloc[-1])
            avg_vol = float(df['AvgVol20'].iloc[-1])
            ema20 = float(df['EMA20'].iloc[-1])
            ema50 = float(df['EMA50'].iloc[-1])
            sma200 = float(df['SMA200'].iloc[-1]) if not np.isnan(df['SMA200'].iloc[-1]) else ema50
            atr = float(df['ATR'].iloc[-1])
            
            if last_close < min_price:
                continue
                
            is_uptrend = (last_close > ema20) and (ema20 > ema50) and (last_close > sma200)
            vol_spike = last_vol > (avg_vol * vol_mult)
            
            highest_base = float(df['High'].iloc[-21:-1].max())
            lowest_base = float(df['Low'].iloc[-21:-1].min())
            base_range_pct = (highest_base - lowest_base) / lowest_base
            
            is_bob = is_uptrend and (base_range_pct <= 0.20) and (last_close >= highest_base) and vol_spike
            recent_high = float(df['High'].iloc[-10:-3].max())
            is_bod = is_uptrend and (last_close > recent_high) and vol_spike and not is_bob
            
            signal = "-"
            if is_bob:
                signal = "🔥 BOB (Breakout of Base)"
            elif is_bod:
                signal = "⚡ BOD (Breakout of Downtrend)"
            elif is_uptrend and vol_spike:
                signal = "✨ Volume Spike (Potensi)"
                
            if signal != "-":
                stop_loss = round(last_close - (atr * 1.5), 2)
                tp1 = round(last_close + ((last_close - stop_loss) * 1.5), 2)
                
                scan_results.append({
                    "Kaunter": ticker.replace(".KL", ""),
                    "Harga (RM)": round(last_close, 2),
                    "Status Isyarat": signal,
                    "Volume Terkini": int(last_vol),
                    "Cadangan Stop-Loss (RM)": stop_loss,
                    "Sasaran Untung (TP1)": tp1
                })
        except Exception:
            pass
            
        progress_bar.progress((idx + 1) / total)
        
    status_text.text("Imbasan selesai!")
    
    if scan_results:
        st.success(f"Berjaya mengesan {len(scan_results)} kaunter yang memenuhi kriteria dalam sektor ini!")
        result_df = pd.DataFrame(scan_results)
        st.dataframe(result_df, use_container_width=True)
        
        # Butang Muat Turun Fail CSV
        csv_data = result_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Muat Turun Laporan Sektor (CSV)",
            data=csv_data,
            file_name=f"bursa_{selected_sector[:10].strip()}_signals.csv",
            mime="text/csv",
        )
    else:
        st.warning("Tiada kaunter yang memenuhi kriteria ketat BOB/BOD dalam sektor ini buat masa ini.")
else:
    st.info("👈 Pilih sektor berpotensi di bahagian kiri (Sidebar) dan klik butang **Mula Imbas Sektor Terpilih**.")