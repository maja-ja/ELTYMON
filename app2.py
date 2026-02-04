def show_encyclopedia_card(row):
    # --- 1. 原有的渲染邏輯 (保持不變) ---
    r_word = str(row.get('word', '未命名主題'))
    r_roots = fix_content(row.get('roots', "")).replace('$', '$$')
    r_phonetic = fix_content(row.get('phonetic', "")) 
    r_breakdown = fix_content(row.get('breakdown', ""))
    r_def = fix_content(row.get('definition', ""))
    r_meaning = str(row.get('meaning', ""))
    r_hook = fix_content(row.get('memory_hook', ""))
    r_vibe = fix_content(row.get('native_vibe', ""))
    r_trans = str(row.get('translation', ""))

    st.markdown(f"<div class='hero-word'>{r_word}</div>", unsafe_allow_html=True)
    
    if r_phonetic and r_phonetic != "無":
        st.markdown(f"<div style='color: #E0E0E0; font-size: 0.95rem; margin-bottom: 20px;'>{r_phonetic}</div>", unsafe_allow_html=True)

    col_a, col_b = st.columns([1, 4])
    with col_a:
        speak(r_word, key_suffix="card_main")
    with col_b:
        st.markdown(f"#### 🧬 邏輯拆解\n{r_breakdown}")

    st.write("---")
    c1, c2 = st.columns(2)
    with c1:
        st.info("### 🎯 定義與解釋")
        st.markdown(r_def) 
        st.markdown(f"**📝 應用案例：** \n{fix_content(row.get('example', ''))}")
    with c2:
        st.success("### 💡 核心原理")
        st.markdown(r_roots)
        st.write(f"**🔍 本質意義：** {r_meaning}")
        st.markdown(f"**🪝 記憶鉤子：** \n{r_hook}")

    if r_vibe:
        st.markdown(f"<div class='vibe-box'><h4>🌊 專家視角</h4>{r_vibe}</div>", unsafe_allow_html=True)

    with st.expander("🔍 深度百科"):
        sub_c1, sub_c2 = st.columns(2)
        with sub_c1:
            st.markdown(f"**⚖️ 相似對比：** \n{fix_content(row.get('synonym_nuance', '無'))}")
        with sub_c2:
            st.markdown(f"**⚠️ 使用注意：** \n{fix_content(row.get('usage_warning', '無'))}")

    # --- 2. 新增：一鍵寫入回報資料庫邏輯 ---
    st.write("---")
    if st.button(f"🚩 回報「{r_word}」解析有誤", type="secondary", use_container_width=True):
        try:
            # 指定回饋表單的網址
            FEEDBACK_URL = "https://docs.google.com/spreadsheets/d/1NNfKPadacJ6SDDLw9c23fmjq-26wGEeinTbWcg7-gFg/edit?gid=0#gid=0"
            
            # 建立與回饋表單的連線
            conn_feedback = st.connection("gsheets", type=GSheetsConnection)
            
            # 準備要寫入的一列資料 (包含 20 個原欄位 + term 欄位)
            # 我們將 term 設為 1 (代表待修理)
            report_data = row.copy()
            report_data['term'] = 1
            
            # 將 Dict 轉為 DataFrame 以便寫入
            report_df = pd.DataFrame([report_data])
            
            # 讀取現有回饋資料並合併 (Append 邏輯)
            existing_feedback = conn_feedback.read(spreadsheet=FEEDBACK_URL, ttl=0)
            new_feedback_df = pd.concat([existing_feedback, report_df], ignore_index=True)
            
            # 執行寫入
            conn_feedback.update(spreadsheet=FEEDBACK_URL, data=new_feedback_df)
            
            st.success(f"✅ 已成功將「{r_word}」標記為待修理並寫入回報庫！")
            st.balloons()
            
        except Exception as e:
            st.error(f"❌ 回報失敗，請確認資料庫權限：{e}")