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

def run_gemini(prompt, model_name='gemini-1.5-flash'):
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
    
    # 1. 倒數計時器 (Hardcoded targets for demo)
    targets = [
        {"name": "生物奧林匹亞初試", "date": "2024-11-04"},
        {"name": "托福考試", "date": "2024-12-15"},
        {"name": "學測", "date": "2025-01-20"},
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
        # 簡單過濾 (實際應用可加日期過濾)
        edited_df = st.data_editor(
            tasks_df, 
            num_rows="dynamic", 
            use_container_width=True,
            column_config={
                "status": st.column_config.CheckboxColumn("完成", help="勾選代表完成"),
                "priority": st.column_config.SelectboxColumn("優先級", options=["High", "Medium", "Low"])
            }
        )
        
        if st.button("💾 更新任務狀態"):
            conn.update(worksheet="tasks", data=edited_df)
            st.success("任務已更新！")
            st.rerun()
            
    except Exception as e:
        st.warning("⚠️ 無法讀取任務表，請確認 Google Sheets 設定。")
        st.error(e)

# ==========================================
# 4. 模組：AI 命題工廠 (Exam Factory)
# ==========================================
def exam_factory_page():
    st.title("🏭 AI 命題工廠")
    
    c1, c2 = st.columns([1, 2])
    
    with c1:
        st.info("設定生成參數")
        subject = st.selectbox("科目", ["生奧 (Campbell)", "托福 (Reading)", "托福 (Listening)", "學測 (自然)", "學測 (英文)"])
        topic = st.text_input("主題/範圍", placeholder="例如：細胞呼吸、光合作用、基因轉錄")
        difficulty = st.select_slider("難度", options=["基礎", "進階", "地獄 (複試等級)"])
        q_count = st.number_input("生成題數", 1, 5, 3)
        
        if st.button("🚀 開始生成題目", type="primary"):
            if not topic:
                st.warning("請輸入主題！")
                return
            
            with st.spinner("🤖 AI 正在閱讀教材並出題中..."):
                # 建構 Prompt
                prompt = f"""
                你現在是{subject}的專業出題老師。請針對「{topic}」這個主題，設計 {q_count} 題 {difficulty} 難度的單選題。
                
                【重要規則】
                1. 請嚴格回傳 JSON 格式列表。
                2. 格式範例：
                [
                    {{
                        "q": "題目敘述...",
                        "options": ["A. 選項1", "B. 選項2", "C. 選項3", "D. 選項4"],
                        "answer": "A",
                        "explanation": "詳解..."
                    }}
                ]
                3. 生奧題目請引用 Campbell 機制；托福請模擬學術文章邏輯。
                """
                
                res = run_gemini(prompt)
                
                try:
                    # 清洗 JSON
                    json_str = res.replace("```json", "").replace("```", "").strip()
                    questions = json.loads(json_str)
                    
                    # 存入 Session State 供預覽
                    st.session_state.generated_questions = questions
                    st.session_state.gen_subject = subject
                    st.session_state.gen_topic = topic
                    
                except Exception as e:
                    st.error("生成格式錯誤，請重試。")
                    st.code(res)

    with c2:
        st.subheader("📝 題目預覽與入庫")
        if "generated_questions" in st.session_state:
            qs = st.session_state.generated_questions
            
            # 轉換為 DataFrame 顯示
            preview_data = []
            for q in qs:
                preview_data.append({
                    "題目": q['q'],
                    "答案": q['answer'],
                    "詳解": q['explanation']
                })
            st.table(pd.DataFrame(preview_data))
            
            if st.button("💾 確認入庫 (存入 Google Sheets)"):
                conn = get_db_connection()
                try:
                    # 讀取現有
                    try:
                        bank_df = conn.read(worksheet="quiz_bank", ttl=0)
                    except:
                        bank_df = pd.DataFrame(columns=['id', 'date', 'subject', 'topic', 'question_json', 'user_answer', 'ai_feedback', 'is_correct', 'review_count'])
                    
                    new_rows = []
                    today_str = datetime.date.today().strftime("%Y-%m-%d")
                    
                    for q in qs:
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
                    
                    updated_df = pd.concat([bank_df, pd.DataFrame(new_rows)], ignore_index=True)
                    conn.update(worksheet="quiz_bank", data=updated_df)
                    st.success(f"成功存入 {len(new_rows)} 題！請至「競技場」刷題。")
                    del st.session_state.generated_questions # 清空
                    
                except Exception as e:
                    st.error(f"存檔失敗: {e}")

# ==========================================
# 5. 模組：競技場 (The Arena)
# ==========================================
def arena_page():
    st.title("⚔️ 競技場 (The Arena)")
    
    conn = get_db_connection()
    try:
        bank_df = conn.read(worksheet="quiz_bank", ttl=0)
    except:
        st.warning("題庫為空，請先去「命題工廠」生成題目。")
        return

    # 篩選未完成的題目
    pending_df = bank_df[bank_df['is_correct'] == "Pending"]
    
    if pending_df.empty:
        st.success("🎉 今日題目已全數刷完！")
        return
    
    st.metric("待刷題數", len(pending_df))
    
    # 取第一題來做
    current_q_row = pending_df.iloc[0]
    q_data = json.loads(current_q_row['question_json'])
    
    st.markdown(f"""
    <div class="quiz-card">
        <div style="color:#666; font-size:0.9rem;">{current_q_row['subject']} | {current_q_row['topic']}</div>
        <div class="question-text">{q_data['q']}</div>
    </div>
    """, unsafe_allow_html=True)
    
    user_choice = st.radio("請選擇答案：", q_data['options'], key=f"q_{current_q_row['id']}")
    
    if st.button("提交答案"):
        # 判斷對錯
        # 假設選項格式為 "A. xxx"，取第一個字元比較
        user_ans_char = user_choice.split(".")[0].strip()
        correct_ans_char = q_data['answer'].strip()
        
        is_correct = (user_ans_char == correct_ans_char)
        
        # 顯示結果
        if is_correct:
            st.success("✅ 正確！")
            st.info(f"詳解：{q_data['explanation']}")
            result_status = "TRUE"
        else:
            st.error(f"❌ 錯誤。正確答案是 {correct_ans_char}")
            st.warning(f"詳解：{q_data['explanation']}")
            result_status = "FALSE"
            
        # 更新資料庫
        # 這裡用簡單的邏輯：找到 ID 更新 (實際操作建議用 index 或更嚴謹的 SQL 邏輯)
        bank_df.loc[bank_df['id'] == current_q_row['id'], 'user_answer'] = user_ans_char
        bank_df.loc[bank_df['id'] == current_q_row['id'], 'is_correct'] = result_status
        
        conn.update(worksheet="quiz_bank", data=bank_df)
        st.button("下一題 (請按兩下以刷新)", on_click=st.rerun)

# ==========================================
# 6. 模組：每日戰報 (Daily Report)
# ==========================================
def report_page():
    st.title("📄 每日戰報生成 (Daily Debrief)")
    
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    st.write(f"生成日期：{today_str}")
    
    if st.button("生成今日 PDF 報告"):
        conn = get_db_connection()
        bank_df = conn.read(worksheet="quiz_bank", ttl=0)
        
        # 篩選今日做的題目
        today_df = bank_df[bank_df['date'] == today_str]
        
        if today_df.empty:
            st.warning("今日尚未有刷題紀錄。")
            return
            
        # 計算統計數據
        total = len(today_df)
        # 修正：確保 is_correct 欄位是字串比較
        correct = len(today_df[today_df['is_correct'].astype(str) == "TRUE"])
        accuracy = int((correct / total) * 100)
        
        # 整理錯題
        wrong_df = today_df[today_df['is_correct'].astype(str) == "FALSE"]
        wrong_md = ""
        for _, row in wrong_df.iterrows():
            q = json.loads(row['question_json'])
            wrong_md += f"""
### ❌ {row['subject']} - {row['topic']}
**題目**: {q['q']}  
**你的答案**: {row['user_answer']} | **正確答案**: {q['answer']}  
**詳解**: {q['explanation']}
---
"""
        
        # 讓 AI 寫總評
        with st.spinner("AI 正在分析你的今日表現..."):
            summary_prompt = f"""
            學生今日刷了 {total} 題，正確率 {accuracy}%。
            錯題主題包含：{', '.join(wrong_df['topic'].unique())}。
            請給出一段 200 字的鼓勵與具體複習建議，語氣要像嚴格但溫暖的教練。
            """
            ai_comment = run_gemini(summary_prompt)
        
        # 組合 Markdown 報告
        report_md = f"""
## 📊 今日戰績總覽
- **日期**: {today_str}
- **總題數**: {total}
- **正確率**: {accuracy}% ({correct}/{total})

## 🤖 AI 教練點評
{ai_comment}

## 📝 錯題深度訂正
{wrong_md if not wrong_df.empty else "🎉 太神了！今日全對！"}

## 📅 明日重點
請參考 Google Sheets 行事曆，繼續保持！
        """
        
        # 顯示並提供下載
        st.markdown(report_md)
        html = generate_pdf_html(f"Study_Report_{today_str}", report_md)
        components.html(html, height=100)

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
