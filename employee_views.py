import streamlit as st
import sqlite3
import pandas as pd
import geocoder
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import json
from database import (
    DATABASE_PATH,
    get_health_admin_name,
    save_response,
    save_response_detail,
    get_allowed_surveys,
    get_survey_fields
)

def show_employee_dashboard():
    """
    عرض لوحة تحكم الموظف مع الميزات المطورة:
    - اختيار متعدد للاستبيانات
    - تحديد الموقع الجغرافي
    - واجهة مستخدم محسنة
    """
    # التحقق من وجود region_id في الجلسة
    if not st.session_state.get('region_id'):
        st.error("حسابك غير مرتبط بأي منطقة. يرجى التواصل مع المسؤول.")
        return

    # الحصول على معلومات المنطقة التابع لها الموظف
    region_info = get_employee_region_info(st.session_state.region_id)
    if not region_info:
        st.error("لم يتم العثور على معلومات المنطقة الخاصة بك في النظام")
        return

    # عرض معلومات المنطقة والمحافظة
    display_employee_header(region_info)

    # الحصول على الاستبيانات المسموح بها للموظف
    allowed_surveys = get_allowed_surveys(st.session_state.user_id)
    
    if not allowed_surveys:
        st.info("لا توجد استبيانات متاحة لك حاليًا")
        return

    # عرض اختيار متعدد للاستبيانات
    selected_surveys = display_survey_selection(allowed_surveys)
    
    # عرض كل استبيان محدد
    for survey_id in selected_surveys:
        display_single_survey(survey_id, region_info['admin_id'])

def get_employee_region_info(region_id: int) -> Optional[Dict]:
    """الحصول على معلومات المنطقة التابع لها الموظف"""
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT h.admin_id, h.admin_name, g.governorate_name, g.governorate_id
            FROM HealthAdministrations h
            JOIN Governorates g ON h.governorate_id = g.governorate_id
            WHERE h.admin_id = ?
        ''', (region_id,))
        result = cursor.fetchone()
        return {
            'admin_id': result[0],
            'admin_name': result[1],
            'governorate_name': result[2],
            'governorate_id': result[3]
        } if result else None
    except sqlite3.Error as e:
        st.error(f"خطأ في قاعدة البيانات: {str(e)}")
        return None
    finally:
        conn.close()

def display_employee_header(region_info: Dict):
    """عرض معلومات رأس لوحة الموظف"""
    st.set_page_config(layout="wide")
    st.title(f"لوحة الموظف - {region_info['admin_name']}")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("المحافظة")
        st.info(region_info['governorate_name'])
    with col2:
        st.subheader("الإدارة الصحية")
        st.info(region_info['admin_name'])
    with col3:
        st.subheader("آخر دخول")
        st.info(st.session_state.get('last_login', 'غير معروف'))

def display_survey_selection(allowed_surveys: List[Tuple[int, str]]) -> List[int]:
    """عرض اختيار متعدد للاستبيانات وإرجاع القيم المحددة"""
    st.header("الاستبيانات المتاحة")
    
    selected_surveys = st.multiselect(
        "اختر استبيان أو أكثر",
        options=[s[0] for s in allowed_surveys],
        format_func=lambda x: next(s[1] for s in allowed_surveys if s[0] == x),
        key="selected_surveys"
    )
    
    return selected_surveys

def display_single_survey(survey_id: int, region_id: int):
    """عرض استبيان واحد مع خيارات الإدخال"""
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        # الحصول على معلومات الاستبيان
        survey_info = conn.execute('''
            SELECT survey_name, created_at FROM Surveys WHERE survey_id = ?
        ''', (survey_id,)).fetchone()
        
        if not survey_info:
            st.error("الاستبيان المحدد غير موجود")
            return
            
        # عرض عنوان الاستبيان
        with st.expander(f"📋 {survey_info[0]} (تاريخ الإنشاء: {survey_info[1]})"):
            # الحصول على حقول الاستبيان
            fields = get_survey_fields(survey_id)
            
            # عرض نموذج الاستبيان مع تحديد الموقع
            display_survey_form(survey_id, region_id, fields, survey_info[0])
            
    except sqlite3.Error as e:
        st.error(f"حدث خطأ في قاعدة البيانات: {str(e)}")
    finally:
        conn.close()

def display_survey_form(survey_id: int, region_id: int, fields: List[Tuple], survey_name: str):
    """عرض نموذج استبيان مع خيارات الحفظ"""
    with st.form(f"survey_form_{survey_id}"):
        st.markdown("**يرجى تعبئة جميع الحقول المطلوبة (*)**")
        
        # قسم تحديد الموقع الجغرافي
        location_section = st.container()
        with location_section:
            st.subheader("📍 الموقع الجغرافي")
            latitude, longitude = get_geolocation()
        
        # قسم حقول الاستبيان
        st.subheader("🧾 بيانات الاستبيان")
        answers = {}
        for field in fields:
            field_id, label, field_type, options, is_required, _ = field
            answers[field_id] = render_field(field_id, label, field_type, options, is_required)
        
        # أزرار الحفظ والإرسال
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("🚀 إرسال النموذج")
        with col2:
            save_draft = st.form_submit_button("💾 حفظ مسودة")
        
        if submitted or save_draft:
            process_survey_submission(
                survey_id,
                region_id,
                fields,
                answers,
                latitude,
                longitude,
                submitted,
                survey_name
            )

def get_geolocation() -> Tuple[Optional[float], Optional[float]]:
    """الحصول على الموقع الجغرافي"""
    use_location = st.checkbox("تحديد الموقع الجغرافي تلقائياً", value=True)
    
    if use_location:
        try:
            g = geocoder.ip('me')
            if g.latlng:
                st.success(f"تم تحديد موقعك: {g.latlng[0]}, {g.latlng[1]}")
                return g.latlng[0], g.latlng[1]
        except Exception as e:
            st.warning(f"تعذر تحديد الموقع تلقائياً: {str(e)}")
    
    # الخيار اليدوي إذا فشل التحديد التلقائي
    col1, col2 = st.columns(2)
    with col1:
        lat = st.number_input("خط العرض", min_value=-90.0, max_value=90.0, value=0.0)
    with col2:
        lon = st.number_input("خط الطول", min_value=-180.0, max_value=180.0, value=0.0)
    
    return (lat, lon) if lat != 0.0 and lon != 0.0 else (None, None)

def render_field(field_id: int, label: str, field_type: str, options: str, is_required: bool):
    """عرض حقل إدخال حسب نوعه"""
    required_mark = " *" if is_required else ""
    
    if field_type == 'text':
        return st.text_input(label + required_mark, key=f"text_{field_id}")
    elif field_type == 'number':
        return st.number_input(label + required_mark, key=f"number_{field_id}")
    elif field_type == 'dropdown':
        options_list = json.loads(options) if options else []
        return st.selectbox(label + required_mark, options_list, key=f"dropdown_{field_id}")
    elif field_type == 'checkbox':
        return st.checkbox(label + required_mark, key=f"checkbox_{field_id}")
    elif field_type == 'date':
        return st.date_input(label + required_mark, key=f"date_{field_id}")
    else:
        st.warning(f"نوع الحقل غير معروف: {field_type}")
        return None

def process_survey_submission(
    survey_id: int,
    region_id: int,
    fields: List[Tuple],
    answers: Dict[int, any],
    latitude: Optional[float],
    longitude: Optional[float],
    is_completed: bool,
    survey_name: str
):
    """معالجة إرسال أو حفظ الاستبيان"""
    # التحقق من الحقول المطلوبة
    missing_fields = check_required_fields(fields, answers)
    
    if missing_fields and is_completed:
        st.error(f"الحقول التالية مطلوبة: {', '.join(missing_fields)}")
        return
    
    # حفظ الإجابات في قاعدة البيانات
    response_id = save_response(
        survey_id=survey_id,
        user_id=st.session_state.user_id,
        region_id=region_id,
        is_completed=is_completed,
        latitude=latitude,
        longitude=longitude
    )
    
    if not response_id:
        st.error("حدث خطأ أثناء حفظ البيانات")
        return
    
    # حفظ تفاصيل الإجابات
    save_response_details(response_id, answers)
    
    # عرض رسالة نجاح
    show_submission_message(is_completed, survey_name)

def check_required_fields(fields: List[Tuple], answers: Dict[int, any]) -> List[str]:
    """التحقق من الحقول المطلوبة"""
    missing_fields = []
    for field in fields:
        field_id, label, _, _, is_required, _ = field
        if is_required and not answers.get(field_id):
            missing_fields.append(label)
    return missing_fields

def save_response_details(response_id: int, answers: Dict[int, any]):
    """حفظ تفاصيل الإجابات"""
    for field_id, answer in answers.items():
        if answer is not None:
            save_response_detail(
                response_id=response_id,
                field_id=field_id,
                answer_value=str(answer)
            )

def show_submission_message(is_completed: bool, survey_name: str):
    """عرض رسالة نجاح حسب نوع الحفظ"""
    if is_completed:
        st.success(f"تم إرسال استبيان '{survey_name}' بنجاح")
        st.balloons()
        
        # عرض معلومات الإرسال
        cols = st.columns(3)
        cols[0].info(f"الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        cols[1].info(f"بواسطة: {st.session_state.username}")
        cols[2].info(f"حالة: مكتمل")
    else:
        st.success(f"تم حفظ مسودة استبيان '{survey_name}' بنجاح")
