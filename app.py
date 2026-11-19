import base64
import io
import numpy as np
import pandas as pd
import requests
import streamlit as st
from PIL import Image

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except Exception:
    OpenAI = None
    OPENAI_AVAILABLE = False

st.set_page_config(page_title="MYX Swing Pro Screener", page_icon="📈", layout="wide")

st.markdown(
    """
    <style>
    .main { background-color: #0e1117; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("📈 MYX Swing Pro: Screener, AI Vision & Watchlist")
st.markdown(
    "Penapis Uptrend Patuh Syariah (EMA20/EMA50/RSI/RVOL), Prestasi Sektor, AI Chart Inspector & Multi-TP"
)

NON_SHARIAH_EXCLUDED = {
    "MAYBANK", "CIMB", "PBBANK", "HLBANK", "RHBBANK", "AMBANK",
    "ABMB", "AFFIN", "MBSB", "BIMB", "HLFG", "LPI", "ALLIANZ",
    "TAKAFUL", "BURSA", "GENTING", "GENM", "MAGNUM", "SPTOTO",
    "CARLSBG", "HEIM", "BAT", "ASTRO", "CAPITALA",
}

sector_benchmarks = {
    "🔥 Pembinaan & Infrastruktur (Construction)": ["GAMUD", "SUNCON", "IJM", "MRCB", "WCT", "KERJAYA"],
    "⚡ Tenaga Boleh Baharu & Utiliti (Energy/RE)": ["CITAGLB", "SAMAIDEN", "PEKAT", "TENAGA", "YTLPOWR", "SOLARVEST"],
    "💻 Teknologi & Semikonduktor (Tech)": ["FRONTKN", "INARI", "KGB", "MYEG", "UNISEM", "GTRONIC", "VITROX"],
    "🏥 Penjagaan Kesihatan (Healthcare)": ["KPJ", "IHH", "TOPGLOV", "HARTA"],
    "🌾 Perladangan & Komoditi (Plantation)": ["KLK", "IOICORP", "FGV", "SIMEPROP"],
    "⚙️ Perindustrian & Telco (Industrial/Telco)": ["CDB", "MAXIS", "SIME", "PMETAL", "ANCOMNY", "WASCO"],
}

master_bursa_tickers = []
ticker_to_sector = {}
for sec_name, t_list in sector_benchmarks.items():
    for t in t_list:
        ticker_to_sector[t] = sec_name
    master_bursa_tickers.extend(t_list)
master_bursa_tickers = list(set(master_bursa_tickers))


def fetch_tradingview_scanner(tickers):
    formatted_symbols = [f"MYX:{t.strip().replace('.KL', '')}" for t in tickers]
    url = "https://scanner.tradingview.com/malaysia/scan"
    payload = {
        "symbols": {"tickers": formatted_symbols},
        "columns": [
            "close", "change", "volume", "RSI",
            "MACD.macd", "MACD.signal", "BB.upper", "BB.lower",
            "EMA20", "EMA50", "volume[1]", "relative_volume_10d_calc",
        ],
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
                    "close": vals[0] if len(vals) > 0 and vals[0] is not None else 0.0,
                    "change": vals[1] if len(vals) > 1 and vals[1] is not None else 0.0,
                    "volume": vals[2] if len(vals) > 2 and vals[2] is not None else 0,
                    "prev_volume": vals[10] if len(vals) > 10 and vals[10] is not None else 0,
                    "rvol": vals[11] if len(vals) > 11 and vals[11] is not None else 0.0,
                    "rsi": vals[3] if len(vals) > 3 and vals[3] is not None else 50.0,
                    "macd": vals[4] if len(vals) > 4 and vals[4] is not None else 0.0,
                    "macd_signal": vals[5] if len(vals) > 5 and vals[5] is not None else 0.0,
                    "bb_upper": vals[6] if len(vals) > 6 and vals[6] is not None else 0.0,
                    "bb_lower": vals[7] if len(vals) > 7 and vals[7] is not None else 0.0,
                    "ema20": vals[8] if len(vals) > 8 and vals[8] is not None else 0.0,
                    "ema50": vals[9] if len(vals) > 9 and vals[9] is not None else 0.0,
                }
            return results
    except Exception:
        pass
    return {}


def semak_uptrend_menaik(info, rsi_min=50.0, rsi_max=80.0):
    harga = info.get("close", 0.0)
    ema20 = info.get("ema20", 0.0)
    ema50 = info.get("ema50", 0.0)
    rsi_val = info.get("rsi", 0.0)
    ema_valid = (ema20 > 0) and (ema50 > 0) and (harga > ema20) and (ema20 > ema50)
    rsi_valid = (rsi_val >= rsi_min) and (rsi_val <= rsi_max)
    return ema_valid and rsi_valid


st.sidebar.header("⚙️ Kriteria Tapisan Asas")
min_price = st.sidebar.number_input("Harga Minimum (RM)", value=0.50, step=0.05)
filter_shariah_only = st.sidebar.checkbox("Tapis Keluar Saham Bukan Syariah (Bank/Konvensional)", value=True)
filter_uptrend_only = st.sidebar.checkbox("Hanya Uptrend Menaik (Harga > EMA20 > EMA50)", value=True)
min_rsi = st.sidebar.slider("Had Minimum RSI (Uptrend)", 30, 65, 50, 1)
max_rsi = st.sidebar.slider("Had Maksimum RSI", 70, 95, 80, 1)
min_change_pct = st.sidebar.slider("Perubahan Harian Min (%)", -5.0, 5.0, -2.0, 0.5)

st.sidebar.markdown("---")
st.sidebar.header("🎛️ Penapisan Indikator & Volum")
min_rvol = st.sidebar.slider("RVOL Minimum (10D) [0 = Semua, 1.2 = Sihat, 1.5 = Kuat]", 0.0, 3.0, 0.0, 0.1)
filter_vol_higher = st.sidebar.checkbox("Hanya Volum > Volum Sebelumnya", value=False)
filter_macd = st.sidebar.checkbox("Hanya MACD Bullish Crossover (MACD > Signal)", value=False)
filter_bb_squeeze = st.sidebar.checkbox("Hanya Bollinger Bands Squeeze (Konsolidasi Sempit)", value=False)

st.sidebar.markdown("---")
st.sidebar.header("🤖 OpenAI API Tetapan")
openai_api_key = st.sidebar.text_input("OpenAI API Key", type="password", placeholder="sk-...")

st.sidebar.markdown("---")
st.sidebar.header("🔔 Telegram Bot Alert (Manual Test)")
telegram_token = st.sidebar.text_input("Telegram Bot Token", type="password")
telegram_chat_id = st.sidebar.text_input("Telegram Chat ID")

st.sidebar.markdown("---")
st.sidebar.header("🧮 Kalkulator Risiko & Multi-TP")
calc_capital = st.sidebar.number_input("Jumlah Modal (RM):", value=10000.0, step=500.0)
calc_risk_pct = st.sidebar.slider("Risiko Maksimum (% dari Modal):", 1.0, 5.0, 2.0, 0.5)
calc_entry = st.sidebar.number_input("Harga Beli (Entry) (RM):", value=1.00, step=0.01)
calc_sl = st.sidebar.number_input("Harga Stop-Loss (SL) (RM):", value=0.92, step=0.01)
calc_tp1 = st.sidebar.number_input("Target 1 (TP1 - 50% Lot):", value=1.10, step=0.01)
calc_tp2 = st.sidebar.number_input("Target 2 (TP2 - 50% Lot):", value=1.25, step=0.01)

if calc_entry > 0 and calc_sl > 0 and calc_entry > calc_sl:
    max_risk_rm = calc_capital * (calc_risk_pct / 100.0)
    risk_per_share = calc_entry - calc_sl
    raw_shares = max_risk_rm / risk_per_share
    suggested_shares = max(100, int(raw_shares // 100) * 100)
    total_investment = suggested_shares * calc_entry
    actual_risk_rm = suggested_shares * risk_per_share

    half_shares = suggested_shares // 2
    profit_tp1 = half_shares * (calc_tp1 - calc_entry) if calc_tp1 > calc_entry else 0.0
    profit_tp2 = half_shares * (calc_tp2 - calc_entry) if calc_tp2 > calc_entry else 0.0
    rr_ratio = (calc_tp2 - calc_entry) / risk_per_share if risk_per_share > 0 else 0.0

    st.sidebar.markdown(
        f"**Jumlah Saham:** {suggested_shares:,} unit ({suggested_shares // 100} Lot)\n\n"
        f"**Modal Diguna:** RM {total_investment:,.2f}\n\n"
        f"**Risiko Maks:** RM {actual_risk_rm:,.2f}\n\n"
        f"**Potensi TP1:** RM {profit_tp1:,.2f}\n\n"
        f"**Potensi TP2:** RM {profit_tp2:,.2f}\n\n"
        f"**Nisbah R:R (TP2):** 1 : {rr_ratio:.2f}"
    )
else:
    st.sidebar.warning("Sila pastikan Harga Entry lebih tinggi daripada Stop-Loss.")


def send_telegram_message(token, chat_id, message):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception:
        return False


def analyze_chart_bob_bod(api_key, image, trend, price):
    if not OPENAI_AVAILABLE or OpenAI is None:
        return "⚠️ Pakej `openai` tidak dipasang dalam environment aplikasi."
    try:
        client = OpenAI(api_key=api_key)
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        buffered = io.BytesIO()
        image.save(buffered, format="JPEG")
        base64_image = base64.b64encode(buffered.getvalue()).decode("utf-8")

        prompt = (
            "Anda adalah Ketua Penganalisis Teknikal Bursa Malaysia pakar strategi BOB & BOD. "
            f"Trend asas: '{trend}', Harga Semasa: RM {price}. "
            "Nilai struktur carta dahulu sama ada benar-benar uptrend menaik atau sideway/downtrend, "
            "kemudian pilih pendekatan BOB atau BOD mengikut kesesuaian carta semasa. "
            "Sila beri laporan dalam Bahasa Melayu merangkumi:\n"
            "1. Analisis Hala Tuju & Struktur Fasa.\n"
            "2. Penilaian Kesesuaian Setup (BOB vs BOD mengikut carta).\n"
            "3. Zon Harga Kritikal (Stop-Loss, Sokongan, Rintangan, TP1 & TP2).\n"
            "4. Cadangan Taktikal Watchlist."
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                    ],
                }
            ],
            max_tokens=800,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ Ralat OpenAI API: {str(e)}"


if "scan_results" not in st.session_state:
    st.session_state.scan_results = []
if "raw_tickers" not in st.session_state:
    st.session_state.raw_tickers = []
if "watchlist" not in st.session_state:
    st.session_state.watchlist = []
if "sector_perf" not in st.session_state:
    st.session_state.sector_perf = []

app_mode = st.radio(
    "Pilih Mod Utama Sistem:",
    [
        "🔍 Screener & Prestasi Sektor",
        "📸 AI Chart Vision (BOB/BOD)",
        "⭐ Watchlist Peribadi",
        "🔗 Pautan Rasmi Bursa",
    ],
    horizontal=True,
)
st.markdown("---")

if app_mode == "🔗 Pautan Rasmi Bursa":
    st.subheader("🔗 Rujukan Pantas Data Rasmi Pasaran")
    st.markdown(
        "* 👉 [Bursa Malaysia Portal](https://www.bursamalaysia.com/)\n"
        "* 👉 [KLSE Screener Portal](https://www.klsescreener.com/)\n"
        "* 👉 [Senarai Sekuriti Patuh Syariah Rasmi (SC Malaysia)](https://www.sc.com.my/development/icm/shariah-compliant-securities/list-of-shariah-compliant-securities)"
    )

elif app_mode == "⭐ Watchlist Peribadi":
    st.subheader("⭐ Senarai Tontonan Peribadi (My Watchlist)")
    if st.session_state.watchlist:
        wl_df = pd.DataFrame(st.session_state.watchlist)
        st.dataframe(wl_df, use_container_width=True, hide_index=True)
        if st.button("🗑️ Kosongkan Watchlist"):
            st.session_state.watchlist = []
            st.rerun()
    else:
        st.info("Tiada kaunter dalam watchlist. Tambah kaunter daripada hasil imbasan screener di tab utama.")

elif app_mode == "📸 AI Chart Vision (BOB/BOD)":
    st.subheader("📸 Modul Analisis AI Khusus Teknik BOB & BOD")
    uploaded_chart = st.file_uploader("Pilih fail imej carta (PNG, JPG, JPEG):", type=["png", "jpg", "jpeg"])

    if uploaded_chart is not None:
        col_img, col_settings = st.columns([1, 1])
        with col_img:
            image = Image.open(uploaded_chart)
            st.image(image, caption="Carta Dimuat Naik", use_column_width=True)
        with col_settings:
            st.markdown("### 🤖 Tetapan Penilaian AI:")
            selected_trend = st.selectbox("Hala Tuju Asas:", ["🚀 Uptrend", "📉 Downtrend", "⚖️ Sideway"])
            est_current_price = st.number_input("Harga Semasa (RM):", value=0.95, step=0.01)
            run_ai_analysis = st.button("✨ Analisis Setup BOB / BOD", type="primary", use_container_width=True)

        st.markdown("---")
        if run_ai_analysis:
            if not openai_api_key:
                st.error("⚠️ Sila masukkan OpenAI API Key di sidebar!")
            else:
                with st.spinner("🤖 OpenAI sedang menilai carta..."):
                    ai_report = analyze_chart_bob_bod(openai_api_key, image, selected_trend, est_current_price)
                st.markdown("### 📊 Laporan Analisis Taktikal AI")
                st.markdown(ai_report)

else:
    scan_mode = st.radio(
        "Pilih Mod Imbasan:",
        ["🤖 Imbas Automatik Seluruh Pasaran", "📂 Imbas Mengikut Sektor"],
        horizontal=True,
    )

    if scan_mode == "📂 Imbas Mengikut Sektor":
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            sel_sector = st.selectbox("Pilih Sektor:", list(sector_benchmarks.keys()))
            default_t = ", ".join(sector_benchmarks[sel_sector])
        with col_m2:
            custom_input = st.text_area("Kod Kaunter:", value=default_t, height=75)
            target_tickers = [t.strip().upper().replace(".KL", "") for t in custom_input.split(",") if t.strip()]
    else:
        target_tickers = master_bursa_tickers

    if filter_shariah_only:
        target_tickers = [t for t in target_tickers if t not in NON_SHARIAH_EXCLUDED]

    run_scan = st.button("🚀 Mula Imbas Pasaran Sekarang", type="primary", use_container_width=True)
    st.markdown("---")

    if run_scan:
        tv_results = fetch_tradingview_scanner(target_tickers)
        scored_results = []
        alert_messages = []

        for t in target_tickers:
            if filter_shariah_only and t in NON_SHARIAH_EXCLUDED:
                continue

            if t in tv_results:
                info = tv_results[t]
                price = info["close"]
                change = info["change"]
                rsi_val = info["rsi"]
                vol = info["volume"]
                prev_vol = info.get("prev_volume", 0)
                rvol = info.get("rvol", 0.0)
                macd = info["macd"]
                macd_sig = info["macd_signal"]
                bb_up = info["bb_upper"]
                bb_low = info["bb_lower"]
                ema20 = info["ema20"]
                ema50 = info["ema50"]

                if price < min_price or rsi_val > max_rsi or change < min_change_pct:
                    continue

                if min_rvol > 0 and rvol < min_rvol:
                    continue

                is_uptrend = semak_uptrend_menaik(info, rsi_min=min_rsi, rsi_max=max_rsi)
                if filter_uptrend_only and not is_uptrend:
                    continue

                vol_is_higher = prev_vol > 0 and vol > prev_vol
                if filter_vol_higher and not vol_is_higher:
                    continue

                if filter_macd and macd <= macd_sig:
                    continue

                if filter_bb_squeeze:
                    bb_width = (bb_up - bb_low) / price if price > 0 else 1.0
                    if bb_width > 0.08:
                        continue

                entry_price = round(price, 2)
                if is_uptrend and change >= 2.0 and vol > 500000:
                    fokus_kajian = "🚀 Uptrend + Momentum (Kaji BOB pada Carta)"
                elif is_uptrend and -1.5 <= change < 2.0 and vol > 300000:
                    fokus_kajian = "🔄 Uptrend + Pullback (Kaji BOD pada Carta)"
                elif is_uptrend:
                    fokus_kajian = "📈 Uptrend Menaik (Kaji BOB/BOD ikut Carta)"
                else:
                    fokus_kajian = "⚖️ Bukan Uptrend Penuh (Perlu Semak Carta)"

                status_vol = "✅ Lebih Tinggi" if vol_is_higher else "⚠️ Lebih Rendah"
                sec_name = ticker_to_sector.get(t, "Lain-lain")

                item_data = {
                    "Kaunter": t,
                    "Sektor": sec_name,
                    "Harga (RM)": entry_price,
                    "EMA20": round(ema20, 2) if ema20 > 0 else "-",
                    "EMA50": round(ema50, 2) if ema50 > 0 else "-",
                    "Perubahan": f"{'+' if change >= 0 else ''}{change:.2f}%",
                    "RSI": round(rsi_val, 1),
                    "RVOL (10D)": f"{rvol:.2f}x" if rvol > 0 else "-",
                    "Status & Fokus": fokus_kajian,
                    "Volum Sebelumnya": f"{prev_vol:,.0f}",
                    "Volum": f"{vol:,.0f}",
                    "Status Volum": status_vol,
                }
                priority_key = (1 if vol_is_higher else 0, change, rvol)
                scored_results.append(
                    (priority_key, t, item_data, is_uptrend, entry_price, rsi_val, rvol, status_vol, fokus_kajian, sec_name)
                )

        scored_results.sort(key=lambda x: x[0], reverse=True)

        scan_results = [x[2] for x in scored_results]
        raw_tickers = [x[1] for x in scored_results]

        for _, t, _, is_uptrend, entry_price, rsi_val, rvol, status_vol, fokus_kajian, sec_name in scored_results:
            if is_uptrend:
                alert_messages.append(
                    f"• *{t}* ({sec_name}) | RM {entry_price:.2f} | RSI {rsi_val:.1f} | RVOL {rvol:.2f}x | {status_vol} | {fokus_kajian}"
                )

        st.session_state.scan_results = scan_results
        st.session_state.raw_tickers = raw_tickers

        if alert_messages and telegram_token and telegram_chat_id:
            full_msg = (
                "🚨 *MYX UPTREND SCREENER ALERT (SHARIAH)* 🚨\nKaunter lulus uptrend menaik:\n"
                + "\n".join(alert_messages)
            )
            send_telegram_message(telegram_token, telegram_chat_id, full_msg)

        sector_perf = []
        for sec_name, t_list in sector_benchmarks.items():
            if filter_shariah_only:
                t_list = [t for t in t_list if t not in NON_SHARIAH_EXCLUDED]
            sec_data = fetch_tradingview_scanner(t_list)
            sec_changes = [v["change"] for v in sec_data.values() if "change" in v]
            avg_ret = np.mean(sec_changes) if sec_changes else 0.0
            status_trend = "🔥 Sektor Leader" if avg_ret > 0.5 else ("📈 Positif" if avg_ret >= 0 else "📉 Lemah")
            sector_perf.append(
                {
                    "Sektor Pasaran": sec_name,
                    "Prestasi (%)": f"{'+' if avg_ret >= 0 else ''}{avg_ret:.2f}%",
                    "Status Trend": status_trend,
                }
            )
        st.session_state.sector_perf = sector_perf

    st.subheader("📊 Prestasi Sektor Semasa")
    if st.session_state.sector_perf:
        st.dataframe(pd.DataFrame(st.session_state.sector_perf), use_container_width=True, hide_index=True)
    else:
        st.info("Klik **Mula Imbas Pasaran Sekarang** untuk memuatkan prestasi sektor terkini dan menapis kaunter uptrend menaik.")

    st.markdown("---")

    if st.session_state.scan_results:
        st.success(f"Berjaya menemui **{len(st.session_state.scan_results)} kaunter** sepadan!")
        df_display = pd.DataFrame(st.session_state.scan_results)
        st.dataframe(df_display, use_container_width=True, hide_index=True)

        st.markdown("### ⭐ Simpan ke Watchlist Peribadi:")
        selected_to_wl = st.selectbox("Pilih kaunter untuk dimasukkan ke Watchlist:", st.session_state.raw_tickers)
        if st.button("➕ Tambah ke Watchlist"):
            match_item = next((item for item in st.session_state.scan_results if item["Kaunter"] == selected_to_wl), None)
            if match_item and match_item not in st.session_state.watchlist:
                st.session_state.watchlist.append(match_item)
                st.success(f"✅ {selected_to_wl} berjaya dimasukkan ke Watchlist!")
            else:
                st.warning("Kaunter sudah ada dalam Watchlist.")

        st.markdown("🔗 **Pautan Cepat Carta TradingView:**")
        cols_tv = st.columns(6)
        for i, t_name in enumerate(st.session_state.raw_tickers):
            tv_url = f"https://www.tradingview.com/chart/?symbol=MYX%3A{t_name}"
            with cols_tv[i % 6]:
                st.markdown(f"👉 [{t_name}]({tv_url})", unsafe_allow_html=True)

        st.markdown("---")
        csv_data = df_display.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Muat Tur
