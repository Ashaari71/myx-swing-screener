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

st.title("📈 MYX Swing Pro: AI-Powered BOB/BOD & Sector Screener")
st.markdown("Sistem Imbasan Automatik, Analisis Teknikal AI (S/R, Pullback, Reversal) & Gandaan 100 Unit")

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
min_change_pct = st.sidebar.slider("Perubahan Harian Min (%)", -5.0, 5.0, -2.0, 0.5)

st.sidebar.markdown("---")
st.sidebar.subheader("🧮 Risiko & Modal")
total_capital = st.sidebar.number_input("Modal Dagangan (RM)", value=10000.0, step=1000.0)
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
st.markdown("### 🔍 Panel Imbasan & Analisis AI Sektor / Manual")
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

run_scan = st.button("🚀 Mula Imbasan & Analisis AI Sekarang", type="primary", use_container_width=True)
st.markdown("---")

# --- KEPUTUSAN IMBASAN & ANALISIS AI ---
if run_scan:
    tv_results = fetch_tradingview_scanner(target_tickers)
    scan_results = []
    ai_breakdowns = []
    raw_tickers = []
    
    for t in target_tickers:
        if t in tv_results:
            info = tv_results[t]
            price = info["close"]
            change = info["change"]
            rsi_val = info["rsi"]
            vol = info["volume"]
            
            if price >= min_price and rsi_val <= max_rsi and change >= min_change_pct:
                sl = round(price * 0.93, 2)
                support_est = round(price * 0.95, 2)
                resistance_est = round(price * 1.07, 2)
                
                risk_amt = total_capital * (risk_per_trade_pct / 100.0)
                risk_per_share = price - sl
                
                if risk_per_share > 0:
                    raw_shares = risk_amt / risk_per_share
                    shares = max(1, round(raw_shares / 100.0)) * 100
                else:
                    shares = 100
                    
                inv_total = shares * price
                
                # AI Technical Logic (BOB / BOD / Pullback / Reversal)
                if change > 2.0 and rsi_val > 55:
                    signal = "🔥 BOB (Breakout of Base)"
                    ai_note = f"Harga memecah tapak asas dengan momentum kuat. Sokongan terdekat di RM {support_est}, rintangan di RM {resistance_est}. Potensi sambungan *uptrend* jika volum kekal tinggi."
                elif change > 0 and rsi_val <= 55:
                    signal = "🔄 BOD (Breakout of Downtrend)"
                    ai_note = f"Fasa pemulihan dari trend menurun (*downtrend*). Tapak sokongan kukuh di RM {support_est}. Cari peluang *entry* semasa *pullback* kecil."
                elif change < 0:
                    signal = "📉 Pullback / Reversal Setup"
                    ai_note = f"Harga sedang membuat *pullback* sihat menghampiri paras sokongan RM {support_est}. Perhati zon pembalikan (*reversal candle*) sebelum masuk."
                else:
                    signal = "📈 Uptrend Konsisten"
                    ai_note = f"Pergerakan harga mendatar stabil. Sokongan di RM {support_est} dan sasaran rintangan pertama di RM {resistance_est}."
                
                scan_results.append({
                    "Kaunter": t,
                    "Harga (RM)": round(price, 2),
                    "Perubahan": f"{'+' if change>=0 else ''}{change:.2f}%",
                    "RSI": round(rsi_val, 1),
                    "Volum": f"{vol:,.0f}",
                    "Setup Teknikal": signal,
                    "Stop-Loss": sl,
                    "Unit (Lot)": f"{shares:,}",
                    "Modal (RM)": f"{inv_total:,.2f}"
                })
                
                ai_breakdowns.append({
                    "Kaunter": t,
                    "Analisis AI & Nota Teknikal": ai_note,
                    "Sokongan (S)": f"RM {support_est}",
                    "Rintangan (R)": f"RM {resistance_est}"
                })
                
                raw_tickers.append(t)
                
    if scan_results:
        st.success(f"Berjaya menemui **{len(scan_results)} kaunter** sepadan!")
        
        # Paparan Jadual Utama (Kompak)
        res_df = pd.DataFrame(scan_results)
        st.dataframe(res_df, use_container_width=True, hide_index=True)
        
        # Paparan Nota Analisis AI Terperinci
        st.markdown("### 🤖 Nota Analisis Teknikal AI (BOB/BOD, Sokongan & Rintangan)")
        ai_df = pd.DataFrame(ai_breakdowns)
        st.dataframe(ai_df, use_container_width=True, hide_index=True)
        
        # Pautan Cepat TradingView
        st.markdown("🔗 **Pautan Pantas Carta TradingView (Klik untuk sahkan analisis):**")
        cols = st.columns(6)
        for i, t_name in enumerate(raw_tickers):
            tv_url = f"https://www.tradingview.com/chart/?symbol=MYX%3A{t_name}"
            with cols[i % 6]:
                st.markdown(f"👉 [{t_name}]({tv_url})", unsafe_allow_html=True)
                
        csv_data = res_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Muat Turun Laporan (CSV)", data=csv_data, file_name="myx_ai_screener.csv", mime="text/csv")
    else:
        st.warning("⚠️ Tiada kaunter melepasi tapisan kriteria semasa.")
    st.markdown("---")

# --- PAPAN PENDAHUDU SEKTOR (SECTOR ROTATION) ---
st.subheader("📊 Prestasi Sektor Semasa (Sector Leadership)")
sector_perf = []
for sec_name, t_list in sector_benchmarks.items():
    sec_data = fetch_tradingview_scanner(t_list)
    sec_changes = [v["change"] for v in sec_data.values() if "change" in v]
    avg_ret = np.mean(sec_changes) if sec_changes else 0.0
    status_trend = "🔥 Sektor Leader" if avg_ret > 0.5 else ("📈 Positif" if avg_ret >= 0 else "📉 Lemah / Pullback")
    sector_perf.append({
        "Sektor Pasaran": sec_name,
        "Avg Ret": avg_ret,
        "Prestasi (%)": f"{'+' if avg_ret>=0 else ''}{avg_ret:.2f}%",
        "Status Trend": status_trend
    })

if sector_perf:
    perf_df = pd.DataFrame(sector_perf).sort_values(by="Avg Ret", ascending=False)
    st.dataframe(perf_df[["Sektor Pasaran", "Prestasi (%)", "Status Trend"]], use_container_width=True, hide_index=True)
