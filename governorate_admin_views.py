import streamlit as st
import sqlite3
import pandas as pd
from typing import List, Tuple, Optional
from database import (
    DATABASE_PATH,
    get_governorate_admin_data,
    get_governorate_surveys,
    get_governorate_employees,
    update_survey,
    get_survey_fields,
    update_user
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
    إدارة استبيانات المحافظة
    """
    st.header(f"إدارة استبيانات محافظة {governorate_name}")
    
    # عرض الاستبيانات الحالية
    surveys = get_governorate_surveys(governorate_id)
    
    if not surveys:
        st.info("لا توجد استبيانات مسجلة لهذه المحافظة")
        return
    
    # إنشاء عرض تفاعلي للاستبيانات
    for survey in surveys:
        survey_id, name, created_at, is_active = survey
        
        with st.expander(f"{name} - {'🟢 نشط' if is_active else '🔴 غير نشط'}"):
            col1, col2 = st.columns([4, 1])
            
            with col1:
                st.markdown(f"""
                **تاريخ الإنشاء:** {created_at}  
                **الحالة:** {'مفعل' if is_active else 'غير مفعل'}
                """)
                
            with col2:
                if st.button("تعديل", key=f"edit_{survey_id}"):
                    st.session_state.editing_survey = survey_id
                
                if st.button("عرض البيانات", key=f"view_{survey_id}"):
                    st.session_state.viewing_survey = survey_id
    
    # معالجة تعديل الاستبيان
    if 'editing_survey' in st.session_state:
        edit_governorate_survey(st.session_state.editing_survey, governorate_id)
    
    # معالجة عرض بيانات الاستبيان
    if 'viewing_survey' in st.session_state:
        view_survey_responses(st.session_state.viewing_survey)

def edit_governorate_survey(survey_id: int, governorate_id: int):
    """
    تعديل استبيان محافظة معينة
    """
    st.subheader("تعديل الاستبيان")
    
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        # الحصول على بيانات الاستبيان
        survey = conn.execute(
            "SELECT survey_name, is_active FROM Surveys WHERE survey_id=?",
            (survey_id,)
        ).fetchone()
        
        # الحصول على حقول الاستبيان
        fields = get_survey_fields(survey_id)
        
        # نموذج التعديل
        with st.form(f"edit_survey_{survey_id}"):
            new_name = st.text_input("اسم الاستبيان", value=survey[0])
            is_active = st.checkbox("مفعل", value=bool(survey[1]))
            
            st.subheader("حقول الاستبيان")
            updated_fields = []
            
            for field in fields:
                field_id = field[0]
                with st.expander(f"حقل: {field[2]} ({field[3]})"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        new_label = st.text_input("التسمية", value=field[2], key=f"label_{field_id}")
                        new_type = st.selectbox(
                            "النوع",
                            ["text", "number", "dropdown", "checkbox", "date"],
                            index=["text", "number", "dropdown", "checkbox", "date"].index(field[3]),
                            key=f"type_{field_id}"
                        )
                    
                    with col2:
                        new_required = st.checkbox("مطلوب", value=bool(field[5]), key=f"required_{field_id}")
                        if new_type == 'dropdown':
                            options = "\n".join(json.loads(field[4])) if field[4] else ""
                            new_options = st.text_area(
                                "خيارات القائمة (سطر لكل خيار)",
                                value=options,
                                key=f"options_{field_id}"
                            )
                    
                    updated_fields.append({
                        'field_id': field_id,
                        'field_label': new_label,
                        'field_type': new_type,
                        'field_options': new_options.split('\n') if new_type == 'dropdown' else None,
                        'is_required': new_required
                    })
            
            # أزرار الحفظ والإلغاء
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("💾 حفظ التعديلات"):
                    if update_survey(survey_id, new_name, is_active, updated_fields):
                        st.success("تم تحديث الاستبيان بنجاح")
                        del st.session_state.editing_survey
                        st.rerun()
            
            with col2:
                if st.form_submit_button("❌ إلغاء"):
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
        view_survey_responses(selected_survey[0])

def view_survey_responses(survey_id: int):
    """
    عرض إجابات استبيان معين
    """
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        # الحصول على معلومات الاستبيان
        survey = conn.execute(
            "SELECT survey_name FROM Surveys WHERE survey_id=?",
            (survey_id,)
        ).fetchone()
        
        st.subheader(f"إجابات استبيان {survey[0]}")
        
        # الحصول على الإجابات
        responses = conn.execute('''
            SELECT r.response_id, u.username, ha.admin_name, 
                   r.submission_date, r.is_completed, r.latitude, r.longitude
            FROM Responses r
            JOIN Users u ON r.user_id = u.user_id
            JOIN HealthAdministrations ha ON r.region_id = ha.admin_id
            WHERE r.survey_id = ?
            ORDER BY r.submission_date DESC
        ''', (survey_id,)).fetchall()
        
        if not responses:
            st.info("لا توجد إجابات مسجلة لهذا الاستبيان")
            return
        
        # عرض الإحصائيات
        total = len(responses)
        completed = sum(1 for r in responses if r[4])
        
        col1, col2, col3 = st.columns(3)
        col1.metric("إجمالي الإجابات", total)
        col2.metric("الإجابات المكتملة", completed)
        col3.metric("نسبة الإكمال", f"{round((completed/total)*100)}%")
        
        # عرض البيانات في جدول
        df = pd.DataFrame(
            [(r[0], r[1], r[2], r[3], "✔️" if r[4] else "✖️", 
              f"{r[5]}, {r[6]}" if r[5] and r[6] else "غير مسجل") 
             for r in responses],
            columns=["ID", "المستخدم", "المنطقة", "التاريخ", "الحالة", "الإحداثيات"]
        )
        
        st.dataframe(df, use_container_width=True)
        
        # خيار التصدير
        if st.button("📤 تصدير إلى Excel"):
            export_to_excel(df, survey[0])
    
    except sqlite3.Error as e:
        st.error(f"حدث خطأ في قاعدة البيانات: {str(e)}")
    finally:
        conn.close()

def export_to_excel(df: pd.DataFrame, survey_name: str):
    """
    تصدير البيانات إلى ملف Excel
    """
    from io import BytesIO
    import re
    
    # تنظيف اسم الملف
    filename = re.sub(r'[^\w\-_]', '_', survey_name) + ".xlsx"
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="البيانات")
    
    st.download_button(
        label="⬇️ تنزيل الملف",
        data=output.getvalue(),
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

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
                if st.button("تعديل", key=f"edit_emp_{user_id}"):
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
        
        # الحصول على الإدارات الصحية للمحافظة
        health_admins = conn.execute('''
            SELECT admin_id, admin_name FROM HealthAdministrations
            WHERE governorate_id = ?
            ORDER BY admin_name
        ''', (governorate_id,)).fetchall()
        
        # الحصول على الاستبيانات المتاحة
        surveys = conn.execute('''
            SELECT s.survey_id, s.survey_name
            FROM Surveys s
            JOIN SurveyGovernorate sg ON s.survey_id = sg.survey_id
            WHERE sg.governorate_id = ?
            ORDER BY s.survey_name
        ''', (governorate_id,)).fetchall()
        
        # الحصول على الاستبيانات المسموح بها للموظف
        allowed_surveys = conn.execute('''
            SELECT survey_id FROM EmployeeSurveys
            WHERE user_id = ?
        ''', (user_id,)).fetchall()
        allowed_surveys = [s[0] for s in allowed_surveys]
        
        # نموذج التعديل
        with st.form(f"edit_employee_{user_id}"):
            st.text_input("اسم المستخدم", value=employee[0], disabled=True)
            
            selected_admin = st.selectbox(
                "الإدارة الصحية",
                options=[a[0] for a in health_admins],
                index=[a[0] for a in health_admins].index(employee[1]),
                format_func=lambda x: next(a[1] for a in health_admins if a[0] == x)
            )
            
            selected_surveys = st.multiselect(
                "الاستبيانات المسموح بها",
                options=[s[0] for s in surveys],
                default=allowed_surveys,
                format_func=lambda x: next(s[1] for s in surveys if s[0] == x)
            )
            
            # أزرار الحفظ والإلغاء
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("💾 حفظ التعديلات"):
                    # تحديث بيانات الموظف
                    conn.execute('''
                        UPDATE Users SET assigned_region = ? WHERE user_id = ?
                    ''', (selected_admin, user_id))
                    
                    # تحديث الاستبيانات المسموح بها
                    conn.execute('''
                        DELETE FROM EmployeeSurveys WHERE user_id = ?
                    ''', (user_id,))
                    
                    for survey_id in selected_surveys:
                        conn.execute('''
                            INSERT INTO EmployeeSurveys (user_id, survey_id)
                            VALUES (?, ?)
                        ''', (user_id, survey_id))
                    
                    conn.commit()
                    st.success("تم تحديث بيانات الموظف بنجاح")
                    del st.session_state.editing_employee
                    st.rerun()
            
            with col2:
                if st.form_submit_button("❌ إلغاء"):
                    del st.session_state.editing_employee
                    st.rerun()
    
    except sqlite3.Error as e:
        st.error(f"حدث خطأ في قاعدة البيانات: {str(e)}")
    finally:
        conn.close()