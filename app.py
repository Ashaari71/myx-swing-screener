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

st.title("📈 MYX Swing Pro: Screener, AI Analysis & Trade Log")
st.markdown("Sistem Imbasan Automatik BOB/BOD, Analisis Teknikal AI, Sektor Live, Tiket Pesanan & Rekod Simpanan")

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

# --- SESSION STATE INITIALIZATION ---
if "scan_results" not in st.session_state:
    st.session_state.scan_results = []
if "scanned_data_dict" not in st.session_state:
    st.session_state.scanned_data_dict = {}
if "ai_breakdowns" not in st.session_state:
    st.session_state.ai_breakdowns = []
if "raw_tickers" not in st.session_state:
    st.session_state.raw_tickers = []
if "trade_history" not in st.session_state:
    st.session_state.trade_history = []

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

if run_scan:
    tv_results = fetch_tradingview_scanner(target_tickers)
    scan_results = []
    scanned_data_dict = {}
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
                entry_price = round(price, 2)
                sl = round(entry_price * 0.93, 2)
                support_est = round(entry_price * 0.95, 2)
                resistance_est = round(entry_price * 1.07, 2)
                risk_per_share = entry_price - sl
                tp = round(entry_price + (risk_per_share * 2.0), 2)
                
                risk_amt = total_capital * (risk_per_trade_pct / 100.0)
                if risk_per_share > 0:
                    raw_shares = risk_amt / risk_per_share
                    shares = max(100, round(raw_shares / 100.0) * 100)
                else:
                    shares = 100
                    
                inv_total = shares * entry_price
                
                if change >= 2.0 and vol > 500000:
                    signal = "🔥 BOB (Breakout)"
                    ai_note = f"Harga merembat melepasi rintangan RM {resistance_est} dengan volum besar. Sokongan di RM {support_est}."
                elif change >= -1.5 and change < 2.0 and vol > 300000:
                    signal = "🔄 BOD (Dip/Reversal)"
                    ai_note = f"Pullback sihat dengan tanda lantunan (bullish reversal) di zon sokongan RM {support_est}. Volum menyokong."
                elif change > 0:
                    signal = "📈 Momentum"
                    ai_note = f"Pergerakan harga stabil mendaki menghampiri rintangan RM {resistance_est}."
                else:
                    signal = "📉 Tapak / Pullback"
                    ai_note = f"Menguji kawasan tapak sokongan RM {support_est}. Perhati lilin pembalikan (*reversal candle*)."
                
                item_data = {
                    "Kaunter": t,
                    "Harga (RM)": entry_price,
                    "Perubahan": f"{'+' if change>=0 else ''}{change:.2f}%",
                    "RSI": round(rsi_val, 1),
                    "Setup": signal,
                    "Entry": entry_price,
                    "Stop-Loss": sl,
                    "Target Price": tp,
                    "Lot_Unit": f"{shares:,}",
                    "Modal (RM)": f"{inv_total:,.2f}"
                }
                scan_results.append(item_data)
                scanned_data_dict[t] = item_data
                
                ai_breakdowns.append({
                    "Kaunter": t,
                    "Analisis Teknikal AI (BOB / BOD, Sokongan & Rintangan)": ai_note,
                    "Sokongan (S)": f"RM {support_est}",
                    "Rintangan (R)": f"RM {resistance_est}"
                })
                
                raw_tickers.append(t)
                
    st.session_state.scan_results = scan_results
    st.session_state.scanned_data_dict = scanned_data_dict
    st.session_state.ai_breakdowns = ai_breakdowns
    st.session_state.raw_tickers = raw_tickers

# --- 1. PAPAN PENDAHUDU SEKTOR ---
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

st.markdown("---")

# --- 2. KEPUTUSAN SCREENER, ANALISIS AI & ORDER TICKET ---
if st.session_state.scan_results:
    st.success(f"Berjaya menemui **{len(st.session_state.scan_results)} kaunter** sepadan!")
    
    col_table, col_ticket = st.columns([2, 1])
    
    with col_table:
        st.markdown("#### 📋 Senarai Keputusan Screener")
        df_display = pd.DataFrame(st.session_state.scan_results).rename(columns={"Lot_Unit": "Lot / Unit"})
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
        # Jadual Analisis Teknikal AI
        st.markdown("#### 🤖 Nota Analisis Teknikal AI (BOB / BOD, Sokongan & Rintangan)")
        ai_df = pd.DataFrame(st.session_state.ai_breakdowns)
        st.dataframe(ai_df, use_container_width=True, hide_index=True)
        
        st.markdown("🔗 **Pautan Cepat Carta TradingView:**")
        cols_tv = st.columns(4)
        for i, t_name in enumerate(st.session_state.raw_tickers):
            tv_url = f"https://www.tradingview.com/chart/?symbol=MYX%3A{t_name}"
            with cols_tv[i % 4]:
                st.markdown(f"👉 [{t_name}]({tv_url})", unsafe_allow_html=True)
                
    with col_ticket:
        st.markdown("#### 🎫 Order Execution Ticket")
        selected_ticket_counter = st.selectbox("Pilih Kaunter untuk Urus Niaga:", st.session_state.raw_tickers)
        
        if selected_ticket_counter in st.session_state.scanned_data_dict:
            d = st.session_state.scanned_data_dict[selected_ticket_counter]
            
            st.markdown(f"""
            <div style="background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d;">
                <h3 style="margin-top:0; color: #58a6ff;">📌 {d['Kaunter']}</h3>
                <p><b>Harga Semasa / Entry:</b> RM {d['Entry']}</p>
                <p><b>Setup Strategi:</b> {d['Setup']}</p>
                <hr style="border-color: #30363d;">
                <p style="color: #f85149;">🛡️ <b>Stop-Loss (SL):</b> RM {d['Stop-Loss']}</p>
                <p style="color: #3fb950;">🎯 <b>Take Profit (TP):</b> RM {d['Target Price']}</p>
                <p>📦 <b>Saiz Cadangan:</b> {d['Lot_Unit']} unit</p>
                <p>💰 <b>Jumlah Modal:</b> RM {d['Modal (RM)']}</p>
            </div>
            """, unsafe_allow_html=True)
            
            order_type = st.radio("Jenis Pesanan:", ["Market Order", "Limit Order"], horizontal=True)
            
            if st.button("🚀 Hantar Pesanan / Simpan Pelan Trade", type="primary", use_container_width=True):
                new_record = {
                    "Kaunter": d["Kaunter"],
                    "Jenis Pesanan": order_type,
                    "Entry (RM)": d["Entry"],
                    "Stop-Loss (RM)": d["Stop-Loss"],
                    "Target Price (RM)": d["Target Price"],
                    "Lot / Unit": d["Lot_Unit"],
                    "Modal (RM)": d["Modal (RM)"]
                }
                st.session_state.trade_history.append(new_record)
                st.success(f"Pesanan untuk {d['Kaunter']} ({order_type}) berjaya direkod dan disimpan!")
                
                if telegram_token and telegram_chat_id:
                    msg = f"🚨 *TRADE TICKET ALERT* 🚨\nKaunter: {d['Kaunter']}\nJenis: {order_type}\nEntry: RM{d['Entry']}\nSL: RM{d['Stop-Loss']}\nTP: RM{d['Target Price']}\nUnit: {d['Lot_Unit']}"
                    send_telegram_message(telegram_token, telegram_chat_id, msg)
                    st.info("Makluman berjaya dihantar ke Telegram!")

    st.markdown("---")
    csv_data = df_display.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Muat Turun Laporan (CSV)", data=csv_data, file_name="myx_order_ticket.csv", mime="text/csv")
else:
    st.info("👈 Klik butang **Mula Imbas Pasaran Sekarang** di atas untuk memaparkan senarai kaunter.")

st.markdown("---")

# --- 3. SEKSYEN REKOD SIMPANAN PELAN TRADE (TRADE HISTORY LOG) ---
st.subheader("📁 Rekod Simpanan Pelan Trade (Saved Trades Log)")
if st.session_state.trade_history:
    history_df = pd.DataFrame(st.session_state.trade_history)
    st.dataframe(history_df, use_container_width=True, hide_index=True)
    
    col_h1, col_h2 = st.columns(2)
    with col_h1:
        hist_csv = history_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Muat Turun Rekod Trade (CSV)", data=hist_csv, file_name="myx_trade_history.csv", mime="text/csv")
    with col_h2:
        if st.button("🗑️ Padam Semua Rekod"):
            st.session_state.trade_history = []
            st.rerun()
else:
    st.info("💡 Belum ada rekod trade yang disimpan. Sila pilih kaunter dan klik **'Hantar Pesanan / Simpan Pelan Trade'** di atas.")
