import streamlit as st
import pandas as pd
import numpy as np
import requests
import base64
import io
from PIL import Image
from openai import OpenAI

st.set_page_config(page_title="MYX Swing Pro Screener", page_icon="📈", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    </style>
""", unsafe_allow_html=True)

st.title("📈 MYX Swing Pro: Screener, AI Vision (OpenAI) & Pautan Rasmi")
st.markdown("Sistem Imbasan Automatik BOB/BOD, AI Chart Inspector (OpenAI GPT-4 Vision) & Rujukan Pantas")

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
st.sidebar.header("🤖 OpenAI API Tetapan")
openai_api_key = st.sidebar.text_input("OpenAI API Key", type="password", placeholder="sk-...")

st.sidebar.markdown("---")
st.sidebar.header("🔔 Telegram Bot Alert")
telegram_token = st.sidebar.text_input("Telegram Bot Token", type="password")
telegram_chat_id = st.sidebar.text_input("Telegram Chat ID")

# --- KALKULATOR SAIZ POSISI & RISIKO ---
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
    raw_shares = max_risk_rm / risk_per_share
    suggested_shares = max(100, int(raw_shares // 100) * 100)
    total_investment = suggested_shares * calc_entry
    actual_risk_rm = suggested_shares * risk_per_share
    potential_profit = suggested_shares * (calc_tp - calc_entry) if calc_tp > calc_entry else 0
    risk_reward_ratio = (calc_tp - calc_entry) / risk_per_share if risk_per_share > 0 else 0
    
    st.sidebar.markdown(f"""
    <div style="background-color: #161b22; padding: 12px; border-radius: 8px; border: 1px solid #30363d; font-size: 13px;">
        <p style="color: #58a6ff; margin:0 0 5px 0; font-weight:bold;">📊 Keputusan Pengiraan (Lot Bursa):</p>
        <p style="margin:2px 0;">📦 <b>Jumlah Unit Saham:</b> {suggested_shares:,} unit ({suggested_shares//100} Lot)</p>
        <p style="margin:2px 0;">💰 <b>Jumlah Modal Diguna:</b> RM {total_investment:,.2f}</p>
        <p style="color: #f85149; margin:2px 0;">⚠️ <b>Risiko Sebenar:</b> RM {actual_risk_rm:,.2f}</p>
        <p style="color: #3fb950; margin:2px 0;">🎯 <b>Potensi Untung (TP):</b> RM {potential_profit:,.2f}</p>
        <p style="color: #e3b341; margin:2px 0;">⚖️ <b>N
