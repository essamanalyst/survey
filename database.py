import sqlite3
import streamlit as st
import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATABASE_DIR = BASE_DIR / "data"
DATABASE_DIR.mkdir(exist_ok=True)  
DATABASE_PATH = str(DATABASE_DIR / "survey_app.db")

def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    
    # Create Users table
    c.execute('''CREATE TABLE IF NOT EXISTS Users
                 (user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password_hash TEXT NOT NULL,
                  role TEXT NOT NULL,
                  assigned_region INTEGER,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  last_login TIMESTAMP,
                  FOREIGN KEY(assigned_region) REFERENCES Regions(region_id))''')
    
    # Create Governorates table
    c.execute('''CREATE TABLE IF NOT EXISTS Governorates
                 (governorate_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  governorate_name TEXT NOT NULL UNIQUE,
                  description TEXT)''')
    
    # Create Regions table (with governorate relationship)
    c.execute('''CREATE TABLE IF NOT EXISTS Regions
                 (region_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  region_name TEXT NOT NULL,
                  description TEXT,
                  governorate_id INTEGER NOT NULL,
                  FOREIGN KEY(governorate_id) REFERENCES Governorates(governorate_id))''')
    
    # Create Surveys table
    c.execute('''CREATE TABLE IF NOT EXISTS Surveys
                 (survey_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  survey_name TEXT NOT NULL,
                  created_by INTEGER NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  is_active BOOLEAN DEFAULT TRUE,
                  FOREIGN KEY(created_by) REFERENCES Users(user_id))''')
    
    # Create Survey_Fields table
    c.execute('''CREATE TABLE IF NOT EXISTS Survey_Fields
                 (field_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  survey_id INTEGER NOT NULL,
                  field_type TEXT NOT NULL,
                  field_label TEXT NOT NULL,
                  field_options TEXT,
                  is_required BOOLEAN DEFAULT FALSE,
                  field_order INTEGER NOT NULL,
                  FOREIGN KEY(survey_id) REFERENCES Surveys(survey_id))''')
    
    # Create Responses table
    c.execute('''CREATE TABLE IF NOT EXISTS Responses
                 (response_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  survey_id INTEGER NOT NULL,
                  user_id INTEGER NOT NULL,
                  region_id INTEGER NOT NULL,
                  submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  is_completed BOOLEAN DEFAULT FALSE,
                  FOREIGN KEY(survey_id) REFERENCES Surveys(survey_id),
                  FOREIGN KEY(user_id) REFERENCES Users(user_id),
                  FOREIGN KEY(region_id) REFERENCES Regions(region_id))''')
    
    # Create Response_Details table
    c.execute('''CREATE TABLE IF NOT EXISTS Response_Details
                 (detail_id INTEGER PRIMARY KEY AUTOINCREMENT,
                  response_id INTEGER NOT NULL,
                  field_id INTEGER NOT NULL,
                  answer_value TEXT,
                  FOREIGN KEY(response_id) REFERENCES Responses(response_id),
                  FOREIGN KEY(field_id) REFERENCES Survey_Fields(field_id))''')
    
    # Add default admin user if none exists
    c.execute("SELECT COUNT(*) FROM Users WHERE role='admin'")
    if c.fetchone()[0] == 0:
        from auth import hash_password
        admin_password = hash_password("admin123")
        c.execute("INSERT INTO Users (username, password_hash, role) VALUES (?, ?, ?)",
                  ("admin", admin_password, "admin"))
    
    conn.commit()
    conn.close()

def get_user_by_username(username):
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM Users WHERE username=?", (username,))
    user = c.fetchone()
    conn.close()
    
    if user:
        return {
            'user_id': user[0],
            'username': user[1],
            'password_hash': user[2],
            'role': user[3],
            'assigned_region': user[4],
            'created_at': user[5],
            'last_login': user[6]
        }
    return None

def get_user_role(user_id):
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("SELECT role FROM Users WHERE user_id=?", (user_id,))
    role = c.fetchone()
    conn.close()
    return role[0] if role else None

def get_regions():
    """استرجاع جميع المناطق من قاعدة البيانات"""
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("SELECT region_id, region_name FROM Regions")
    regions = c.fetchall()
    conn.close()
    return regions
def add_user(username, password, role, region_id=None):
    """إضافة مستخدم جديد إلى قاعدة البيانات"""
    from auth import hash_password  # استيراد دالة التجزئة
    
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO Users (username, password_hash, role, assigned_region) VALUES (?, ?, ?, ?)",
            (username, hash_password(password), role, region_id)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        st.error("اسم المستخدم موجود بالفعل!")
        return False
    finally:
        conn.close()
        
def add_region(region_name, description):
    """إضافة منطقة جديدة إلى قاعدة البيانات مع التحقق من التكرار"""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        
        # التحقق من وجود المنطقة مسبقاً
        c.execute("SELECT 1 FROM Regions WHERE region_name=?", (region_name,))
        if c.fetchone():
            st.error("هذه المنطقة موجودة بالفعل!")
            return False
        
        # إضافة المنطقة الجديدة
        c.execute(
            "INSERT INTO Regions (region_name, description) VALUES (?, ?)",
            (region_name, description)
        )
        conn.commit()
        st.success(f"تمت إضافة المنطقة '{region_name}' بنجاح")
        return True
        
    except sqlite3.Error as e:
        st.error(f"حدث خطأ في قاعدة البيانات: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()
def get_region_name(region_id):
    """استرجاع اسم المنطقة بناءً على المعرف"""
    if region_id is None:
        return "غير معين"
    
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    try:
        c.execute("SELECT region_name FROM Regions WHERE region_id=?", (region_id,))
        result = c.fetchone()
        return result[0] if result else "غير معروف"
    except sqlite3.Error as e:
        print(f"خطأ في جلب اسم المنطقة: {e}")
        return "خطأ في النظام"
    finally:
        conn.close()         
        
def save_response(survey_id, user_id, region_id, is_completed=False):
    """حفظ استجابة جديدة في قاعدة البيانات وإعادة معرف الاستجابة"""
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO Responses (survey_id, user_id, region_id, is_completed) VALUES (?, ?, ?, ?)",
            (survey_id, user_id, region_id, is_completed)
        )
        response_id = c.lastrowid
        conn.commit()
        return response_id
    except sqlite3.Error as e:
        st.error(f"حدث خطأ في حفظ الاستجابة: {str(e)}")
        return None
    finally:
        conn.close()

def save_response_detail(response_id, field_id, answer_value):
    """حفظ تفاصيل إجابة لحقل معين في الاستبيان"""
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO Response_Details (response_id, field_id, answer_value) VALUES (?, ?, ?)",
            (response_id, field_id, answer_value)
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        st.error(f"حدث خطأ في حفظ تفاصيل الإجابة: {str(e)}")
        return False
    finally:
        conn.close()

def save_survey(survey_name, fields):
    """حفظ استبيان جديد مع حقوله في قاعدة البيانات"""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        
        # 1. حفظ الاستبيان الأساسي
        c.execute(
            "INSERT INTO Surveys (survey_name, created_by) VALUES (?, ?)",
            (survey_name, st.session_state.user_id)
        )
        survey_id = c.lastrowid
        
        # 2. حفظ حقول الاستبيان
        for i, field in enumerate(fields):
            field_options = json.dumps(field.get('field_options', [])) if field.get('field_options') else None
            
            c.execute(
                """INSERT INTO Survey_Fields 
                   (survey_id, field_type, field_label, field_options, is_required, field_order) 
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (survey_id, 
                 field['field_type'], 
                 field['field_label'],
                 field_options,
                 field.get('is_required', False),
                 i + 1)  # field_order starts at 1
            )
        
        conn.commit()
        return True
        
    except sqlite3.Error as e:
        st.error(f"حدث خطأ في حفظ الاستبيان: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()
def update_last_login(user_id):
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("UPDATE Users SET last_login = CURRENT_TIMESTAMP WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()            
def update_user_activity(user_id):
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("UPDATE Users SET last_activity = CURRENT_TIMESTAMP WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def delete_survey(survey_id):
    """حذف استبيان وجميع بياناته المرتبطة"""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        
        # حذف تفاصيل الإجابات المرتبطة
        c.execute('''
            DELETE FROM Response_Details 
            WHERE response_id IN (
                SELECT response_id FROM Responses WHERE survey_id = ?
            )
        ''', (survey_id,))
        
        # حذف الإجابات المرتبطة
        c.execute("DELETE FROM Responses WHERE survey_id = ?", (survey_id,))
        
        # حذف حقول الاستبيان
        c.execute("DELETE FROM Survey_Fields WHERE survey_id = ?", (survey_id,))
        
        # حذف الاستبيان نفسه
        c.execute("DELETE FROM Surveys WHERE survey_id = ?", (survey_id,))
        
        conn.commit()
        st.success("تم حذف الاستبيان بنجاح")
        return True
    except sqlite3.Error as e:
        st.error(f"حدث خطأ أثناء حذف الاستبيان: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()        