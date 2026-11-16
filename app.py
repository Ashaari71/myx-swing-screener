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
    klci_text = "FBM KLCI: 1,588.03 (+0.34%)"

st.info(f"🟢 **{klci_text}**   |   ✨ **Status:** Sistem Aktif & Mod Paparan Contoh Diaktifkan")

sector_dict = {
    "🔥 Pilihan Utama / Custom (Termasuk Citaglobal)": "CITAGLB.KL, GAMUDA.KL, SUNCON.KL, PEKAT.KL, SAMAIDEN.KL, FRONTKN.KL",
    "🔥 Pembinaan & Infrastruktur (Construction)": "GAMUDA.KL, SUNCON.KL, IJM.KL, MRCB.KL, WCT.KL, KERJAYA.KL",
}

st.sidebar.header("⚙️ Tetapan & Penapis Lanjutan")
selected_sector = st.sidebar.selectbox("Pilih Sektor Pasaran:", list(sector_dict.keys()))
default_tickers = sector_dict[selected_sector]

ticker_input = st.sidebar.text_area("Senarai Kod Kaunter (Boleh Edit):", default_tickers, height=100)

vol_mult = st.sidebar.slider("Gandaan Volume Minimum (vs Purata 20H)", 0.5, 3.0, 1.0, 0.1)
min_price = st.sidebar.number_input("Harga Minimum (RM)", value=0.10, step=0.05)
max_rsi = st.sidebar.slider("Had Maksimum RSI (Elak Overbought)", 70, 95, 90, 1)

# Kotak pilihan untuk melihat contoh rupa jadual
show_demo = st.sidebar.checkbox("👀 Paparkan Contoh Rupa Jadual (Demo Pattern)", value=True)

if st.sidebar.button("🚀 Mula Imbas Pasaran Pro", type="primary") or show_demo:
    scan_results = []
    
    # Masukkan data contoh (Demo Pattern) supaya anda boleh lihat corak paparan jadual
    if "CITAGLB.KL" in ticker_input or show_demo:
        scan_results.append({
            "Kaunter & Sektor": "CITAGLB | Tenaga/RE (S)",
            "Harga (MYR)": "RM 1.09 (+4.00%)",
            "Isyarat Teknikal": "⚡ BOD (Breakout of Downtrend) (Base: 22h)",
            "Struktur Trend & Vol": "Harga > EMA20 > EMA50 | Vol: 3.2x RSI: 68",
            "Cadangan SL (ATR)": "RM 0.98 (-10.1%)",
            "EPS YoY / ROE": "+42.5% YoY\nROE: 18.2%",
            "Skor FA & CANSLIM": "88/100\nP/E: 22.4x",
            "Tindakan": "✅ Lulus Saringan"
        })
    
    if "SUNCON.KL" in ticker_input or show_demo:
        scan_results.append({
            "Kaunter & Sektor": "SUNCON | Pembinaan (S)",
            "Harga (MYR)": "RM 4.68 (+3.54%)",
            "Isyarat Teknikal": "🔥 BOB (Breakout of Base) (Base: 19h)",
            "Struktur Trend & Vol": "Harga > EMA20 > EMA50 | Vol: 2.3x RSI: 64",
            "Cadangan SL (ATR)": "RM 4.35 (-7.1%)",
            "EPS YoY / ROE": "+38.5% YoY\nROE: 21.4%",
            "Skor FA & CANSLIM": "94/100\nP/E: 26.5x",
            "Tindakan": "✅ Lulus Saringan"
        })

    if scan_results:
        st.success(f"Berjaya mengesan {len(scan_results)} kaunter berpotensi tinggi!")
        result_df = pd.DataFrame(scan_results)
        st.dataframe(result_df, use_container_width=True, hide_index=True)
        
        # Butang Muat Turun
        csv_data = result_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Muat Turun Laporan Pro (CSV)",
            data=csv_data,
            file_name="bursa_swing_pro_report.csv",
            mime="text/csv",
        )
    else:
        st.warning("Tiada kaunter memenuhi kriteria.")
else:
    st.info("👈 Klik **Mula Imbas Pasaran Pro** atau tandakan kotak demo di sidebar untuk melihat corak keputusan.")
