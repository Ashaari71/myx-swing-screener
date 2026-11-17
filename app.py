import streamlit as st
import pandas as pd
import numpy as np
import requests
from PIL import Image

st.set_page_config(page_title="MYX Swing Pro Screener", page_icon="📈", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    </style>
""", unsafe_allow_html=True)

st.title("📈 MYX Swing Pro: Screener, AI Chart Vision & Pautan Rasmi")
st.markdown("Sistem Imbasan Automatik BOB/BOD, AI Chart Inspector & Rujukan Pantas Bursa / KLSE")

# --- MASTER SEKTOR & KAUNTER UTAMA BURSA MALAYSIA ---
sector_benchmarks = {
    "🔥 Pembinaan & Infrastruktur (Construction)": ["GAMUD", "SUNCON", "IJM", "MRCB", "WCT", "KERJAYA"],
    "⚡ Tenaga Boleh Baharu & Utiliti (Energy/RE)": ["CITAGLB", "SAMAIDEN", "PEKAT", "TENAGA", "YTLPOWR", "SOLARVEST"],
    "💻 Teknologi & Semikonduktor (Tech)": ["FRONTKN", "INARI", "KGB", "MYEG", "UNISEM", "GTRONIC", "VITROX"],
    "🏥 Penjagaan Kesihatan (Healthcare)": ["KPJ", "IHH", "TOPGLOV", "HARTA"],
    "🌾 Perladangan & Komoditi (Plantation)": ["KLK", "IOICORP", "FGV", "SIMEPROP"],
    "⚙️ Perindustrian & Telco (Industrial/Telco)": ["CDB", "MAXIS", "SIME", "PMETAL", "ANCOMNY", "WASCO"],
    "🏦 Perbankan & Kewangan (Banking/Finance)": ["MAYBANK", "CIMB", "PBBANK", "HLBANK", "RHBBANK", "AMBANK"]
}

master_bursa_tickers = []
for t_list in sector_benchmarks.values():
    master_bursa_tickers.extend(t_list)
master_bursa_tickers = list(set(master_bursa_tickers))

# --- FUNGSI AMBIL LIVE DATA DARI TRADINGVIEW SCANNER API ---
def fetch_tradingview_scanner(tickers):
    formatted_symbols = [f"MYX:{t.strip().replace('.KL', '')}" for t in tickers]
    url = "https://scanner.tradingview.com/malaysia/scan"
    payload = {
        "symbols": {"tickers": formatted_symbols},
        "columns": ["close", "change", "volume", "RSI"]
    }
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=8)
        if response.status_code == 200:
            data = response.json()
            results = {}
            for item in data.get("data", []):
                sym = item["s"].replace("MYX:", "")
                vals = item["d"]
                results[sym] = {
                    "close": vals[0] if vals[0] is not None else 0.0,
                    "change": vals[1] if vals[1] is not None else 0.0,
                    "volume": vals[2] if vals[2] is not None else 0,
                    "rsi": vals[3] if len(vals) > 3 and vals[3] is not None else 50.0
                }
            return results
    except Exception:
        pass
    return {}

# --- SIDEBAR TETAPAN & KALKULATOR POSISI ---
st.sidebar.header("⚙️ Kriteria Tapisan")
min_price = st.sidebar.number_input("Harga Minimum (RM)", value=0.50, step=0.05)
max_rsi = st.sidebar.slider("Had Maksimum RSI", 70, 95, 80, 1)
min_change_pct = st.sidebar.slider("Perubahan Harian Min (%)", -5.0, 5.0, -3.0, 0.5)

st.sidebar.markdown("---")
st.sidebar.header("🔔 Telegram Bot Alert")
telegram_token = st.sidebar.text_input("Telegram Bot Token", type="password")
telegram_chat_id = st.sidebar.text_input("Telegram Chat ID")

# --- KALKULATOR SAIZ POSISI & RISIKO DI SIDEBAR ---
st.sidebar.markdown("---")
st.sidebar.header("🧮 Kalkulator Saiz Posisi & Risiko")
calc_capital = st.sidebar.number_input("Jumlah Modal (RM):", value=10000.0, step=500.0)
calc_risk_pct = st.sidebar.slider("Risiko Maksimum (% dari Modal):", 1.0, 5.0, 2.0, 0.5)
calc_entry = st.sidebar.number_input("Harga Beli (Entry) (RM):", value=1.00, step=0.01)
calc_sl = st.sidebar.number_input("Harga Stop-Loss (SL) (RM):", value=0.92, step=0.01)
calc_tp = st.sidebar.number_input("Harga Target (TP) (RM):", value=1.20, step=0.01)

if calc_entry > 0 and calc_sl > 0 and calc_entry > calc_sl:
    max_risk_rm = calc_capital * (calc_risk_pct / 100.0)
    risk_per_share = calc_entry - calc_sl
    suggested_shares = int(max_risk_rm / risk_per_share)
    total_investment = suggested_shares * calc_entry
    potential_profit = suggested_shares * (calc_tp - calc_entry) if calc_tp > calc_entry else 0
    risk_reward_ratio = (calc_tp - calc_entry) / (calc_entry - calc_sl) if (calc_entry - calc_sl) > 0 else 0
    
    st.sidebar.markdown(f"""
    <div style="background-color: #161b22; padding: 12px; border-radius: 8px; border: 1px solid #30363d; font-size: 13px;">
        <p style="color: #58a6ff; margin:0 0 5px 0; font-weight:bold;">📊 Keputusan Pengiraan:</p>
        <p style="margin:2px 0;">📦 <b>Jumlah Unit Saham:</b> {suggested_shares:,} unit</p>
        <p style="margin:2px 0;">💰 <b>Jumlah Modal Diguna:</b> RM {total_investment:,.2f}</p>
        <p style="color: #f85149; margin:2px 0;">⚠️ <b>Risiko Kerugian:</b> RM {max_risk_rm:,.2f} ({calc_risk_pct}%)</p>
        <p style="color: #3fb950; margin:2px 0;">🎯 <b>Potensi Untung (TP):</b> RM {potential_profit:,.2f}</p>
        <p style="color: #e3b341; margin:2px 0;">⚖️ <b>Nisbah R:R:</b> 1 : {risk_reward_ratio:.2f}</p>
    </div>
    """, unsafe_allow_html=True)
else:
    st.sidebar.warning("Sila pastikan Harga Entry lebih tinggi daripada Harga Stop-Loss.")

def send_telegram_message(token, chat_id, message):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        response = requests.post(url, json=payload)
        return response.status_code == 200
    except Exception:
        return False

# --- SESSION STATE INITIALIZATION ---
if "scan_results" not in st.session_state:
    st.session_state.scan_results = []
if "raw_tickers" not in st.session_state:
    st.session_state.raw_tickers = []

# --- NAVIGASI MOD UTAMA ---
app_mode = st.radio(
    "Pilih Mod Utama Sistem:", 
    [
        "🔍 Screener & Prestasi Sektor", 
        "📸 AI Chart Image Scanner & Analisis Terperinci", 
        "🔗 Pautan Pantas Data Rasmi (Bursa & KLSE)"
    ], 
    horizontal=True
)
st.markdown("---")

if app_mode == "🔗 Pautan Pantas Data Rasmi (Bursa & KLSE)":
    st.subheader("🔗 Rujukan Pantas Data Rasmi Pasaran")
    st.markdown("Klik pautan di bawah untuk terus merujuk data sahih di platform rasmi Bursa Malaysia dan KLSE Screener.")
    
    st.markdown("""
    <div style="background-color: #161b22; padding: 25px; border-radius: 10px; border: 1px solid #30363d;">
        <h3 style="color: #58a6ff; margin-top:0;">📌 Pautan Rasmi Pasaran Saham</h3>
        <p>Pilih platform rujukan di bawah:</p>
        <ul>
            <li>👉 <a href="https://www.bursamalaysia.com/" target="_blank"><b>Bursa Malaysia Official Portal</b></a></li>
            <li>👉 <a href="https://www.klsescreener.com/" target="_blank"><b>KLSE Screener Portal</b></a></li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

elif app_mode == "📸 AI Chart Image Scanner & Analisis Terperinci":
    st.subheader("📸 Modul Analisis Visual Imej Carta (AI Chart Inspector)")
    st.markdown("Muat naik *screenshot* carta TradingView anda untuk paparan rujukan harga Sokongan, Rintangan, Target Price serta Cadangan & Pandangan AI.")
    
    uploaded_chart = st.file_uploader("Pilih fail imej carta (PNG, JPG, JPEG):", type=["png", "jpg", "jpeg"])
    
    if uploaded_chart is not None:
        col_img1, col_img2 = st.columns([1, 1])
        with col_img1:
            image = Image.open(uploaded_chart)
            st.image(image, caption="Carta Dimuat Naik", use_column_width=True)
            
        with col_img2:
            st.markdown("### 🤖 Laporan Analisis & Pandangan
