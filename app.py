import streamlit as st
import sqlite3
import pandas as pd
from datetime import date
import requests

# ---------------------------------
# 1. Telegram Configuration
# ---------------------------------
# Paste the credentials you copied from Telegram here
TELEGRAM_BOT_TOKEN = "8868999203:AAHXOeiIa1eb6tT8_4J88L9qVwrdi3YhLFQ"
TELEGRAM_CHAT_ID = "7071409922"

def send_absent_notification(student_name):
    """Sends a 100% free instant push notification via Telegram Bot"""
    if "PASTE_" in TELEGRAM_BOT_TOKEN or not TELEGRAM_BOT_TOKEN:
        st.warning(f"⚠️ Telegram Bot is not configured yet. (Simulated: {student_name} is absent)")
        return False
        
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        message_text = f"🔔 *EduTrack Pro Alert*\n\nNotice: **{student_name}** was marked **ABSENT** today ({date.today()}).\n\nPlease contact the school front office if this is an error."
        
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message_text,
            "parse_mode": "Markdown"
        }
        
        response = requests.post(url, json=payload)
        return response.status_code == 200
    except Exception as e:
        st.error(f"❌ Notification failed: {e}")
        return False

# ---------------------------------
# 2. Database Setup
# ---------------------------------
conn = sqlite3.connect('school_attendance.db', check_same_thread=False)
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS students 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, grade TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS attendance 
             (date TEXT, student_id INTEGER, status TEXT, 
             UNIQUE(date, student_id) ON CONFLICT REPLACE)''')
conn.commit()

# ---------------------------------
# 3. App Configuration & UI
# ---------------------------------
st.set_page_config(page_title="EduTrack Pro", layout="wide")
st.title("📋 EduTrack Pro: Local Attendance System")

tab1, tab2, tab3 = st.tabs(["Mark Attendance", "View Reports", "Manage Students"])

# ---------------------------------
# 4. Mark Attendance Tab
# ---------------------------------
with tab1:
    st.header("Daily Attendance")
    today = st.date_input("Select Date", date.today())
    
    students_df = pd.read_sql_query("SELECT * FROM students", conn)
    
    if students_df.empty:
        st.warning("No students in the system. Add them in 'Manage Students' first.")
    else:
        with st.form("attendance_form"):
            st.write(f"Marking attendance for: **{today}**")
            
            attendance_data = {}
            for index, row in students_df.iterrows():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{row['name']}** (Grade: {row['grade']})")
                with col2:
                    status = st.radio("Status", ["Present", "Absent", "Late"], 
                                      key=f"status_{row['id']}", horizontal=True)
                    attendance_data[row['id']] = {"status": status, "name": row['name']}
            
            submit = st.form_submit_button("Save Attendance & Notify Parents")
            
            if submit:
                alerts_sent = 0
                for student_id, info in attendance_data.items():
                    c.execute("INSERT INTO attendance (date, student_id, status) VALUES (?, ?, ?)",
                              (str(today), student_id, info["status"]))
                    
                    if info["status"] == "Absent":
                        success = send_absent_notification(info["name"])
                        if success:
                            alerts_sent += 1
                            
                conn.commit()
                st.success(f"✅ Attendance saved! {alerts_sent} instant parental alerts sent.")

# ---------------------------------
# 5. View Reports Tab
# ---------------------------------
with tab2:
    st.header("Attendance Reports")
    report_date = st.date_input("View report for date", date.today(), key="report_date")
    
    query = f"""
    SELECT s.name, s.grade, a.status 
    FROM students s
    LEFT JOIN attendance a ON s.id = a.student_id AND a.date = '{report_date}'
    """
    report_df = pd.read_sql_query(query, conn)
    
    if report_df.empty or report_df['status'].isna().all():
        st.info("No attendance records found for this date.")
    else:
        col1, col2, col3 = st.columns(3)
        col1.metric("Present", len(report_df[report_df['status'] == 'Present']))
        col2.metric("Absent", len(report_df[report_df['status'] == 'Absent']))
        col3.metric("Late", len(report_df[report_df['status'] == 'Late']))
        st.dataframe(report_df, use_container_width=True)

# ---------------------------------
# 6. Manage Students Tab
# ---------------------------------
with tab3:
    st.header("Add New Student")
    with st.form("add_student"):
        new_name = st.text_input("Student Full Name")
        new_grade = st.selectbox("Class / Grade Level", ["Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5"])
        add_btn = st.form_submit_button("Add Student")
        
        if add_btn and new_name:
            c.execute("INSERT INTO students (name, grade) VALUES (?, ?)", (new_name, new_grade))
            conn.commit()
            st.success(f"Added {new_name} to roster.")
            st.rerun()
            
    st.divider()
    st.header("Current Roster")
    current_students = pd.read_sql_query("SELECT id, name, grade FROM students", conn)
    st.dataframe(current_students, hide_index=True, use_container_width=True)
