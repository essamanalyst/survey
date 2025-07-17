import streamlit as st
import sqlite3
import pandas as pd
import json
from typing import List, Tuple, Optional
from datetime import datetime
from database import (
    DATABASE_PATH,
    get_governorate_admin_data,
    get_governorate_surveys,
    get_governorate_employees,
    update_survey,
    get_survey_fields,
    update_user,
    get_user_allowed_surveys,
    update_user_allowed_surveys,
    get_response_info,
    get_response_details,
    update_response_detail
)

def show_governorate_admin_dashboard():
    """
    عرض لوحة تحكم مسؤول المحافظة
    """
    # التحقق من الصلاحيات
    if st.session_state.get('role') != 'governorate_admin':
        st.error("غير مصرح لك بالوصول إلى هذه الصفحة")
        return
    
    # الحصول على بيانات المحافظة
    gov_data = get_governorate_admin_data(st.session_state.user_id)
    
    if not gov_data:
        st.error("حسابك غير مرتبط بأي محافظة. يرجى التواصل مع مسؤول النظام.")
        return
    
    governorate_id, governorate_name, description = gov_data
    
    # تنسيق واجهة المستخدم
    st.set_page_config(layout="wide")
    st.title(f"لوحة تحكم محافظة {governorate_name}")
    st.markdown(f"**وصف المحافظة:** {description}")
    
    # تبويبات لوحة التحكم
    tab1, tab2, tab3 = st.tabs([
        "📋 إدارة الاستبيانات",
        "📊 عرض البيانات",
        "👥 إدارة الموظفين"
    ])
    
    with tab1:
        manage_governorate_surveys(governorate_id, governorate_name)
    
    with tab2:
        view_governorate_data(governorate_id, governorate_name)
    
    with tab3:
        manage_governorate_employees(governorate_id, governorate_name)

def manage_governorate_surveys(governorate_id: int, governorate_name: str):
    """
    إدارة استبيانات محافظة معينة
    """
    st.subheader(f"إدارة استبيانات محافظة {governorate_name}")
    
    # التحقق مما إذا كان المستخدم يشاهد أو يعدل استبيان
    if 'viewing_survey' in st.session_state:
        view_survey_responses(st.session_state.viewing_survey, governorate_id)
        if st.button("العودة"):
            del st.session_state.viewing_survey
            st.rerun()
        return
    
    if 'editing_survey' in st.session_state:
        edit_governorate_survey(st.session_state.editing_survey, governorate_id)
        return
    
    # عرض قائمة الاستبيانات
    surveys = get_governorate_surveys(governorate_id)
    
    if not surveys:
        st.info("لا توجد استبيانات لهذه المحافظة")
        return
    
    # عرض الاستبيانات في جدول
    df = pd.DataFrame(survey[1:] for survey in surveys)
    df.columns = ["اسم الاستبيان", "تاريخ الإنشاء", "الحالة"]
    df["الحالة"] = df["الحالة"].apply(lambda x: "مفعل" if x else "غير مفعل")

    st.dataframe(df, use_container_width=True)
    
    # اختيار استبيان للتحكم
    selected_survey = st.selectbox(
        "اختر استبيان للتحكم",
        surveys,
        format_func=lambda x: x[1]
    )
    
    survey_id = selected_survey[0]
    
    # أزرار التحكم
    col1, col2 = st.columns(2)  # تم إزالة زر إضافة حقل جديد
    
    with col1:
        if st.button("عرض المدخلات", key=f"view_{survey_id}"):
            st.session_state.viewing_survey = survey_id
            st.rerun()
    
    with col2:
        if st.button("تعديل حالة الاستبيان", key=f"edit_{survey_id}"):
            st.session_state.editing_survey = survey_id
            st.rerun()



def edit_governorate_survey(survey_id: int, governorate_id: int):
    """
    تعديل استبيان محافظة معينة (صلاحيات محدودة لمسؤول المحافظة)
    """
    st.subheader("تعديل حالة الاستبيان")
    
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        # الحصول على بيانات الاستبيان
        survey = conn.execute(
            "SELECT survey_name, is_active FROM Surveys WHERE survey_id=?",
            (survey_id,)
        ).fetchone()
        
        # نموذج التعديل المحدود
        with st.form(f"edit_survey_{survey_id}"):
            st.text_input("اسم الاستبيان", value=survey[0], disabled=True)
            is_active = st.checkbox("مفعل", value=bool(survey[1]))
            
            st.info("ملاحظة: مسؤول المحافظة يمكنه فقط تغيير حالة تفعيل الاستبيان")
            
            # أزرار الحفظ والإلغاء
            col1, col2 = st.columns(2)
            with col1:
                save_btn = st.form_submit_button("💾 حفظ التعديلات")
                if save_btn:
                    conn.execute(
                        "UPDATE Surveys SET is_active=? WHERE survey_id=?",
                        (is_active, survey_id)
                    )
                    conn.commit()
                    st.success("تم تحديث حالة الاستبيان بنجاح")
                    del st.session_state.editing_survey
                    st.rerun()
            
            with col2:
                cancel_btn = st.form_submit_button("❌ إلغاء")
                if cancel_btn:
                    del st.session_state.editing_survey
                    st.rerun()
    
    except sqlite3.Error as e:
        st.error(f"حدث خطأ في قاعدة البيانات: {str(e)}")
    finally:
        conn.close()



def view_governorate_data(governorate_id: int, governorate_name: str):
    """
    عرض بيانات المحافظة
    """
    st.header(f"بيانات محافظة {governorate_name}")
    
    surveys = get_governorate_surveys(governorate_id)
    
    if not surveys:
        st.info("لا توجد استبيانات لعرض البيانات")
        return
    
    selected_survey = st.selectbox(
        "اختر استبيان",
        surveys,
        format_func=lambda x: x[1],
        key="survey_select"
    )
    
    if selected_survey:
        view_survey_responses(selected_survey[0], governorate_id)


def view_survey_responses(survey_id: int, governorate_id: int):
    """
    عرض إجابات استبيان معين للمحافظة فقط مع تمكين التعديل
    """
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        # الحصول على معلومات الاستبيان
        survey = conn.execute(
            "SELECT survey_name FROM Surveys WHERE survey_id=?",
            (survey_id,)
        ).fetchone()
        
        st.subheader(f"إجابات استبيان {survey[0]} - تعديل المدخلات")
        
        # زر العودة مع مفتاح فريد
        if st.button("← العودة إلى القائمة", 
                    key=f"back_{survey_id}_{governorate_id}_{datetime.now().timestamp()}"):
            if 'viewing_survey' in st.session_state:
                del st.session_state.viewing_survey
            st.rerun()
        
        # الحصول على الإجابات للمحافظة فقط
        responses = conn.execute('''
            SELECT r.response_id, u.username, ha.admin_name, 
                   r.submission_date, r.is_completed
            FROM Responses r
            JOIN Users u ON r.user_id = u.user_id
            JOIN HealthAdministrations ha ON r.region_id = ha.admin_id
            WHERE r.survey_id = ? AND ha.governorate_id = ?
            ORDER BY r.submission_date DESC
        ''', (survey_id, governorate_id)).fetchall()
        
        if not responses:
            st.info("لا توجد إجابات مسجلة لهذا الاستبيان في محافظتك")
            return
        
        # عرض الإحصائيات
        total = len(responses)
        completed = sum(1 for r in responses if r[4])
        
        col1, col2, col3 = st.columns(3)
        col1.metric("إجمالي الإجابات", total)
        col2.metric("الإجابات المكتملة", completed)
        col3.metric("نسبة الإكمال", f"{round((completed/total)*100)}%")
        
        # اختيار إجابة محددة مع مفتاح فريد
        selected_response = st.selectbox(
            "اختر إجابة لتعديلها",
            options=responses,
            format_func=lambda x: f"إجابة #{x[0]} - {x[1]} - {x[2]} - {x[3]}",
            key=f"select_response_{survey_id}_{governorate_id}_{datetime.now().timestamp()}"
        )
        
        if selected_response:
            response_id = selected_response[0]
            display_editable_response(response_id, survey_id, governorate_id)
    
    except sqlite3.Error as e:
        st.error(f"حدث خطأ في قاعدة البيانات: {str(e)}")
    finally:
        conn.close()

def display_editable_response(response_id: int, survey_id: int, governorate_id: int):
    """
    عرض وتعديل إجابة محددة مع حل مشاكل الأزرار بشكل نهائي
    """
    # الحصول على معلومات الإجابة
    response_info = get_response_info(response_id)
    if not response_info:
        st.error("لم يتم العثور على معلومات الإجابة")
        return
    
    # إنشاء كائن حالة الجلسة إذا لم يكن موجوداً
    if f"response_{response_id}_edits" not in st.session_state:
        st.session_state[f"response_{response_id}_edits"] = {}
    
    # عرض معلومات الإجابة
    with st.container():
        st.markdown(f"""
        ### معلومات الإجابة:
        - **المستخدم:** {response_info[2]}
        - **الإدارة الصحية:** {response_info[3]}
        - **المحافظة:** {response_info[4]}
        - **تاريخ التقديم:** {response_info[5]}
        """)
        
        # زر العودة مع مفتاح فريد
        if st.button("← العودة إلى القائمة", 
                    key=f"back_{response_id}_{datetime.now().timestamp()}"):
            if 'viewing_survey' in st.session_state:
                del st.session_state.viewing_survey
            st.rerun()

    # الحصول على تفاصيل الإجابة
    details = get_response_details(response_id)
    if not details:
        st.warning("لا توجد تفاصيل مسجلة لهذه الإجابة")
        return
    
    # عرض حقول التعديل
    for detail in details:
        detail_id, field_id, label, field_type, options, answer = detail
        
        # استخدام مفتاح فريد لكل حقل يتضمن معرف الاستبيان وطابع زمني
        field_key = f"field_{survey_id}_{response_id}_{detail_id}_{datetime.now().timestamp()}"
        
        st.markdown(f"#### {label}")
        
        if field_type == 'text':
            new_value = st.text_input(
                label,
                value=answer,
                key=field_key
            )
        elif field_type == 'number':
            new_value = st.number_input(
                label,
                value=float(answer) if answer and answer.replace('.', '').isdigit() else 0,
                key=field_key
            )
        elif field_type == 'dropdown':
            options_list = json.loads(options) if options else []
            new_value = st.selectbox(
                label,
                options=options_list,
                index=options_list.index(answer) if answer in options_list else 0,
                key=field_key
            )
        elif field_type == 'checkbox':
            new_value = st.checkbox(
                label,
                value=bool(answer),
                key=field_key
            )
        elif field_type == 'date':
            new_value = st.date_input(
                label,
                value=datetime.strptime(answer, "%Y-%m-%d").date() if answer else datetime.now(),
                key=field_key
            )
        else:
            new_value = answer
        
        # حفظ التعديلات في حالة الجلسة
        if new_value != answer:
            st.session_state[f"response_{response_id}_edits"][detail_id] = str(new_value)
        elif detail_id in st.session_state[f"response_{response_id}_edits"]:
            del st.session_state[f"response_{response_id}_edits"][detail_id]

    # أزرار التحكم
    col1, col2 = st.columns(2)
    
    with col1:
        # زر الحفظ مع مفتاح فريد
        if st.button("💾 حفظ التعديلات", 
                    key=f"save_{response_id}_{datetime.now().timestamp()}"):
            if st.session_state[f"response_{response_id}_edits"]:
                success_count = 0
                for detail_id, new_value in st.session_state[f"response_{response_id}_edits"].items():
                    if update_response_detail(detail_id, new_value):
                        success_count += 1
                
                if success_count > 0:
                    st.success(f"تم تحديث {success_count} حقول بنجاح")
                    # تحديث الصفحة بعد الحفظ
                    st.rerun()
                else:
                    st.error("حدث خطأ أثناء حفظ التعديلات")
            else:
                st.info("لم تقم بإجراء أي تعديلات")
    
    with col2:
        # زر الإلغاء مع مفتاح فريد
        if st.button("❌ إلغاء التعديلات", 
                    key=f"cancel_{response_id}_{datetime.now().timestamp()}"):
            # مسح التعديلات من حالة الجلسة
            st.session_state[f"response_{response_id}_edits"] = {}
            st.info("تم إلغاء جميع التعديلات")
            st.rerun()

def manage_governorate_employees(governorate_id: int, governorate_name: str):
    """
    إدارة موظفي المحافظة
    """
    st.header(f"إدارة موظفي محافظة {governorate_name}")
    
    employees = get_governorate_employees(governorate_id)
    
    if not employees:
        st.info("لا يوجد موظفون مسجلون لهذه المحافظة")
        return
    
    # عرض الموظفين
    for emp in employees:
        user_id, username, admin_name = emp
        
        with st.expander(f"{username} - {admin_name}"):
            col1, col2 = st.columns([4, 1])
            
            with col1:
                st.markdown(f"""
                **اسم المستخدم:** {username}  
                **الإدارة الصحية:** {admin_name}
                """)
            
            with col2:
                if st.button("تعديل", key=f"edit_btn_{user_id}"):
                    st.session_state.editing_employee = user_id
    # معالجة تعديل الموظف
    if 'editing_employee' in st.session_state:
        edit_employee(st.session_state.editing_employee, governorate_id)

def edit_employee(user_id: int, governorate_id: int):
    """
    تعديل بيانات الموظف
    """
    st.subheader("تعديل بيانات الموظف")
    
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        # الحصول على بيانات الموظف
        employee = conn.execute('''
            SELECT u.username, u.assigned_region, ha.admin_name
            FROM Users u
            JOIN HealthAdministrations ha ON u.assigned_region = ha.admin_id
            WHERE u.user_id = ?
        ''', (user_id,)).fetchone()
        
        if not employee:
            st.error("الموظف غير موجود")
            del st.session_state.editing_employee
            return
        
        # الحصول على الإدارات الصحية للمحافظة فقط
        health_admins = conn.execute('''
            SELECT admin_id, admin_name FROM HealthAdministrations
            WHERE governorate_id = ?
            ORDER BY admin_name
        ''', (governorate_id,)).fetchall()
        
        # الحصول على الاستبيانات المتاحة للمحافظة فقط
        surveys = get_governorate_surveys(governorate_id)
        
        # الحصول على الاستبيانات المسموح بها للموظف
        allowed_surveys = get_user_allowed_surveys(user_id)
        allowed_survey_ids = [s[0] for s in allowed_surveys]
        
        # تصفية allowed_survey_ids لضمان وجودها في surveys
        survey_ids = [s[0] for s in surveys]
        valid_allowed_survey_ids = [sid for sid in allowed_survey_ids if sid in survey_ids]
        
        # نموذج التعديل
        with st.form(f"edit_employee_{user_id}"):
            st.text_input("اسم المستخدم", value=employee[0], disabled=True)
            
            selected_admin = st.selectbox(
                "الإدارة الصحية",
                options=[a[0] for a in health_admins],
                index=[a[0] for a in health_admins].index(employee[1]) if health_admins else 0,
                format_func=lambda x: next(a[1] for a in health_admins if a[0] == x)
            )
            
            if surveys:
                selected_surveys = st.multiselect(
                    "الاستبيانات المسموح بها",
                    options=[s[0] for s in surveys],
                    default=valid_allowed_survey_ids,
                    format_func=lambda x: next(s[1] for s in surveys if s[0] == x)
                )
            else:
                st.info("لا توجد استبيانات متاحة لهذه المحافظة")
                selected_surveys = []
            
            # أزرار الحفظ والإلغاء
            col1, col2 = st.columns(2)
            with col1:
                submit_btn = st.form_submit_button("💾 حفظ التعديلات")
            with col2:
                cancel_btn = st.form_submit_button("❌ إلغاء")
            
            if submit_btn:
                # تحديث بيانات الموظف
                update_user(user_id, employee[0], 'employee', selected_admin)
                
                # تحديث الاستبيانات المسموح بها
                if update_user_allowed_surveys(user_id, selected_surveys):
                    st.success("تم تحديث بيانات الموظف بنجاح")
                    del st.session_state.editing_employee
                    st.rerun()
            
            if cancel_btn:
                del st.session_state.editing_employee
                st.rerun()
    
    except sqlite3.Error as e:
        st.error(f"حدث خطأ في قاعدة البيانات: {str(e)}")
    finally:
        conn.close()
        
        

        
