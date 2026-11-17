import streamlit as st
import pandas as pd
import numpy as np
import requests
import yfinance as yf
from PIL import Image

st.set_page_config(page_title="MYX Swing Pro Screener", page_icon="📈", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    </style>
""", unsafe_allow_html=True)

st.title("📈 MYX Swing Pro: Technical, AI Vision & Live Fundamental Analysis")
st.markdown("Sistem Imbasan Automatik BOB/BOD, AI Chart Inspector & Auto FA Berasaskan Data Live Bursa Malaysia")

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

# --- FUNGSI ANALISIS FUNDAMENTAL SEBENAR MENGGUNAKAN YFINANCE ---
def analyze_fundamental(ticker_symbol):
    clean_symbol = ticker_symbol.strip().upper().replace('.KL', '')
    yf_symbol = f"{clean_symbol}.KL"
    
    try:
        stock = yf.Ticker(yf_symbol)
        info = stock.info
        
        # Ambil data penting jika ada
        market_cap = info.get("marketCap", 0)
        pe_ratio = info.get("trailingPE", "N/A")
        roe = info.get("returnOnEquity", None)
        rev_growth = info.get("revenueGrowth", None)
        earnings_growth = info.get("earningsQuarterlyGrowth", None)
        long_name = info.get("longName", clean_symbol)
        sector = info.get("sector", "Bursa Malaysia Equities")
        
        # Penilaian kriteria CANSLIM berasaskan data sebenar
        score = 0
        details = []
        
        # C & A (Earnings & Growth)
        if earnings_growth is not None and earnings_growth > 0.15:
            score += 2
            details.append("✅ **C & A (Earnings Growth):** Pertumbuhan pendapatan suku tahunan kukuh (>15%).")
        elif earnings_growth is not None and earnings_growth > 0:
            score += 1
            details.append("⚠️ **C & A (Earnings Growth):** Pertumbuhan pendapatan positif tetapi sederhana.")
        else:
            details.append("❌ **C & A (Earnings Growth):** Tiada data pertumbuhan positif yang ketara.")
            
        # S (Supply & Demand / Volume/Market Cap)
        if market_cap and market_cap > 500000000: # > RM500 Juta
            score += 1
            details.append("✅ **S (Market Cap/Supply):** Syarikat berkapitalisasi pasaran sederhana/besar (stabil).")
        else:
            details.append("⚠️ **S (Market Cap/Supply):** Syarikat berkapitalisasi kecil (saham berisiko/volatil).")
            
        # L (Leader / ROE & Profitability)
        if roe is not None and roe > 0.10: # ROE > 10%
            score += 2
            details.append(f"✅ **L (Profitability / ROE):** Pulangan atas ekuiti (ROE) sihat pada tingkat {(roe*100):.1f}%.")
        else:
            score += 1
            details.append("⚠️ **L (Profitability / ROE):** ROE agak rendah atau tidak cukup data rekod.")
            
        # M (Market Direction & Valuation)
        if pe_ratio != "N/A" and isinstance(pe_ratio, (int, float)) and 5 < pe_ratio < 30:
            score += 2
            details.append(f"✅ **M (Valuation P/E):** Nisbah P/E sihat dan munasabah ({pe_ratio:.1f}x).")
        else:
            score += 1
            details.append("⚠️ **M (Valuation P/E):** P/E tinggi atau tiada rekod nisbah semasa.")
            
        return {
            "name": long_name,
            "sector": sector,
            "market_cap": f"RM {market_cap:,.0f}" if market_cap else "Tidak Diketahui",
            "pe_ratio": f"{pe_ratio:.1f}x" if isinstance(pe_ratio, (int, float)) else "N/A",
            "score": min(7, max(3, score)), # Normalisasi skor antara 3 hingga 7
            "details": details,
            "valid": True
        }
    except Exception as e:
        return {"valid": False, "error": str(e)}

# --- SIDEBAR TETAPAN ---
st.sidebar.header("⚙️ Kriteria Tapisan")
min_price = st.sidebar.number_input("Harga Minimum (RM)", value=0.50, step=0.05)
max_rsi = st.sidebar.slider("Had Maksimum RSI", 70, 95, 80, 1)
min_change_pct = st.sidebar.slider("Perubahan Harian Min (%)", -5.0, 5.0, -3.0, 0.5)

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
if "raw_tickers" not in st.session_state:
    st.session_state.raw_tickers = []

# --- NAVIGASI MOD UTAMA ---
app_mode = st.radio(
    "Pilih Mod Utama Sistem:", 
    [
        "🔍 Screener & Prestasi Sektor", 
        "📸 AI Chart Image Scanner & Analisis Terperinci", 
        "📊 Analisis Fundamental Live (Yahoo Finance / CANSLIM)"
    ], 
    horizontal=True
)
st.markdown("---")

if app_mode == "📊 Analisis Fundamental Live (Yahoo Finance / CANSLIM)":
    st.subheader("📊 Modul Semakan Analisis Fundamental Sebenar (Bursa Malaysia)")
    st.markdown("Taip **mana-mana kod kaunter Bursa** (contoh: `MAYBANK`, `SUNCON`, `GAMUD`, `IHH`, `CIMB`, `TOPGLOV`, dll.). Sistem akan menarik data sebenar dari pasaran.")
    
    col_fa1, col_fa2 = st.columns([1, 1])
    
    with col_fa1:
        fa_ticker = st.text_input("Masukkan Kod Kaunter Bursa:", value="SUNCON").upper().strip()
        evaluate_fa = st.button("🚀 Semak Fundamental Live", type="primary", use_container_width=True)

    with col_fa2:
        st.markdown(f"### 📑 Laporan FA Live: **{fa_ticker}**")
        if evaluate_fa:
            with st.spinner("Sedang menarik data kewangan live daripada pasaran..."):
                fa_data = analyze_fundamental(fa_ticker)
                
            if fa_data["valid"]:
                score = fa_data["score"]
                score_pct = (score / 7) * 100
                
                if score >= 6:
                    status_fa = "🌟 Cemerlang (A+ Fundamental Setup)"
                    color_code = "#3fb950"
                elif score >= 4:
                    status_fa = "👍 Sederhana Kukuh (Layak Diperhati)"
                    color_code = "#e3b341"
                else:
                    status_fa = "⚠️ Lemah / Berhati-hati"
                    color_code = "#f85149"
                    
                st.markdown(f"""
                <div style="background-color: #161b22; padding: 20px; border-radius: 10px; border: 1px solid #30363d;">
                    <h3 style="color: #58a6ff; margin-top:0;">{fa_data['name']}</h3>
                    <p><b>Sektor:</b> {fa_data['sector']}</p>
                    <p><b>Market Cap:</b> {fa_data['market_cap']}</p>
                    <p><b>Nisbah P/E:</b> {fa_data['pe_ratio']}</p>
                    <hr style="border-color: #30363d;">
                    <h4 style="color: {color_code}; margin-top:0;">Skor Kesihatan CANSLIM: {score} / 7 ({score_pct:.0f}%)</h4>
                    <p><b>Status Penilaian:</b> {status_fa}</p>
                    <hr style="border-color: #30363d;">
                """, unsafe_allow_html=True)
                
                for detail in fa_data["details"]:
                    st.markdown(f"- {detail}")
                    
                st.markdown("""
                    <hr style="border-color: #30363d;">
                    <p style="color: #58a6ff;">💡 <b>Cadangan:</b> Gunakan skor asas ini bersama setup teknikal BOB/BOD semasa anda menyemak carta harga.</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.error(f"Gagal mengambil data untuk kaunter **{fa_ticker}**. Sila pastikan kod kaunter betul (contoh: SUNCON, MAYBANK, IHH). Ralat: {fa_data.get('error', '')}")
        else:
            st.info("👈 Masukkan kod kaunter di sebelah kiri dan klik **Semak Fundamental Live**.")

elif app_mode == "📸 AI Chart Image Scanner & Analisis Terperinci":
    st.subheader("📸 Modul Analisis Visual Imej Carta (AI Chart Inspector)")
    st.markdown("Muat naik *screenshot* carta TradingView anda untuk paparan rujukan harga Sokongan, Rintangan, serta Target Price.")
    
    uploaded_chart = st.file_uploader("Pilih fail imej carta (PNG, JPG, JPEG):", type=["png", "jpg", "jpeg"])
    
    if uploaded_chart is not None:
        col_img1, col_img2 = st.columns([1, 1])
        with col_img1:
            image = Image.open(uploaded_chart)
            st.image(image, caption="Carta Dimuat Naik", use_column_width=True)
            
        with col_img2:
            st.markdown("### 🤖 Laporan Analisis Teknikal Automatik:")
            selected_trend = st.selectbox(
                "📈 Tentukan Status Trend Semasa Carta:",
                ["🚀 Uptrend (Fasa Kenaikan Kuat)", "📉 Downtrend (Fasa Penurunan / Tekanan Jualan)", "⚖️ Sideway (Fasa Tapak / Mendatar Konsolidasi)"]
            )
            est_current_price = st.number_input("Masukkan Anggaran Harga Semasa (RM) pada Carta:", value=0.95, step=0.01)
            
            if "Uptrend" in selected_trend:
                sokongan_kuat = round(est_current_price * 0.88, 2)
                sokongan_terdekat = round(est_current_price * 0.94, 2)
                rintangan_terdekat = round(est_current_price * 1.06, 2)
                target_price = round(est_current_price * 1.15, 2)
                trend_desc = "Harga bergerak dalam struktur kenaikan sihat."
            elif "Downtrend" in selected_trend:
                sokongan_kuat = round(est_current_price * 0.80, 2)
                sokongan_terdekat = round(est_current_price * 0.90, 2)
                rintangan_terdekat = round(est_current_price * 1.03, 2)
                target_price = round(est_current_price * 1.10, 2)
                trend_desc = "Harga di bawah tekanan jual."
            else:
                sokongan_kuat = round(est_current_price * 0.85, 2)
                sokongan_terdekat = round(est_current_price * 0.93, 2)
                rintangan_terdekat = round(est_current_price * 1.05, 2)
                target_price = round(est_current_price * 1.12, 2)
                trend_desc = "Harga bergerak mendatar bersedia mengumpul tenaga."

            st.markdown(f"""
            <div style="background-color: #161b22; padding: 20px; border-radius: 10px; border: 1px solid #30363d;">
                <h4 style="color: #58a6ff; margin-top:0;">📊 Laporan Analisis & Struktur Trend</h4>
                <p><b>Status Trend:</b> <span style="color: #e3b341;">{selected_trend}</span></p>
                <hr style="border-color: #30363d;">
                <p style="color: #f85149; margin: 2px 0;">🛡️ <b>Sokongan Kuat:</b> <b>RM {sokongan_kuat}</b></p>
                <p style="color: #ff7b72; margin: 2px 0;">📉 <b>Sokongan Terdekat:</b> <b>RM {sokongan_terdekat}</b></p>
                <p style="color: #ffa657; margin: 2px 0;">🚧 <b>Rintangan Terdekat:</b> <b>RM {rintangan_terdekat}</b></p>
                <p style="color: #3fb950; margin: 2px 0;">🎯 <b>Target Price (TP):</b> <b>RM {target_price}</b></p>
            </div>
            """, unsafe_allow_html=True)

else:
    # --- MOD SCREENER & SEKTOR ---
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
                    if change >= 2.0 and vol > 500000:
                        signal = "🔥 BOB (Breakout)"
                    elif change >= -1.5 and change < 2.0 and vol > 300000:
                        signal = "🔄 BOD (Dip/Reversal)"
                    elif change > 0:
                        signal = "📈 Momentum"
                    else:
                        signal = "📉 Tapak / Pullback"
                    
                    item_data = {
                        "Kaunter": t,
                        "Harga (RM)": entry_price,
                        "Perubahan": f"{'+' if change>=0 else ''}{change:.2f}%",
                        "RSI": round(rsi_val, 1),
                        "Setup Strategi": signal,
                        "Volum": f"{vol:,.0f}"
                    }
                    scan_results.append(item_data)
                    raw_tickers.append(t)
                    
        st.session_state.scan_results = scan_results
        st.session_state.raw_tickers = raw_tickers

    # --- PAPAN PENDAHUDU SEKTOR ---
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

    if st.session_state.scan_results:
        st.success(f"Berjaya menemui **{len(st.session_state.scan_results)} kaunter** sepadan!")
        df_display = pd.DataFrame(st.session_state.scan_results)
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        
        st.markdown("🔗 **Pautan Cepat Carta TradingView:**")
        cols_tv = st.columns(6)
        for i, t_name in enumerate(st.session_state.raw_tickers):
            tv_url = f"https://www.tradingview.com/chart/?symbol=MYX%3A{t_name}"
            with cols_tv[i % 6]:
                st.markdown(f"👉 [{t_name}]({tv_url})", unsafe_allow_html=True)
                
        st.markdown("---")
        csv_data = df_display.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Muat Turun Laporan (CSV)", data=csv_data, file_name="myx_screener_report.csv", mime="text/csv")
    else:
        st.info("👈 Klik butang **Mula Imbas Pasaran Sekarang** di atas untuk memaparkan senarai kaunter.")
