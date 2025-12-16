import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup

# --- ⚙️ 頁面設定 ---
st.set_page_config(
    page_title="商品定價工具",
    layout="centered"  # 使用置中佈局
)

# --- 🎯 調整視窗寬度與留白邊界的 CSS 腳本 ---
# 註: 這段程式碼必須在 st.set_page_config 之後，且在 Streamlit 介面元件之前執行
st.markdown(
    """
    <style>
    /* 1. 調整主要內容的寬度與內邊距 (核心區域) */
    .block-container {
        /* 設定最大寬度為 450px，這是您嘗試更窄的效果 */
        max-width: 5 50px; 
        
        /* 減少頂部、底部、左側和右側的內邊距 (Padding) */
        padding-top: 1rem;
        padding-bottom: 1rem;
        padding-left: 0.1rem;  /* 左右邊距減少 */
        padding-right: 0.1rem; /* 左右邊距減少 */
    }
    
    /* 2. 減少 Streamlit 頂部和底部容器的間距 */
    /* st-emotion-cache-18ni2gq / st-emotion-cache-z5rd0u 是 Streamlit 容器的 CSS 類別 */
    .st-emotion-cache-18ni2gq, .st-emotion-cache-z5rd0u {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    
    /* 3. 調整頁面標題（讓標題更靠上） */
    .st-emotion-cache-1jm6hrf { /* Streamlit 標題 H1 的 CSS 類別 */
        margin-top: 0rem;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# 🔹 抓台灣銀行美元即期賣出匯率 (使用 Streamlit 的緩存機制)
@st.cache_data(ttl=3600) # 緩存數據一小時，避免頻繁請求
def get_tw_bank_usd_rate():
    """抓取台灣銀行美元即期賣出匯率。"""
    try:
        url = "https://rate.bot.com.tw/xrt?Lang=zh-TW"
        res = requests.get(url, timeout=10)
        res.raise_for_status() # 檢查請求是否成功
        
        soup = BeautifulSoup(res.text, "html.parser")
        rows = soup.select("table.table tbody tr")
        
        for row in rows:
            if "美元" in row.text:
                rate_text = row.select("td")[4].text.strip() # 即期賣出
                return float(rate_text)
        return None
    except Exception as e:
        st.error(f"無法取得台銀匯率，請檢查網路或手動輸入。錯誤: {e}")
        return None

# 🔹 計算表格
def calculate_price_table(cost, currency, rate):
    """根據成本、幣別和匯率計算加成率及利潤率售價表。"""
    
    cost_twd = cost if currency == "TWD" else cost * rate

    rates = [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.5]
    data = []

    for r in rates:
        markup_price = cost_twd * (1 + r)
        margin_price = cost_twd / (1 - r)
        
        data.append({
            "利潤比例": f"{int(r*100)}%",
            "加成率售價 (TWD)": round(markup_price, 2),
            "利潤率售價 (TWD)": round(margin_price, 2)
        })

    return pd.DataFrame(data)

# --- 💻 Streamlit 介面配置 ---

st.title("💰 商品定價工具")
st.markdown("---")

# 1. 元件區塊：使用 st.columns 來並排顯示
# 嘗試調整為 [1, 1, 1] 確保在窄視窗下排列更平均，因為 450px 已經很窄了
col1, col2, col3 = st.columns([1, 1, 1]) 

with col1:
    cost = st.number_input(
        '成本:',
        min_value=0.0,
        value=1.3,
        step=0.1,
        format="%.2f",
        key='cost_input'
    )

with col2:
    currency = st.selectbox(
        '幣別:',
        options=['美金 USD', '台幣 TWD'],
        index=0,
        key='currency_input'
    )
    currency_code = currency.split(' ')[1]

with col3:
    if 'usd_rate' not in st.session_state:
        st.session_state.usd_rate = 32.0

    rate = st.number_input(
        f'{currency_code}→TWD:',
        value=st.session_state.usd_rate,
        step=0.01,
        format="%.4f",
        disabled=(currency_code == 'TWD'),
        key='rate_input'
    )

st.markdown("---")

# 2. 更新匯率按鈕
if st.button('更新台銀匯率', type="primary", use_container_width=True):
    st.cache_data.clear()
    
    new_rate = get_tw_bank_usd_rate()
    if new_rate:
        st.session_state.usd_rate = new_rate
        st.rerun() 

# 3. 顯示表格
if currency_code == 'USD':
    st.info(f"當前匯率: 1 {currency_code} = **{rate}** TWD")

if cost > 0:
    df_result = calculate_price_table(cost, currency_code, rate)
    
    st.header("定價結果 (TWD)")
    st.dataframe(df_result, use_container_width=True)
else:
    st.warning("請輸入有效的成本金額。")
