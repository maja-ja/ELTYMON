import streamlit as st
import pandas as pd
import datetime
import time
import json
import base64
import google.generativeai as genai
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components
import markdown
import uuid
import re
import random
import time

# ==========================================
# 核心工具：多 Key 輪詢引擎
# ==========================================
def run_gemini_robust(prompt, image=None, model_name='gemini-1.5-flash'):
    """
    智慧型 AI 呼叫函式：
    1. 自動讀取 secrets 中的 GEMINI_KEYS 列表。
    2. 隨機打亂順序 (負載平衡)。
    3. 遇到錯誤自動切換下一個 Key (故障轉移)。
    """
    # 1. 取得 Keys
    keys = st.secrets.get("GEMINI_KEYS")
    
    # 相容性處理：如果使用者還沒改 secrets，嘗試讀取舊的單一 Key
    if not keys:
        single_key = st.secrets.get("GEMINI_API_KEY")
        if single_key:
            keys = [single_key]
        else:
            st.error("❌ 未設定 GEMINI_KEYS 或 GEMINI_API_KEY")
            return None
            
    # 確保 keys 是列表
    if isinstance(keys, str):
        keys = [keys]

    # 2. 隨機打亂 (避免每次都操勞第一支 Key)
    # 複製一份以免影響原始順序，然後打亂
    shuffled_keys = keys.copy()
    random.shuffle(shuffled_keys)

    # 3. 輪詢嘗試 (Retry Loop)
    last_error = None
    
    for i, api_key in enumerate(shuffled_keys):
        try:
            # 設定當前使用的 Key
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            
            # 準備內容 (文字 + 圖片)
            content_parts = [prompt]
            if image:
                content_parts.append(image)
                
            # 發送請求
            response = model.generate_content(content_parts)
            
            # 成功則直接回傳
            if response.text:
                return response.text
                
        except Exception as e:
            # 捕捉錯誤，記錄並嘗試下一個
            last_error = e
            print(f"⚠️ Key #{i+1} failed: {e}. Switching to next key...")
            time.sleep(1) # 稍微冷卻一下，避免瞬間發送太快
            continue # 繼續迴圈，試下一個 Key

    # 4. 如果 6 支 Key 全掛了
    st.error(f"❌ 所有 AI Keys 皆無法回應。最後一次錯誤: {last_error}")
    return None
# ==========================================
# 1. 核心配置與 CSS
# ==========================================
st.set_page_config(page_title="備考戰情室", page_icon="🛡️", layout="wide")

def inject_custom_css():
    st.markdown("""
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&family=JetBrains+Mono:wght@400&display=swap');
            
            :root { --primary: #FF4B4B; --bg-secondary: #f0f2f6; }
            
            /* 全局字體 */
            html, body, [class*="css"] { font-family: 'Noto Sans TC', sans-serif; }
            .stCodeBlock { font-family: 'JetBrains Mono', monospace; }

            /* 儀表板卡片 */
            .metric-card {
                background: white; border-radius: 12px; padding: 20px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center;
                border-top: 5px solid var(--primary); margin-bottom: 20px;
            }
            .metric-value { font-size: 2.5rem; font-weight: 800; color: #333; }
            .metric-label { font-size: 1rem; color: #666; font-weight: 500; }

            /* 題目卡片 */
            .quiz-card {
                background: #ffffff; border: 1px solid #e0e0e0; border-radius: 10px;
                padding: 25px; margin-bottom: 20px;
            }
            .question-text { font-size: 1.2rem; font-weight: 600; color: #1a1a1a; margin-bottom: 15px; }
            
            /* PDF 預覽區 */
            .pdf-preview { border: 2px dashed #ccc; padding: 20px; background: #fafafa; border-radius: 10px; }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 資料庫與 AI 工具函式
# ==========================================

def get_db_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def run_gemini(prompt, model_name='gemini-2.5-flash'):
    """呼叫 Gemini API"""
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key:
        st.error("❌ 未設定 GEMINI_API_KEY")
        return None
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"AI Error: {e}")
        return None

def generate_pdf_html(title, content_md):
    """生成 PDF 下載用的 HTML"""
    html_content = markdown.markdown(content_md, extensions=['tables', 'fenced_code'])
    return f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap" rel="stylesheet">
        <style>
            body {{ font-family: 'Noto Sans TC', sans-serif; padding: 20px; background: #555; }}
            #report {{ background: white; width: 210mm; min-height: 297mm; padding: 20mm; margin: 0 auto; box-shadow: 0 0 10px rgba(0,0,0,0.5); }}
            h1 {{ border-bottom: 3px solid #333; padding-bottom: 10px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            code {{ background: #f4f4f4; padding: 2px 5px; border-radius: 3px; }}
        </style>
    </head>
    <body>
        <div id="report">
            <h1>{title}</h1>
            <p>生成時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
            <hr>
            {html_content}
        </div>
        <script>
            function downloadPDF() {{
                const element = document.getElementById('report');
                html2pdf().from(element).save('{title}.pdf');
            }}
        </script>
        <div style="text-align: center; margin-top: 20px;">
            <button onclick="downloadPDF()" style="padding: 10px 20px; font-size: 16px; cursor: pointer; background: #FF4B4B; color: white; border: none; border-radius: 5px;">📥 下載 PDF</button>
        </div>
    </body>
    </html>
    """

# ==========================================
# 3. 模組：戰情儀表板 (Mission Control)
# ==========================================
def dashboard_page():
    st.title("🛡️ 備考戰情室 (Mission Control)")
    
    # 1. 倒數計時器
    targets = [
        {"name": "生物奧林匹亞初試", "date": "2026-11-01"},
        {"name": "托福考試", "date": "2026-12-15"},
        {"name": "多益考試", "date": "2026-12-15"},
        {"name": "學測", "date": "2027-01-20"},
        {"name": "同等學力", "date": "2026-10-01"}
    ]
    
    cols = st.columns(len(targets))
    for i, target in enumerate(targets):
        t_date = datetime.datetime.strptime(target['date'], "%Y-%m-%d").date()
        today = datetime.date.today()
        days_left = (t_date - today).days
        
        with cols[i]:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-label">{target['name']}</div>
                <div class="metric-value" style="color: {'#d9534f' if days_left < 30 else '#333'}">
                    {days_left} <span style="font-size:1rem">天</span>
                </div>
                <div class="metric-label">{target['date']}</div>
            </div>
            """, unsafe_allow_html=True)

    # 2. 今日任務 (Google Sheets 連動)
    st.subheader("📅 今日任務清單")
    conn = get_db_connection()
    try:
        tasks_df = conn.read(worksheet="tasks", ttl=0)
        
        # 🔥 修正關鍵：強制將 status 欄位轉換為布林值 (Boolean)
        # 1. fillna(False): 把空值填補為 False
        # 2. astype(bool): 強制轉型為 True/False
        if 'status' in tasks_df.columns:
            tasks_df['status'] = tasks_df['status'].fillna(False).astype(bool)
        else:
            # 如果欄位不存在（新表），手動建立
            tasks_df['status'] = False

        edited_df = st.data_editor(
            tasks_df, 
            num_rows="dynamic", 
            use_container_width=True,
            column_config={
                "status": st.column_config.CheckboxColumn(
                    "完成", 
                    help="勾選代表完成",
                    default=False  # 設定預設值
                ),
                "priority": st.column_config.SelectboxColumn(
                    "優先級", 
                    options=["High", "Medium", "Low"],
                    required=True
                )
            }
        )
        
        if st.button("💾 更新任務狀態"):
            conn.update(worksheet="tasks", data=edited_df)
            st.success("任務已更新！")
            time.sleep(1) # 稍微停頓讓使用者看到成功訊息
            st.rerun()
            
    except Exception as e:
        st.warning("⚠️ 無法讀取任務表，請確認 Google Sheets 設定。")
        st.error(f"錯誤詳情: {e}")

# ==========================================
# 4. 模組：AI 命題工廠 (Exam Factory)
# ==========================================

def exam_factory_page():
    st.title("🏭 AI 命題工廠 (Exam Factory)")
    st.caption("全方位備考引擎：支援生奧、托福、學測與同等學歷全科生成。")
    
    # ==========================================
    # 1. 定義科目地圖 (Subject Mapping)
    # ==========================================
    SUBJECT_MAP = {
        "🧬 生物奧林匹亞 (IBO/Campbell)": [
            "Unit 1: 生命化學 (Chemistry of Life)",
            "Unit 2: 細胞學 (The Cell)",
            "Unit 3: 遺傳學 (Genetics)",
            "Unit 4: 演化機制 (Mechanisms of Evolution)",
            "Unit 5: 生物多樣性 (Evolutionary History)",
            "Unit 6: 植物型態與生理 (Plant Form & Function)",
            "Unit 7: 動物型態與生理 (Animal Form & Function)",
            "Unit 8: 生態學 (Ecology)",
            "生奧複試：實驗設計與圖表分析 (Practical & Data)"
        ],
        "🌍 托福 (TOEFL iBT)": [
            "Reading: 學術文章閱讀 (Academic Reading)",
            "Listening: 校園對話 (Conversation)",
            "Listening: 學術講座 (Lecture)",
            "Speaking: 獨立口說 (Task 1)",
            "Writing: 學術討論寫作 (Academic Discussion)",
            "Vocabulary: 學術高頻單字 (C1 Level)"
        ],
        "🎓 學測/同等學歷 (GSAT/Equivalency)": [
            "國文: 綜合閱讀理解 (Reading Comprehension)",
            "國文: 古文 15 篇與國學常識",
            "英文: 綜合測驗 (Cloze & Vocabulary)",
            "英文: 閱讀測驗 (Reading)",
            "數學: 數 A (高難度/理工)",
            "數學: 數 B (基礎/人文)",
            "自然: 物理 (Physics)",
            "自然: 化學 (Chemistry)",
            "自然: 生物 (Biology - 高中範圍)",
            "自然: 地科 (Earth Science)",
            "社會: 歷史 (History)",
            "社會: 地理 (Geography)",
            "社會: 公民 (Civics)"
        ]
    }

    col1, col2 = st.columns([1.2, 0.8]) # 左側參數區稍微寬一點
    
    with col1:
        st.subheader("1. 設定出題參數")
        
        # --- 參數設定 ---
        c_param1, c_param2 = st.columns(2)
        with c_param1:
            main_category = st.selectbox("考試類別", list(SUBJECT_MAP.keys()))
            difficulty = st.select_slider("難度", options=["基礎", "進階", "地獄"], value="進階")
        with c_param2:
            sub_category = st.selectbox("測驗細項", SUBJECT_MAP[main_category])
            q_count = st.slider("題數", 1, 10, 3)
        
        st.divider()
        
        # --- 多模態輸入區 (左右分割) ---
        st.markdown("#### 📚 素材輸入 (RAG-lite)")
        
        input_c1, input_c2 = st.columns([1, 1]) # 50/50 分割
        
        with input_c1:
            st.markdown("**📝 文字筆記/文章**")
            context_text = st.text_area("文字輸入", height=200, placeholder="貼上筆記、文章段落或錯題觀念...", label_visibility="collapsed")
            
        with input_c2:
            st.markdown("**📸 圖片素材 (支援多張)**")
            uploaded_files = st.file_uploader("上傳圖片", type=["jpg", "jpeg", "png"], accept_multiple_files=True, label_visibility="collapsed")
            
            # 處理圖片列表
            image_payloads = []
            if uploaded_files:
                # 顯示縮圖預覽 (限制高度以免佔太多空間)
                st.image(uploaded_files, width=100, caption=[f"Img {i+1}" for i in range(len(uploaded_files))])
                # 轉換為 PIL Image 物件
                for f in uploaded_files:
                    image_payloads.append(Image.open(f))
                st.caption(f"已載入 {len(image_payloads)} 張圖片")

        generate_btn = st.button("🚀 啟動 AI 出題引擎", type="primary", use_container_width=True)

    # ==========================================
    # 2. 生成邏輯
    # ==========================================
    if generate_btn:
        with st.spinner(f"🤖 正在分析 {len(image_payloads)} 張圖片與文字，切換至【{sub_category}】模式..."):
            
            # --- 設定 AI 人設 (System Role) ---
            system_role = ""
            if "生物奧林匹亞" in main_category:
                system_role = "你現在是 IBO 生物奧林匹亞教練。請針對 Campbell Biology 範圍出題。若有圖片，請綜合分析多張圖表的關聯性或實驗數據。"
            elif "托福" in main_category:
                system_role = "你現在是 ETS 托福出題官。請使用標準學術英語。若有圖片，請將其視為學術講座的投影片。"
            elif "學測" in main_category:
                system_role = "你現在是學測命題老師。請依素養導向出題。若有多張圖片，請設計圖表比較或綜合判讀題。"

            # --- 題目格式定義 ---
            format_requirement = """
            請回傳 JSON Array，格式如下：
            [
                {
                    "q": "題目敘述",
                    "options": ["A. 選項1", "B. 選項2", "C. 選項3", "D. 選項4"],
                    "answer": "A",
                    "explanation": "詳細解析 (請引用圖片內容佐證)"
                }
            ]
            """
            if "Speaking" in sub_category or "Writing" in sub_category:
                format_requirement = """
                請回傳 JSON Array: [{"q": "題目", "options": ["N/A"], "answer": "回答重點", "explanation": "高分技巧"}]
                """

            # --- 組合 Prompt ---
            context_prompt = ""
            if context_text:
                context_prompt += f"參考文字內容：\n{context_text}\n"
            if image_payloads:
                context_prompt += f"參考圖片內容：共 {len(image_payloads)} 張。請仔細分析所有圖片中的資訊。\n"
            
            full_prompt = f"""
            {system_role}
            任務：針對「{sub_category}」出 {q_count} 題 {difficulty} 難度的題目。
            {context_prompt}
            
            【格式嚴格要求】
            1. 直接回傳 JSON Array，不要 Markdown。
            2. 確保 JSON 合法。
            {format_requirement}
            """
            
            # --- 呼叫 AI (使用新的多圖版函式) ---
            raw_res = run_gemini_robust(full_prompt, images=image_payloads)
            
            if raw_res:
                try:
                    clean_json = re.sub(r"```json|```", "", raw_res).strip()
                    questions = json.loads(clean_json)
                    
                    st.session_state.generated_questions = questions
                    st.session_state.gen_subject = main_category.split(" ")[1]
                    st.session_state.gen_topic = f"{sub_category} ({len(image_payloads)} imgs)" if image_payloads else sub_category
                    
                    st.success(f"✅ 成功生成 {len(questions)} 題！")
                except Exception as e:
                    st.error("生成失敗，AI 回傳格式有誤。")
                    with st.expander("錯誤詳情"):
                        st.text(raw_res)


    # ==========================================
    # 3. 預覽與入庫 (Preview & Save)
    # ==========================================
    with col2:
        st.subheader("2. 題目預覽與入庫")
        if "generated_questions" in st.session_state and st.session_state.generated_questions:
            qs = st.session_state.generated_questions
            
            with st.form("save_questions_form"):
                selected_indices = []
                for i, q in enumerate(qs):
                    # 顯示題目卡片
                    st.markdown(f"""
                    <div style="border:1px solid #ddd; padding:10px; border-radius:5px; margin-bottom:10px;">
                        <div style="font-weight:bold; color:#d9534f;">Q{i+1}</div>
                        <div>{q['q']}</div>
                        <div style="font-size:0.9em; color:#666; margin-top:5px;">
                            <span style="background:#eee; padding:2px 5px; border-radius:3px;">Ans: {q['answer']}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if st.checkbox(f"納入題庫", value=True, key=f"sel_{i}"):
                        selected_indices.append(i)
                
                st.caption("勾選滿意的題目後，點擊下方按鈕存入資料庫。")
                save_btn = st.form_submit_button("💾 確認入庫 (Save to Database)", type="primary")
            
            if save_btn:
                conn = get_db_connection()
                try:
                    # 讀取並寫入
                    try: bank_df = conn.read(worksheet="quiz_bank", ttl=0)
                    except: bank_df = pd.DataFrame(columns=['id', 'date', 'subject', 'topic', 'question_json', 'user_answer', 'ai_feedback', 'is_correct', 'review_count'])
                    
                    new_rows = []
                    today_str = datetime.date.today().strftime("%Y-%m-%d")
                    
                    for idx in selected_indices:
                        q = qs[idx]
                        new_rows.append({
                            "id": str(uuid.uuid4())[:8],
                            "date": today_str,
                            "subject": st.session_state.gen_subject,
                            "topic": st.session_state.gen_topic,
                            "question_json": json.dumps(q, ensure_ascii=False),
                            "user_answer": "",
                            "ai_feedback": "",
                            "is_correct": "Pending",
                            "review_count": 0
                        })
                    
                    if new_rows:
                        updated_df = pd.concat([bank_df, pd.DataFrame(new_rows)], ignore_index=True)
                        conn.update(worksheet="quiz_bank", data=updated_df)
                        st.toast(f"🎉 已存入 {len(new_rows)} 題！請前往「競技場」刷題。", icon="✅")
                        del st.session_state.generated_questions
                        time.sleep(1)
                        st.rerun()
                except Exception as e:
                    st.error(f"存檔失敗: {e}")
        else:
            st.info("👈 請先在左側選擇科目並生成題目")
# ==========================================
# 5. 模組：競技場 (The Arena)
# ==========================================
def arena_page():
    st.title("⚔️ 競技場 (The Arena)")
    
    # --- 初始化 Session State ---
    if "arena_q_index" not in st.session_state:
        st.session_state.arena_q_index = 0
    if "arena_show_answer" not in st.session_state:
        st.session_state.arena_show_answer = False

    conn = get_db_connection()
    try:
        bank_df = conn.read(worksheet="quiz_bank", ttl=0)
        # 篩選 Pending 的題目
        pending_df = bank_df[bank_df['is_correct'] == "Pending"].reset_index(drop=True)
    except:
        st.warning("題庫讀取失敗或為空。")
        return

    if pending_df.empty:
        st.success("🎉 恭喜！今日題庫已全數清空！請前往「每日戰報」生成總結。")
        return

    # 取得當前題目
    current_idx = st.session_state.arena_q_index
    # 防止 index 超出範圍 (例如剛好做完最後一題)
    if current_idx >= len(pending_df):
        st.session_state.arena_q_index = 0
        st.rerun()

    row = pending_df.iloc[current_idx]
    q_data = json.loads(row['question_json'])
    
    # --- 題目卡片 UI ---
    st.markdown(f"""
    <div class="quiz-card">
        <div style="display:flex; justify-content:space-between; color:#888; font-size:0.8rem; margin-bottom:10px;">
            <span>{row['subject']}</span>
            <span>Topic: {row['topic']}</span>
        </div>
        <div class="question-text" style="font-size:1.3rem; font-weight:bold; color:#222;">
            {q_data['q']}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- 作答區 ---
    # 使用 form 避免每次點擊 radio 就刷新
    with st.form(key=f"ans_form_{row['id']}"):
        user_choice = st.radio("你的選擇：", q_data['options'], index=None)
        
        # 按鈕邏輯：如果還沒看答案，顯示「提交並翻牌」；如果看過了，顯示「下一題」
        submit_label = "提交答案並查看詳解 (Flip)" 
        submitted = st.form_submit_button(submit_label, type="primary")

    if submitted:
        if not user_choice:
            st.warning("請先選擇一個答案！")
        else:
            st.session_state.arena_show_answer = True
            st.session_state.user_selected = user_choice

    # --- 詳解與結算區 (翻牌後顯示) ---
    if st.session_state.arena_show_answer:
        user_ans_char = st.session_state.user_selected.split(".")[0].strip()
        correct_ans_char = q_data['answer'].strip()
        is_correct = (user_ans_char == correct_ans_char)

        # 1. 顯示結果
        if is_correct:
            st.success(f"✅ 正確！答案是 {correct_ans_char}")
        else:
            st.error(f"❌ 錯誤。正確答案是 {correct_ans_char}，你選了 {user_ans_char}")

        # 2. 顯示詳解 (Expander)
        with st.expander("📖 查看完整解析 (Explanation)", expanded=True):
            st.markdown(f"**{q_data['explanation']}**")

        # 3. 結算按鈕
        if st.button("記錄結果並前往下一題 ➡️"):
            # 更新資料庫
            # 為了確保資料一致性，我們重新讀取並更新特定 ID
            # (這裡簡化直接用 row index 更新，實際建議用 ID 查找)
            bank_df.loc[bank_df['id'] == row['id'], 'user_answer'] = user_ans_char
            bank_df.loc[bank_df['id'] == row['id'], 'is_correct'] = "TRUE" if is_correct else "FALSE"
            bank_df.loc[bank_df['id'] == row['id'], 'date'] = datetime.date.today().strftime("%Y-%m-%d") # 更新為作答日期
            
            conn.update(worksheet="quiz_bank", data=bank_df)
            
            # 重置狀態
            st.session_state.arena_show_answer = False
            # 因為 pending_df 會變少，index 其實不用加 1，保持 0 就會自動補上下一個
            # 但為了保險，我們直接 rerun 讓 pandas 重新抓取 pending
            st.rerun()

# ==========================================
# 6. 模組：每日戰報 (Daily Report)
# ==========================================
def report_page():
    st.title("📄 每日戰報 (Daily Debrief)")
    st.caption("將今日的戰鬥數據轉化為永久的知識資產。")

    today_str = datetime.date.today().strftime("%Y-%m-%d")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown(f"### 📅 日期：{today_str}")
        if st.button("⚡ 生成今日戰報", type="primary", use_container_width=True):
            with st.spinner("正在調閱作答紀錄並進行 AI 分析..."):
                conn = get_db_connection()
                try:
                    bank_df = conn.read(worksheet="quiz_bank", ttl=0)
                    # 篩選今日已完成的題目
                    today_df = bank_df[
                        (bank_df['date'] == today_str) & 
                        (bank_df['is_correct'].isin(["TRUE", "FALSE"]))
                    ]
                except:
                    st.error("資料庫讀取失敗")
                    return

                if today_df.empty:
                    st.warning("⚠️ 今日尚未有完成的刷題紀錄，無法生成戰報。請先去「競技場」戰鬥！")
                    return

                # --- 數據統計 ---
                total_q = len(today_df)
                correct_q = len(today_df[today_df['is_correct'] == "TRUE"])
                accuracy = round((correct_q / total_q) * 100, 1)
                
                # --- 錯題整理 ---
                wrong_df = today_df[today_df['is_correct'] == "FALSE"]
                wrong_content_for_ai = ""
                wrong_md_list = ""
                
                for i, row in wrong_df.iterrows():
                    q = json.loads(row['question_json'])
                    # 給 AI 看的簡化版
                    wrong_content_for_ai += f"- 主題: {row['topic']} | 題目: {q['q']} | 誤答: {row['user_answer']} | 正解: {q['answer']}\n"
                    # PDF 用的詳細版
                    wrong_md_list += f"""
---
#### ❌ Q: {q['q']}
- **主題**: {row['subject']} / {row['topic']}
- **你的答案**: `{row['user_answer']}` | **正確答案**: `{q['answer']}`
- **💡 詳解**: {q['explanation']}
"""

                # --- AI 教練分析 ---
                if not wrong_df.empty:
                    prompt = f"""
                    我是生奧/托福考生。今日做了 {total_q} 題，正確率 {accuracy}%。
                    以下是我的錯題列表：
                    {wrong_content_for_ai}
                    
                    請給出一段「戰報總結」：
                    1. **弱點診斷**：我哪個觀念最不熟？(例如：遺傳學計算、植物生理...)
                    2. **行動建議**：明天我該優先複習什麼？
                    3. **心態喊話**：簡短有力的鼓勵。
                    請用 Markdown 格式，語氣專業且激勵人心。
                    """
                    ai_analysis = run_gemini(prompt)
                else:
                    ai_analysis = "🎉 **完美全對！** 今日表現無懈可擊。建議明天挑戰更高難度（Hell Mode）題目，保持手感！"

                # --- 生成 HTML 報告 ---
                report_html = f"""
                <div style="font-family: 'Noto Sans TC', sans-serif; color: #333;">
                    <h1 style="text-align:center; color:#FF4B4B; border-bottom: 2px solid #FF4B4B;">🛡️ 每日備考戰報</h1>
                    <p style="text-align:right; color:#666;">生成時間: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
                    
                    <div style="background:#f4f4f4; padding:15px; border-radius:10px; margin:20px 0; display:flex; justify-content:space-around;">
                        <div style="text-align:center;"><h2>{total_q}</h2><small>總題數</small></div>
                        <div style="text-align:center; color:{'green' if accuracy >= 80 else 'red'};"><h2>{accuracy}%</h2><small>正確率</small></div>
                        <div style="text-align:center;"><h2>{len(wrong_df)}</h2><small>錯題數</small></div>
                    </div>

                    <h2>🧠 AI 教練診斷</h2>
                    <div style="background:#e8f4ff; padding:15px; border-left:5px solid #2196F3; border-radius:5px;">
                        {markdown.markdown(ai_analysis)}
                    </div>

                    <h2>📝 錯題深度訂正 (Error Log)</h2>
                    {markdown.markdown(wrong_md_list) if wrong_md_list else "<p>今日無錯題，Excellent!</p>"}
                </div>
                """
                
                # 存入 Session State 以便預覽
                st.session_state.report_html = report_html
                st.session_state.report_title = f"Daily_Report_{today_str}"

    with col2:
        if "report_html" in st.session_state:
            st.subheader("📄 報告預覽")
            # 顯示預覽
            components.html(st.session_state.report_html, height=600, scrolling=True)
            
            # 下載按鈕邏輯 (Client-side PDF generation)
            # 我們將 HTML 包裝進一個完整的 HTML 檔案，並包含 html2pdf.js
            full_html = f"""
            <html>
            <head>
                <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
                <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap" rel="stylesheet">
            </head>
            <body>
                <div id="content">
                    {st.session_state.report_html}
                </div>
                <script>
                    window.onload = function() {{
                        const element = document.getElementById('content');
                        const opt = {{
                            margin: 10,
                            filename: '{st.session_state.report_title}.pdf',
                            image: {{ type: 'jpeg', quality: 0.98 }},
                            html2canvas: {{ scale: 2 }},
                            jsPDF: {{ unit: 'mm', format: 'a4', orientation: 'portrait' }}
                        }};
                        // 自動下載或提供按鈕
                        // 這裡我們不自動下載，而是讓 Streamlit 的 components 觸發
                    }};
                    function download() {{
                        const element = document.getElementById('content');
                        html2pdf().from(element).save('{st.session_state.report_title}.pdf');
                    }}
                </script>
                <div style="text-align:center; margin-top:20px;">
                    <button onclick="download()" style="background:#FF4B4B; color:white; border:none; padding:10px 20px; border-radius:5px; cursor:pointer; font-size:16px; font-weight:bold;">
                        📥 點擊下載 PDF 檔案
                    </button>
                </div>
            </body>
            </html>
            """
            components.html(full_html, height=100)

# ==========================================
# 7. 主程式導航
# ==========================================
def main():
    inject_custom_css()
    
    with st.sidebar:
        st.title("🛡️ 備考戰情室")
        st.markdown("---")
        page = st.radio("導航", ["戰情儀表板", "AI 命題工廠", "競技場 (刷題)", "每日戰報 PDF"])
        
        st.markdown("---")
        st.caption("v5.0 War Room Edition")

    if page == "戰情儀表板":
        dashboard_page()
    elif page == "AI 命題工廠":
        exam_factory_page()
    elif page == "競技場 (刷題)":
        arena_page()
    elif page == "每日戰報 PDF":
        report_page()

if __name__ == "__main__":
    main()
