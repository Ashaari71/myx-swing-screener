import base64
import re
import time
from pathlib import Path

import streamlit as st
from openai import OpenAI

st.set_page_config(page_title="Screener & AI Chart Filter", layout="wide")

PROMPT_PENAPIS_PENUH = """
Bertindak sebagai penapis setup teknikal yang ketat untuk strategi Buy on Breakout (BOB) dan Buy on Dip (BOD).
Fokus utama analisis adalah hala tuju pergerakan (market direction), kebarangkalian senario, dan idea dagangan yang berdisiplin.

Nilai carta ini secara objektif. Berikan idea dagangan HANYA JIKA salah satu syarat di bawah dipenuhi secara jelas pada struktur harga semasa:

1. SYARAT BOB KETAT (Anti-Fake Breakout):
Setup BOB hanya dianggap berpotensi sah jika memenuhi sekurang-kurangnya 3 daripada 4 kriteria berikut:
- Penutupan Kukuh (Close Confirmation): Harga berjaya ditutup (close) melepasi zon rintangan/konsolidasi, bukan sekadar mencucuk atau meninggalkan ekor atas (upper wick) yang panjang dan ditolak semula ke bawah rintangan.
- Sokongan Volume / RVOL: Pergerakan tembusan disokong oleh lonjakan volume atau RVOL yang jelas lebih tinggi berbanding purata/hari sebelumnya.
- Struktur Trend Menyokong: Harga berada dalam struktur uptrend atau keluar dari fasa konsolidasi yang kemas, dengan paras sokongan terdekat / EMA tidak terlalu jauh sehingga risiko cut loss menjadi tidak masuk akal.
- Ruang Pergerakan (Clear Path): Tiada halangan rintangan major yang terlalu rapat tepat di atas paras breakout.

AMARAN FAKE BREAKOUT (Wajib Tolak / Tunggu jika berlaku):
- Lilin tembusan mempunyai upper shadow/wick panjang menandakan penolakan penjual.
- Harga sekadar "spike" singkat melepasi rintangan tetapi gagal mengekalkan kedudukan.
- Breakout berlaku dalam keadaan volume mendatar/lemah atau pasaran choppy/sideways.
Jika tanda-tanda ini kelihatan, anggap ia sebagai potensi FALSE BREAKOUT dan tandakan status sebagai [TIADA SETUP - TUNGGU].

2. SYARAT BOD KETAT (Anti-Pisau Jatuh):
Setup BOD hanya dianggap berpotensi sah jika memenuhi sekurang-kurangnya 3 daripada 4 kriteria berikut:
- Konteks Trend Menaik Terpelihara: Struktur keseluruhan masih menunjukkan kecenderungan menaik dan harga belum memecahkan paras sokongan struktur utama secara jelas.
- Penurunan Terkawal (Bukan Menjunam): Pullback berlaku secara berperingkat atau perlahan menuju zon sokongan (EMA 20 / EMA 50 / support), bukan siri lilin merah besar yang agresif.
- Isyarat Penolakan / Kestabilan di Sokongan: Terdapat tanda pembeli mula mempertahankan zon sokongan (lower shadow / wick panjang di bawah, lilin pemulihan, atau kestabilan harga).
- Volume Terkawal / Tidak Panik: Penurunan tidak disertai lonjakan volume jualan yang luar biasa.

AMARAN PISAU JATUH / DOWNTREND (Wajib Tolak / Tunggu jika berlaku):
- Harga jatuh melepasi paras sokongan penting atau EMA utama secara jelas dan gagal bertahan.
- Terdapat lilin merah besar berturut-turut atau tekanan jualan agresif dengan volume tinggi.
- Struktur harga membentuk lower high dan lower low yang jelas.
Jika tanda-tanda ini kelihatan, anggap ia sebagai RISIKO PISAU JATUH / DOWNTREND dan tandakan status sebagai [TIADA SETUP - TUNGGU].

ATURAN PENAPISAN MUTLAK:
Jika carta berada dalam keadaan mendatar (sideways) yang bercelaru, downtrend yang jelas, atau tiada isyarat BOB/BOD yang meyakinkan, JANGAN paksa beri idea kemasukan. Tetapkan status sebagai [TIADA SETUP - TUNGGU]. Elakkan penerangan teori indikator secara panjang lebar.

Format output (ringkas & terus ke inti pati):
1. **Status Setup:** [BOB Valid / BOD Valid / TIADA SETUP - TUNGGU]
2. **Hala Tuju & Kebarangkalian:**
   - **Senario Utama (~60-70%):** [Hala tuju pergerakan seterusnya berdasarkan struktur & volume semasa]
   - **Senario Alternatif (~30-40%):** [Perubahan hala tuju jika paras kritikal ditembusi atau gagal bertahan]
3. **Paras Kritikal:** Rintangan [paras] | Sokongan [paras]
4. **Idea Tindakan (Jika Valid Sahaja):**
   - **Jenis:** [BOB / BOD / Tiada]
   - **Trigger Masuk:** [Syarat pengesahan]
   - **Paras Batal:** [Paras harga jika struktur gagal]
"""


def dapatkan_openai_client() -> OpenAI | None:
    api_key = ""
    if "OPENAI_API_KEY" in st.secrets:
        api_key = st.secrets["OPENAI_API_KEY"]
    if not api_key:
        import os
        api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def encode_image_bytes_base64(image_bytes: bytes) -> str:
    return base64.b64encode(image_bytes).decode("utf-8")


def analisis_carta_bytes(
    image_bytes: bytes,
    mime_type: str = "image/png",
    ticker: str = "",
    timeframe: str = "Daily",
    rvol: float | None = None,
    ema20: float | None = None,
    ema50: float | None = None,
    model: str = "gpt-4o",
    max_retries: int = 2,
) -> str:
    client = dapatkan_openai_client()
    if client is None:
        return "1. **Status Setup:** TIADA SETUP - TUNGGU\nOPENAI_API_KEY belum dijumpai."

    b64_img = encode_image_bytes_base64(image_bytes)

    konteks = [f"Timeframe: {timeframe}"]
    if ticker:
        konteks.append(f"Kaunter: {ticker.upper()}")
    if rvol is not None:
        konteks.append(f"RVOL: {rvol:.2f}x")
    if ema20 is not None:
        konteks.append(f"EMA 20: {ema20:.3f}")
    if ema50 is not None:
        konteks.append(f"EMA 50: {ema50:.3f}")

    user_text = f"Data Rujukan: {' | '.join(konteks)}\n\n{PROMPT_PENAPIS_PENUH}"

    for percubaan in range(max_retries + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=0.1,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Anda ialah penganalisis teknikal yang berdisiplin, objektif, "
                            "dan ketat menapis setup dagangan tanpa rekaan."
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_text},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{b64_img}",
                                    "detail": "high",
                                },
                            },
                        ],
                    },
                ],
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            if percubaan < max_retries:
                time.sleep(1.5 * (percubaan + 1))
                continue
            return f"1. **Status Setup:** TIADA SETUP - TUNGGU\nRalat API OpenAI: {exc}"

    return "1. **Status Setup:** TIADA SETUP - TUNGGU"


def ekstrak_status_setup(teks_analisis: str) -> str:
    if not teks_analisis:
        return "TIADA SETUP - TUNGGU"

    padanan = re.search(
        r"status\s*setup\s*[:\-]?\s*\*?\*?([^\n\r]+)",
        teks_analisis,
        flags=re.IGNORECASE,
    )
    rujukan = padanan.group(1) if padanan else teks_analisis
    kecil = rujukan.lower()

    if re.search(r"\b(bukan|tidak|tiada)\b[^\n]{0,25}\b(bob valid|bod valid)\b", kecil):
        return "TIADA SETUP - TUNGGU"

    if "bob valid" in kecil:
        return "BOB Valid"
    if "bod valid" in kecil:
        return "BOD Valid"
    return "TIADA SETUP - TUNGGU"


def url_tradingview_bursa(ticker: str) -> str:
    bersih = ticker.strip().upper().replace(".KL", "")
    return f"https://www.tradingview.com/chart/?symbol=MYX%3A{bersih}"


# --- Antara Muka Uji Pantas ---
st.title("Analisis Carta AI — Penapis BOB & BOD")

if "senarai_hasil" not in st.session_state:
    st.session_state["senarai_hasil"] = []

col1, col2, col3 = st.columns(3)
with col1:
    ticker_input = st.text_input("Kaunter (Bursa)", value="PEKAT")
    timeframe_input = st.selectbox("Timeframe", ["Daily", "15m", "1H"])
with col2:
    rvol_input = st.number_input("RVOL", min_value=0.0, value=1.50, step=0.10)
    ema20_input = st.number_input("EMA 20", min_value=0.0, value=0.000, step=0.005, format="%.3f")
with col3:
    ema50_input = st.number_input("EMA 50", min_value=0.0, value=0.000, step=0.005, format="%.3f")
    uploaded_img = st.file_uploader("Muat Naik Gambar Carta", type=["png", "jpg", "jpeg"])

if st.button("Analisis Carta", type="primary"):
    if uploaded_img is None:
        st.warning("Sila muat naik gambar carta terlebih dahulu.")
    else:
        with st.spinner("Sedang menganalisis carta..."):
            teks_out = analisis_carta_bytes(
                image_bytes=uploaded_img.getvalue(),
                mime_type=uploaded_img.type or "image/png",
                ticker=ticker_input,
                timeframe=timeframe_input,
                rvol=rvol_input if rvol_input > 0 else None,
                ema20=ema20_input if ema20_input > 0 else None,
                ema50=ema50_input if ema50_input > 0 else None,
            )
            status_out = ekstrak_status_setup(teks_out)
            st.session_state["senarai_hasil"].insert(
                0,
                {
                    "ticker": ticker_input.strip().upper(),
                    "status": status_out,
                    "timeframe": timeframe_input,
                    "rvol": rvol_input if rvol_input > 0 else None,
                    "analisis": teks_out,
                    "tv_url": url_tradingview_bursa(ticker_input),
                },
            )

st.divider()
st.subheader("Setup Sah (BOB Valid / BOD Valid)")

hasil_valid = [
    x for x in st.session_state["senarai_hasil"]
    if x["status"] in ("BOB Valid", "BOD Valid")
]

if not hasil_valid:
    st.info("Belum ada setup BOB Valid atau BOD Valid.")
else:
    for item in hasil_valid:
        rvol_txt = f" | RVOL: {item['rvol']:.2f}x" if item["rvol"] is not None else ""
        tajuk = f"**{item['ticker']}** — `{item['status']}` ({item['timeframe']}){rvol_txt}"
        with st.expander(tajuk, expanded=True):
            st.markdown(item["analisis"])
            st.markdown(f"[Buka Carta di TradingView]({item['tv_url']})")

hasil_ditolak = [
    x for x in st.session_state["senarai_hasil"]
    if x["status"] == "TIADA SETUP - TUNGGU"
]
if hasil_ditolak:
    with st.expander(f"Kaunter Ditolak / Tunggu ({len(hasil_ditolak)})", expanded=False):
        for item in hasil_ditolak:
            st.markdown(f"**{item['ticker']}** ({item['timeframe']}) — `TIADA SETUP - TUNGGU`")
            st.caption(item["analisis"])
