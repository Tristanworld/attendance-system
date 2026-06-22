import streamlit as st
import sqlite3
import pandas as pd
from datetime import date
import requests

# ---------------------------------
# 1. Telegram Configuration
# ---------------------------------
# Pre-filled with your active system credentials
TELEGRAM_BOT_TOKEN = "8868090203:AAHXDei1a1ebGst8_dJ8BL9qVmrds3YhLFQ"
TELEGRAM_CHAT_ID = "7071409922"

def send_batch_absent_notification(absent_names):
    """Sends a single 100% free summary push notification for all absent students to stop app lag"""
    if "PASTE_" in TELEGRAM_BOT_TOKEN or not TELEGRAM_BOT_TOKEN:
        st.warning(f"⚠️ Telegram Bot is not configured yet. (Simulated: {', '.join(absent_names)} are absent)")
        return False
        
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        
        # Formats the absent students beautifully into a bulleted list
        formatted_names = "\n".join([f"•  {name}" for name in absent_names])
        
        message_text = (
            f"🔔 *EduTrack Pro Daily Attendance Alert*\n\n"
            f"Date: *{date.today()}*\n\n"
            f"The following student(s) were marked *ABSENT* today:\n"
            f"{formatted_names}\n\n"
            f"Please contact the school front office for any clarifications."
        )
        
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
        # High Performance UI: One-click status reset for the whole classroom
        st.markdown("### ⚡ Quick Select")
        default_status = st.radio(
            "Set baseline status for all students to save tapping time:", 
            ["Present", "Absent", "Late"], 
            horizontal=True
        )
        
        st.divider()
        
        with st.form("attendance_form"):
            st.write(f"Marking attendance for: **{today}**")
            
            attendance_data = {}
            for index, row in students_df.iterrows():
                col1, col2 = st.columns([3, 2])
                with col1:
                    st.write(f"👤 **{row['name']}** (Grade: {row['grade']})")
                with col2:
                    # Dynamically updates its default position based on the master toggle above
                    status_index = ["Present", "Absent", "Late"].index(default_status)
                    status = st.radio("Status", ["Present", "Absent", "Late"], 
                                      index=status_index,
                                      key=f"status_{row['id']}", horizontal=True)
                    attendance_data[row['id']] = {"status": status, "name": row['name']}
            
            submit = st.form_submit_button("Save Attendance & Notify Parents")
            
            if submit:
                absent_list = []
                
                # Write to local SQLite database instantly
                for student_id, info in attendance_data.items():
                    c.execute("INSERT INTO attendance (date, student_id, status) VALUES (?, ?, ?)",
                              (str(today), student_id, info["status"]))
                    
                    if info["status"] == "Absent":
                        absent_list.append(info["name"])
                            
                conn.commit()
                
                # Fire off notifications instantly without script loop lags
                alerts_sent = 0
                if absent_list:
                    success = send_batch_absent_notification(absent_list)
                    if success:
                        alerts_sent = len(absent_list)
                            
                st.success(f"✅ Attendance saved! {alerts_sent} student alert(s) processed instantly via Telegram.")

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
