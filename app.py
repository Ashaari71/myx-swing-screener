import streamlit as st
import pandas as pd
import numpy as np
import requests

st.set_page_config(page_title="MYX Swing Pro Screener", page_icon="📈", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    </style>
""", unsafe_allow_html=True)

st.title("📈 MYX Swing Pro: Screener & Order Execution Ticket")
st.markdown("Sistem Imbasan Automatik BOB/BOD, Analisis Teknikal AI & Panel Tiket Pesanan")

# --- MASTER SEKTOR & KAUNTER BURSA MALAYSIA ---
sector_benchmarks = {
    "🔥 Pembinaan & Infrastruktur (Construction)": ["GAMUD", "SUNCON", "IJM", "MRCB", "WCT", "KERJAYA"],
    "⚡ Tenaga Boleh Baharu & Utiliti (Energy/RE)": ["CITAGLB", "SAMAIDEN", "PEKAT", "TENAGA", "YTLPOWR", "SOLARVEST"],
    "💻 Teknologi & Semikonduktor (Tech)": ["FRONTKN", "INARI", "KGB", "MYEG", "UNISEM", "GTRONIC", "VITROX"],
    "🏥 Penjagaan Kesihatan (Healthcare)": ["KPJ", "IHH", "TOPGLOV", "HARTA"],
    "🌾 Perladangan & Komoditi (Plantation)": ["KLK", "IOICORP", "FGV", "SIMEPROP"],
    "⚙️ Perindustrian & Telco (Industrial/Telco)": ["CDB", "MAXIS", "SIME", "PMETAL", "ANCOMNY", "WASCO"]
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

# --- SIDEBAR TETAPAN ---
st.sidebar.header("⚙️ Kriteria Tapisan")
min_price = st.sidebar.number_input("Harga Minimum (RM)", value=0.50, step=0.05)
max_rsi = st.sidebar.slider("Had Maksimum RSI", 70, 95, 80, 1)
min_change_pct = st.sidebar.slider("Perubahan Harian Min (%)", -5.0, 5.0, -3.0, 0.5)

st.sidebar.markdown("---")
st.sidebar.subheader("🧮 Risiko & Modal")
total_capital = st.sidebar.number_input("Modal Dagangan (RM)", value=2000.0, step=500.0)
risk_per_trade_pct = st.sidebar.slider("Risiko Dibenarkan (%)", 0.5, 3.0, 1.0, 0.5)

st.sidebar.markdown("---")
telegram_token = st.sidebar.text_input("Telegram Bot Token", type="password")
telegram_chat_id = st.sidebar.text_input("Telegram Chat ID")

def send_telegram_message(token, chat_id, message):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        response = requests.post(url, json=payload)
        return response.status_code == 200
    except Exception:
        return False

# --- PANEL KAWALAN UTAMA & PILIHAN MOD ---
st.markdown("### 🔍 Panel Imbasan & Analisis Pasaran")
scan_mode = st.radio("Pilih Mod Imbasan:", ["🤖 Imbas Automatik Seluruh Pasaran", "📂 Imbas Mengikut Sektor / Manual Kaunter"], horizontal=True)

if scan_mode == "📂 Imbas Mengikut Sektor / Manual Kaunter":
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        sel_sector = st.selectbox("Pilih Sektor:", list(sector_benchmarks.keys()))
        default_t = ", ".join(sector_benchmarks[sel_sector])
    with col_m2:
        custom_input = st.text_area("Atau Edit Kod Kaunter (Koma):", value=default_t, height=75)
        target_tickers = [t.strip().upper().replace('.KL', '') for t in custom_input.split(",") if t.strip()]
else:
    target_tickers = master_bursa_tickers

run_scan = st.button("🚀 Mula Imbas Pasaran Sekarang", type="primary", use_container_width=True)
st.markdown("---")

if "scan_results" not in st.session_state:
    st.session_state.scan_results = []
if "scanned_data_dict" not in st.session_state:
    st.session_state.scanned_data_dict = {}
if "raw_tickers" not in st.session_state:
    st.session_state.raw_tickers = []

if run_scan:
    tv_results = fetch_tradingview_scanner(target_tickers)
    scan_results = []
    scanned_data_dict = {}
    raw_tickers = []
    
    for t in target_tickers:
        if t in tv_results:
            info = tv_results[t]
            price = info["close"]
            change = info["change"]
            rsi_val = info["rsi"]
            vol = info["volume"]
            
            if price >= min_price and rsi_val <= max_rsi and change >= min_change_pct:
                entry_price = round(price, 2)
                sl = round(entry_price * 0.93, 2)
                risk_per_share = entry_price - sl
                tp = round(entry_price + (risk_per_share * 2.0), 2)
                
                risk_amt = total_capital * (risk_per_trade_pct / 100.0)
                if risk_per_share > 0:
                    # Kiraan unit tepat mengikut risiko modal (tanpa paksa 100 unit)
                    shares = max(1, int(risk_amt / risk_per_share))
                else:
                    shares = 100
                    
                inv_total = shares * entry_price
                
                if change >= 2.0 and vol > 500000:
                    signal = "🔥 BOB (Breakout)"
                elif change >= -1.5 and change < 2.0 and vol > 300000:
                    signal = "🔄 BOD (Dip/Reversal)"
                elif
