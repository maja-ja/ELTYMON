import streamlit as st
from datetime import datetime
import pandas as pd

# 1. 倒數計時器
def countdown(event_name, event_date):
    remaining = (event_date - datetime.now()).days
    st.metric(label=event_name, value=f"{remaining} Days")

# 2. 首頁佈局
st.title("🛡️ 全科戰神：戰略指揮中心")

# 頂部：大考倒數 (橫向排列)
col1, col2, col3, col4 = st.columns(4)
with col1: countdown("生奧初試", datetime(2025, 1, 15))
with col2: countdown("TOEFL", datetime(2024, 11, 20))
with col3: countdown("學測", datetime(2025, 1, 20))
with col4: countdown("同等學歷", datetime(2025, 3, 10))

st.divider()

# 左側：今日時刻表
col_left, col_right = st.columns([1, 2])

with col_left:
    st.subheader("📅 今日課表")
    schedule = {
        "09:00-11:00": "🌿 生奧深度攻堅",
        "11:00-12:30": "🗣️ TOEFL 聽說讀寫",
        "13:30-15:30": "📐 學測數學死磕",
        "15:30-17:00": "🤖 AI 壓力測試",
        "17:00-18:00": "📚 國社邏輯建構"
    }
    for time, task in schedule.items():
        st.info(f"**{time}**: {task}")

with col_right:
    st.subheader("🚀 快速啟動")
    # 這裡可以放一鍵啟動按鈕
    if st.button("進入 AI 測試模式"):
        st.switch_page("pages/1_AI_Tutor.py") # 跳轉到你的測試腳本頁面
    
    # 簡單的進度顯示
    st.write("今日進度總覽")
    st.progress(65) # 根據已完成任務動態變動
    st.write("🔥 連續讀書天數：14 天")
