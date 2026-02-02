import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

# ===================== 頁面設定 =====================
st.set_page_config(
    page_title="採購決策與定價工具",
    page_icon="💰",
    layout="centered"
)

# ===================== CSS =====================
st.markdown(
    """
    <style>
    .block-container {
        max-width: 550px;
        padding-top: 1rem;
        padding-bottom: 1rem;
        padding-left: 0.1rem;
        padding-right: 0.1rem;
    }
    .stButton>button {
        font-weight: bold;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ===================== 輔助函數 =====================
def format_large_number(num):
    if abs(num) >= 1_000_000:
        return f"{num / 1_000_000:,.3f} M"
    elif abs(num) >= 1_000:
        return f"{num / 1_000:,.3f} K"
    else:
        return f"{num:,.3f}"

# ===================== 台銀 USD 匯率 =====================
@st.cache_data(ttl=3600)
def get_tw_bank_usd_rate():
    try:
        url = "https://rate.bot.com.tw/xrt?Lang=zh-TW"
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        rows = soup.select("table.table tbody tr")
        for row in rows:
            if "美元" in row.text:
                return float(row.select("td")[4].text.strip())
    except Exception:
        pass
    return None

# ===================== ECB 匯率 =====================
@st.cache_data(ttl=3600)
def get_ecb_rates():
    url = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
    res = requests.get(url, timeout=10)
    res.raise_for_status()

    tree = ET.fromstring(res.content)
    rates = {}

    for cube in tree.findall(".//{*}Cube[@currency]"):
        rates[cube.attrib["currency"]] = float(cube.attrib["rate"])

    return rates  # EUR base

# ===================== Yahoo Finance 匯率 =====================
@st.cache_data(ttl=3600)
def get_yahoo_rate(pair):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{pair}=X"
    res = requests.get(url, timeout=10)
    res.raise_for_status()
    data = res.json()
    return data["chart"]["result"][0]["meta"]["regularMarketPrice"]

# ===================== 顯示用匯率（TWD base） =====================
@st.cache_data(ttl=3600)
def get_display_currency_rates():
    rates = {"TWD": 1.0}

    try:
        ecb = get_ecb_rates()
        eur_twd = get_yahoo_rate("EURTWD")

        rates["EUR"] = eur_twd
        rates["USD"] = eur_twd * ecb.get("USD", 0)
        rates["JPY"] = eur_twd * ecb.get("JPY", 0)
    except Exception:
        pass

    return rates

# ===================== 計算表 =====================
def calculate_price_table(cost, currency, rate, quantity):
    cost_twd = cost if currency == "TWD" else cost * rate
    rates = [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.5]
    data = []

    for r in rates:
        selling_price = cost_twd / (1 - r)
        data.append({
            "利潤比例_float": r,
            "利潤比例": f"{int(r*100)}%",
            "利潤率售價 (TWD)": round(selling_price, 3),
            "單個利潤 (TWD)": round(selling_price - cost_twd, 3),
            "總利潤 (TWD)": round((selling_price - cost_twd) * quantity, 3)
        })

    return pd.DataFrame(data), cost_twd

# ===================== UI =====================
st.title("🛒 採購決策與定價評估")
st.markdown("---")

col1, col2, col3, col4 = st.columns(4)

with col1:
    cost = st.number_input("單個成本", min_value=0.0, value=1.3, step=0.001, format="%.3f")

with col2:
    currency = st.selectbox("幣別", ["USD", "TWD"])

with col3:
    if "usd_rate" not in st.session_state:
        st.session_state.usd_rate = get_tw_bank_usd_rate() or 32.0

    rate = st.number_input(
        "USD → TWD",
        value=st.session_state.usd_rate,
        step=0.0001,
        format="%.4f",
        disabled=(currency == "TWD")
    )

with col4:
    quantity = st.number_input("下單數量", min_value=1, value=100, step=1)

st.markdown("---")

if st.button("更新台銀匯率", use_container_width=True):
    st.cache_data.clear()
    new_rate = get_tw_bank_usd_rate()
    if new_rate:
        st.session_state.usd_rate = new_rate
        st.rerun()

# ===================== 計算 =====================
if cost > 0:
    df_result, cost_twd = calculate_price_table(cost, currency, rate, quantity)

    st.subheader("🎯 定價決策")
    profit_ratio = st.slider("目標利潤率 (%)", 0.0, 50.0, 20.0, 0.1)
    profit_ratio_float = profit_ratio / 100

    selling_price = cost_twd / (1 - profit_ratio_float)
    unit_profit = selling_price - cost_twd
    total_profit = unit_profit * quantity

    st.markdown("---")

    col_kpi_1, col_kpi_2, col_kpi_3 = st.columns(3)

    col_kpi_1.metric("單位成本 (TWD)", f"{cost_twd:,.3f}")
    col_kpi_2.metric("建議售價 (TWD)", f"{selling_price:,.3f}", delta=f"{profit_ratio:.1f}%")
    col_kpi_3.metric("總預期利潤 (TWD)", format_large_number(total_profit))

    st.markdown("---")
    st.header("📊 利潤級距比較表")

display_currency = st.selectbox(
    "售價顯示幣別",
    ["TWD", "USD", "EUR", "JPY"]
)

DISPLAY_CURRENCY_RATES = get_display_currency_rates()

if display_currency not in DISPLAY_CURRENCY_RATES:
    st.warning(f"⚠️ 無法取得 {display_currency} 匯率，目前僅顯示 TWD")
    display_rate = 1.0
else:
    display_rate = DISPLAY_CURRENCY_RATES[display_currency]
    st.caption(f"📌 匯率：1 {display_currency} = {display_rate:.4f} TWD")

df_display = df_result.copy()

df_display["利潤率售價"] = (
    df_display["利潤率售價 (TWD)"] / display_rate
).round(3)

df_display = df_display[[
    "利潤比例",
    "利潤率售價",
    "單個利潤 (TWD)",
    "總利潤 (TWD)"
]]

df_display = df_display.rename(columns={
    "利潤率售價": f"利潤率售價 ({display_currency})"
})

st.dataframe(df_display, use_container_width=True)
else:
    st.warning("請輸入有效的成本金額")
