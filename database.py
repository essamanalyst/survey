import sqlite3
import streamlit as st
import json
from datetime import datetime
from pathlib import Path
from typing import List, Tuple
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
    c.execute('''CREATE TABLE IF NOT EXISTS HealthAdministrations
             (admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
              admin_name TEXT NOT NULL,
              description TEXT,
              governorate_id INTEGER NOT NULL,
              FOREIGN KEY(governorate_id) REFERENCES Governorates(governorate_id),
              UNIQUE(admin_name, governorate_id))''')
             
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
                 
    c.execute('''CREATE TABLE IF NOT EXISTS GovernorateAdmins
             (admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              governorate_id INTEGER NOT NULL,
              FOREIGN KEY(user_id) REFERENCES Users(user_id),
              FOREIGN KEY(governorate_id) REFERENCES Governorates(governorate_id),
              UNIQUE(user_id, governorate_id))''')
             
    c.execute('''CREATE TABLE IF NOT EXISTS Responses
             (response_id INTEGER PRIMARY KEY AUTOINCREMENT,
              survey_id INTEGER NOT NULL,
              user_id INTEGER NOT NULL,
              region_id INTEGER NOT NULL,
              submission_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              is_completed BOOLEAN DEFAULT FALSE,
              latitude REAL,
              longitude REAL,
              FOREIGN KEY(survey_id) REFERENCES Surveys(survey_id),
              FOREIGN KEY(user_id) REFERENCES Users(user_id),
              FOREIGN KEY(region_id) REFERENCES Regions(region_id))''')
             
             
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



def get_health_admins():
    """استرجاع جميع الإدارات الصحية من قاعدة البيانات"""
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("SELECT admin_id, admin_name FROM HealthAdministrations")
    admins = c.fetchall()
    conn.close()
    return admins

def get_health_admin_name(admin_id):
    """استرجاع اسم الإدارة الصحية بناءً على المعرف"""
    if admin_id is None:
        return "غير معين"
    
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    try:
        c.execute("SELECT admin_name FROM HealthAdministrations WHERE admin_id=?", (admin_id,))
        result = c.fetchone()
        return result[0] if result else "غير معروف"
    except sqlite3.Error as e:
        print(f"خطأ في جلب اسم الإدارة الصحية: {e}")
        return "خطأ في النظام"
    finally:
        conn.close()        
        
def save_response(survey_id, user_id, region_id, is_completed=False):
    """حفظ استجابة جديدة في قاعدة البيانات"""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        
        c.execute(
            '''INSERT INTO Responses 
               (survey_id, user_id, region_id, is_completed, latitude, longitude) 
               VALUES (?, ?, ?, ?, ?, ?)''',
            (survey_id, user_id, region_id, is_completed)
        )
        response_id = c.lastrowid
        conn.commit()
        return response_id
    except sqlite3.Error as e:
        st.error(f"حدث خطأ في حفظ الاستجابة: {str(e)}")
        return None
    finally:
        if conn:
            conn.close()

def save_response_detail(response_id, field_id, answer_value):
    """حفظ تفاصيل الإجابة"""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        
        c.execute(
            "INSERT INTO Response_Details (response_id, field_id, answer_value) VALUES (?, ?, ?)",
            (response_id, field_id, str(answer_value) if answer_value is not None else "")
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        st.error(f"حدث خطأ في حفظ تفاصيل الإجابة: {str(e)}")
        return False
    finally:
        if conn:
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

def add_health_admin(admin_name, description, governorate_id):
    """إضافة إدارة صحية جديدة إلى قاعدة البيانات مع التحقق من التكرار"""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        
        # التحقق من وجود الإدارة مسبقاً في نفس المحافظة
        c.execute("SELECT 1 FROM HealthAdministrations WHERE admin_name=? AND governorate_id=?", 
                 (admin_name, governorate_id))
        if c.fetchone():
            st.error("هذه الإدارة الصحية موجودة بالفعل في هذه المحافظة!")
            return False
        
        # إضافة الإدارة الجديدة
        c.execute(
            "INSERT INTO HealthAdministrations (admin_name, description, governorate_id) VALUES (?, ?, ?)",
            (admin_name, description, governorate_id)
        )
        conn.commit()
        st.success(f"تمت إضافة الإدارة الصحية '{admin_name}' بنجاح")
        return True
        
    except sqlite3.Error as e:
        st.error(f"حدث خطأ في قاعدة البيانات: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()     
def get_governorates_list():
    """استرجاع قائمة المحافظات للاستخدام في القوائم المنسدلة"""
    conn = sqlite3.connect(DATABASE_PATH)
    c = conn.cursor()
    c.execute("SELECT governorate_id, governorate_name FROM Governorates")
    governorates = c.fetchall()
    conn.close()
    return governorates      
def update_survey(survey_id, survey_name, is_active, fields):
    """تحديث بيانات الاستبيان وحقوله"""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        
        # 1. تحديث بيانات الاستبيان الأساسية
        c.execute(
            "UPDATE Surveys SET survey_name=?, is_active=? WHERE survey_id=?",
            (survey_name, is_active, survey_id)
        )
        
        # 2. تحديث الحقول الموجودة أو إضافة جديدة
        for field in fields:
            field_options = json.dumps(field.get('field_options', [])) if field.get('field_options') else None
            
            if 'field_id' in field:  # حقل موجود يتم تحديثه
                c.execute(
                    """UPDATE Survey_Fields 
                       SET field_label=?, field_type=?, field_options=?, is_required=?
                       WHERE field_id=?""",
                    (field['field_label'], 
                     field['field_type'],
                     field_options,
                     field.get('is_required', False),
                     field['field_id'])
                )
            else: 
                c.execute("SELECT MAX(field_order) FROM Survey_Fields WHERE survey_id=?", (survey_id,))
                max_order = c.fetchone()[0] or 0
                
                c.execute(
                    """INSERT INTO Survey_Fields 
                       (survey_id, field_label, field_type, field_options, is_required, field_order) 
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (survey_id,
                     field['field_label'],
                     field['field_type'],
                     field_options,
                     field.get('is_required', False),
                     max_order + 1)
                )
        
        conn.commit()
        st.success("تم تحديث الاستبيان بنجاح")
        return True
        
    except sqlite3.Error as e:
        st.error(f"حدث خطأ في تحديث الاستبيان: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()      
def update_user(user_id, username, role, region_id=None):
    """تحديث بيانات المستخدم"""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        
        c.execute("SELECT 1 FROM Users WHERE username=? AND user_id!=?", (username, user_id))
        if c.fetchone():
            st.error("اسم المستخدم موجود بالفعل!")
            return False
        
        c.execute(
            "UPDATE Users SET username=?, role=?, assigned_region=? WHERE user_id=?",
            (username, role, region_id, user_id)
        )
        
        if role == 'governorate_admin':
            c.execute("DELETE FROM GovernorateAdmins WHERE user_id=?", (user_id,))
            
        conn.commit()
        st.success("تم تحديث بيانات المستخدم بنجاح")
        return True
    except sqlite3.Error as e:
        st.error(f"حدث خطأ في تحديث المستخدم: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()

def add_user(username, password, role, region_id=None):
    """إضافة مستخدم جديد إلى قاعدة البيانات"""
    from auth import hash_password
    
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        
        c.execute("SELECT 1 FROM Users WHERE username=?", (username,))
        if c.fetchone():
            st.error("اسم المستخدم موجود بالفعل!")
            return False
        
        c.execute(
            "INSERT INTO Users (username, password_hash, role, assigned_region) VALUES (?, ?, ?, ?)",
            (username, hash_password(password), role, region_id)
        )
        conn.commit()
        st.success("تمت إضافة المستخدم بنجاح")
        return True
    except sqlite3.Error as e:
        st.error(f"حدث خطأ في إضافة المستخدم: {str(e)}")
        return False
    finally:
        if conn:
            conn.close()      
            

def get_governorate_admin(user_id):
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        c = conn.cursor()
        c.execute('''
            SELECT g.governorate_id, g.governorate_name 
            FROM GovernorateAdmins ga
            JOIN Governorates g ON ga.governorate_id = g.governorate_id
            WHERE ga.user_id = ?
        ''', (user_id,))
        return c.fetchall()
    finally:
        conn.close()  

# دوال مسؤول المحافظة
def add_governorate_admin(user_id: int, governorate_id: int) -> bool:
    """
    إضافة مسؤول محافظة جديد
    """
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        conn.execute(
            "INSERT INTO GovernorateAdmins (user_id, governorate_id) VALUES (?, ?)",
            (user_id, governorate_id)
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        st.error(f"خطأ في إضافة مسؤول المحافظة: {str(e)}")
        return False
    finally:
        conn.close()

def get_governorate_admin_data(user_id: int) -> tuple:
    """
    الحصول على بيانات مسؤول المحافظة
    """
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT g.governorate_id, g.governorate_name, g.description 
            FROM GovernorateAdmins ga
            JOIN Governorates g ON ga.governorate_id = g.governorate_id
            WHERE ga.user_id = ?
        ''', (user_id,))
        return cursor.fetchone()
    except sqlite3.Error as e:
        st.error(f"خطأ في جلب بيانات المحافظة: {str(e)}")
        return None
    finally:
        conn.close()

def get_governorate_surveys(governorate_id: int) -> list:
    """
    الحصول على الاستبيانات الخاصة بمحافظة معينة
    """
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT s.survey_id, s.survey_name, s.created_at, s.is_active
            FROM Surveys s
            JOIN SurveyGovernorate sg ON s.survey_id = sg.survey_id
            WHERE sg.governorate_id = ?
            ORDER BY s.created_at DESC
        ''', (governorate_id,))
        return cursor.fetchall()
    finally:
        conn.close()

def get_governorate_employees(governorate_id: int) -> list:
    """
    الحصول على الموظفين التابعين لمحافظة معينة
    """
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT u.user_id, u.username, ha.admin_name
            FROM Users u
            JOIN HealthAdministrations ha ON u.assigned_region = ha.admin_id
            WHERE ha.governorate_id = ? AND u.role = 'employee'
            ORDER BY u.username
        ''', (governorate_id,))
        return cursor.fetchall()
    finally:
        conn.close()        
        
def get_allowed_surveys(user_id: int) -> List[Tuple[int, str]]:
    """الحصول على الاستبيانات المسموح بها للموظف"""
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        cursor = conn.cursor()
        
        # الحصول على الإدارة الصحية للموظف
        cursor.execute("SELECT assigned_region FROM Users WHERE user_id=?", (user_id,))
        region_id = cursor.fetchone()
        if not region_id:
            return []
        
        # الحصول على المحافظة التابعة لها الإدارة الصحية
        cursor.execute("SELECT governorate_id FROM HealthAdministrations WHERE admin_id=?", (region_id[0],))
        governorate_id = cursor.fetchone()
        if not governorate_id:
            return []
        
        # الحصول على الاستبيانات الخاصة بالمحافظة
        cursor.execute('''
            SELECT s.survey_id, s.survey_name
            FROM Surveys s
            JOIN SurveyGovernorate sg ON s.survey_id = sg.survey_id
            WHERE sg.governorate_id = ?
            ORDER BY s.survey_name
        ''', (governorate_id[0],))
        
        return cursor.fetchall()
    except sqlite3.Error as e:
        st.error(f"حدث خطأ في جلب الاستبيانات المسموح بها: {str(e)}")
        return []
    finally:
        conn.close()        
        
def get_survey_fields(survey_id: int) -> List[Tuple]:
    """الحصول على حقول استبيان معين"""
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                field_id, 
                field_label, 
                field_type, 
                field_options, 
                is_required, 
                field_order
            FROM Survey_Fields
            WHERE survey_id = ?
            ORDER BY field_order
        ''', (survey_id,))
        return cursor.fetchall()
    except sqlite3.Error as e:
        st.error(f"حدث خطأ في جلب حقول الاستبيان: {str(e)}")
        return []
    finally:
        conn.close()
        
