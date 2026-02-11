def main():
    st.set_page_config(page_title="Etymon Decoder", page_icon="🧪", layout="centered")
    inject_mobile_ui()

    # 1. 定義導覽選項（統一變數，避免打字錯誤）
    nav_options = ["🔍 探索", "📄 講義", "💖 支持"]

    # 2. 初始化 Session State 且「容錯檢查」
    # 如果 mobile_nav 不存在，或者它的值不在當前的選項裡，就重設為第一個選項
    if 'mobile_nav' not in st.session_state or st.session_state.mobile_nav not in nav_options:
        st.session_state.mobile_nav = nav_options[0]

    # 3. 安全地取得 Index
    try:
        current_idx = nav_options.index(st.session_state.mobile_nav)
    except ValueError:
        current_idx = 0

    # 4. 渲染 Radio 導覽列
    nav = st.radio(
        "選單", 
        nav_options, 
        index=current_idx,
        horizontal=True, 
        label_visibility="collapsed"
    )
    
    # 如果點擊了新的導覽，更新 Session State 並 rerun
    if nav != st.session_state.mobile_nav:
        st.session_state.mobile_nav = nav
        st.rerun()

    st.markdown("---")

    # 載入資料庫
    df = load_db()
    if df.empty:
        st.warning("資料庫目前是空的，請檢查 Google Sheets 連線。")
        return

    # 5. 根據當前選擇切換頁面
    if st.session_state.mobile_nav == "🔍 探索":
        home_page(df)
    elif st.session_state.mobile_nav == "📄 講義":
        handout_page()
    elif st.session_state.mobile_nav == "💖 支持":
        # ... 支持頁面內容 ...
        pass
