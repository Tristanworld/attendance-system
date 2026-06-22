import streamlit as st
import sqlite3
import pandas as pd
from datetime import date
from twilio.rest import Client

# ---------------------------------
# 1. Twilio Configuration
# ---------------------------------
# Replace these placeholders with your actual Twilio credentials from your console
TWILIO_ACCOUNT_SID = "ACd2c1c45a5b939d076c1f0b154c8885f1"
TWILIO_AUTH_TOKEN = "f7799384cf227c09b8a1beb9ae5d31d3"
TWILIO_NUMBER = "09078454471"

def send_absent_sms(student_name, parent_phone):
    """Helper function to trigger the Twilio SMS payload safely."""
    # Safety check if credentials are left blank
    if "your_" in TWILIO_ACCOUNT_SID or not TWILIO_ACCOUNT_SID:
        st.warning(f"⚠️ Twilio is not configured. (Simulated SMS to {parent_phone}: {student_name} is absent)")
        return False
        
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=f"EduTrack Alert: {student_name} was marked ABSENT today. Please contact the front office if this is an error.",
            from_=TWILIO_NUMBER,
            to=parent_phone
        )
        return True
    except Exception as e:
        st.error(f"❌ Failed sending SMS to {parent_phone}: {e}")
        return False

# ---------------------------------
# 2. Database Setup
# ---------------------------------
conn = sqlite3.connect('school_attendance.db', check_same_thread=False)
c = conn.cursor()

# Added parent_phone column to the students table schema
c.execute('''CREATE TABLE IF NOT EXISTS students 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, grade TEXT, parent_phone TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS attendance 
             (date TEXT, student_id INTEGER, status TEXT, 
             UNIQUE(date, student_id) ON CONFLICT REPLACE)''')
conn.commit()

# ---------------------------------
# 3. App Configuration & UI
# ---------------------------------
st.set_page_config(page_title="EduTrack Pro - Attendance System", layout="wide")
st.title("📋 EduTrack Pro: Automated Attendance Dashboard")

tab1, tab2, tab3 = st.tabs(["Mark Attendance", "View Reports", "Manage Students"])

# ---------------------------------
# 4. Mark Attendance Tab (With SMS Trigger)
# ---------------------------------
with tab1:
    st.header("Daily Attendance")
    today = st.date_input("Select Date", date.today())
    
    # Fetch all columns including parent_phone
    students_df = pd.read_sql_query("SELECT * FROM students", conn)
    
    if students_df.empty:
        st.warning("No students in the system. Add them in the 'Manage Students' tab first.")
    else:
        with st.form("attendance_form"):
            st.write(f"Marking attendance for: **{today}**")
            
            attendance_data = {}
            for index, row in students_df.iterrows():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{row['name']}** (Grade: {row['grade']}) — *Parent: {row['parent_phone']}*")
                with col2:
                    status = st.radio("Status", ["Present", "Absent", "Late"], 
                                      key=f"status_{row['id']}", horizontal=True)
                    # Store both the status and parent details for processing later
                    attendance_data[row['id']] = {
                        "status": status, 
                        "name": row['name'], 
                        "phone": row['parent_phone']
                    }
            
            submit = st.form_submit_button("Save Attendance & Notify Parents")
            
            if submit:
                absent_alerts_sent = 0
                for student_id, info in attendance_data.items():
                    # 1. Save to the local SQL database
                    c.execute("INSERT INTO attendance (date, student_id, status) VALUES (?, ?, ?)",
                              (str(today), student_id, info["status"]))
                    
                    # 2. If student is absent, trigger the SMS logic
                    if info["status"] == "Absent" and info["phone"]:
                        success = send_absent_sms(info["name"], info["phone"])
                        if success:
                            absent_alerts_sent += 1
                            
                conn.commit()
                st.success(f"✅ Attendance saved successfully! Dispatch complete ({absent_alerts_sent} SMS alerts processed).")

# ---------------------------------
# 5. View Reports Tab
# ---------------------------------
with tab2:
    st.header("Attendance Reports")
    report_date = st.date_input("View report for date", date.today(), key="report_date")
    
    query = f"""
    SELECT s.name, s.grade, s.parent_phone, a.status 
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
# 6. Manage Students Tab (With Phone Input)
# ---------------------------------
with tab3:
    st.header("Add New Student")
    with st.form("add_student"):
        new_name = st.text_input("Student Full Name")
        new_grade = st.selectbox("Class / Grade Level", ["Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5"])
        # Added input field for the phone number
        new_phone = st.text_input("Parent Phone Number", help="Include country code, e.g., +12345678901")
        add_btn = st.form_submit_button("Add Student")
        
        if add_btn and new_name:
            c.execute("INSERT INTO students (name, grade, parent_phone) VALUES (?, ?, ?)", 
                      (new_name, new_grade, new_phone))
            conn.commit()
            st.success(f"Added {new_name} to roster with contact {new_phone}")
            st.rerun()
            
    st.divider()
    st.header("Current Roster")
    current_students = pd.read_sql_query("SELECT id, name, grade, parent_phone FROM students", conn)
    st.dataframe(current_students, hide_index=True, use_container_width=True)
