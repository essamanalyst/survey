import streamlit as st
import sqlite3
import json
from datetime import datetime
from database import get_region_name, save_response, save_response_detail

def show_employee_dashboard():
    st.title("لوحة الموظف")
    
    # عرض منطقة العمل
    region_name = get_region_name(st.session_state.region_id)
    st.subheader(f"منطقة العمل: {region_name}")
    
    # عرض الاستبيانات المتاحة
    st.header("الاستبيانات المتاحة")
    
    conn = sqlite3.connect("data/survey_app.db")
    surveys = conn.execute('''
        SELECT s.survey_id, s.survey_name 
        FROM Surveys s
        WHERE s.is_active = 1
    ''').fetchall()
    conn.close()
    
    if not surveys:
        st.info("لا توجد استبيانات متاحة حاليًا")
        return
    
    selected_survey = st.selectbox("اختر استبيان", surveys, format_func=lambda x: x[1])
    
    if selected_survey:
        survey_id = selected_survey[0]
        display_survey(survey_id)

def display_survey(survey_id):
    conn = sqlite3.connect("data/survey_app.db")
    
    # الحصول على حقول الاستبيان
    fields = conn.execute('''
        SELECT field_id, field_label, field_type, field_options, is_required, field_order
        FROM Survey_Fields
        WHERE survey_id = ?
        ORDER BY field_order
    ''', (survey_id,)).fetchall()
    
    # عرض نموذج الاستبيان
    with st.form(f"survey_form_{survey_id}"):
        st.subheader("إدخال البيانات")
        
        answers = {}
        for field in fields:
            field_id, label, field_type, options, is_required, _ = field
            
            # إنشاء حقل الإدخال المناسب
            if field_type == 'text':
                answers[field_id] = st.text_input(
                    label, 
                    key=f"field_{field_id}",
                    value="",
                    help="مطلوب" if is_required else None
                )
            elif field_type == 'number':
                answers[field_id] = st.number_input(
                    label, 
                    key=f"field_{field_id}",
                    value=0,
                    help="مطلوب" if is_required else None
                )
            elif field_type == 'dropdown':
                options_list = json.loads(options) if options else []
                answers[field_id] = st.selectbox(
                    label, 
                    options_list, 
                    key=f"field_{field_id}",
                    help="مطلوب" if is_required else None
                )
            elif field_type == 'checkbox':
                answers[field_id] = st.checkbox(
                    label, 
                    key=f"field_{field_id}",
                    help="مطلوب" if is_required else None
                )
            elif field_type == 'date':
                answers[field_id] = st.date_input(
                    label, 
                    key=f"field_{field_id}",
                    help="مطلوب" if is_required else None
                )
            
            # إضافة علامة (*) للحقول المطلوبة
            if is_required:
                st.markdown("<span style='color:red'>*</span>", unsafe_allow_html=True)
        
        # أزرار الحفظ والإرسال
        submitted = st.form_submit_button("إرسال النموذج")
        save_draft = st.form_submit_button("حفظ مسودة")
        
        if submitted or save_draft:
            # التحقق من الحقول المطلوبة
            missing_fields = []
            for field in fields:
                field_id, label, _, _, is_required, _ = field
                if is_required and (answers.get(field_id) is None or answers.get(field_id) == ""):
                    missing_fields.append(label)
            
            if missing_fields and submitted:
                st.error(f"الحقول التالية مطلوبة: {', '.join(missing_fields)}")
            else:
                # حفظ الإجابات في قاعدة البيانات
                response_id = save_response(
                    survey_id, 
                    st.session_state.user_id, 
                    st.session_state.region_id, 
                    is_completed=submitted
                )
                
                if response_id:
                    for field_id, answer in answers.items():
                        save_response_detail(response_id, field_id, str(answer) if answer is not None else "")
                    
                    if submitted:
                        st.success("تم إرسال النموذج بنجاح")
                    else:
                        st.success("تم حفظ المسودة بنجاح")
                else:
                    st.error("حدث خطأ أثناء حفظ البيانات")

    conn.close()

