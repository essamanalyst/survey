import streamlit as st
import sqlite3
from database import DATABASE_PATH, get_regions, add_user, add_region, save_survey, delete_survey

def show_admin_dashboard():
    st.title("لوحة تحكم المسؤول")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "إدارة المستخدمين",
        "إدارة المحافظات", 
        "إدارة المناطق",     
        "إدارة الاستبيانات", 
        "عرض البيانات"
    ])
    
    with tab1:
        manage_users()
    
    with tab2:
        manage_governorates()
    
    with tab3:
        manage_regions()
    
    with tab4:
        manage_surveys()
    
    with tab5:
        view_data()

def manage_users():
    st.header("إدارة المستخدمين")
    
    # Display existing users
    conn = sqlite3.connect(DATABASE_PATH)
    users = conn.execute("SELECT user_id, username, role, assigned_region FROM Users").fetchall()
    conn.close()
    
    st.dataframe(users, use_container_width=True)
    
    # Add new user section
    with st.expander("إضافة مستخدم جديد"):
        # Initialize form state
        if 'add_user_form_cleared' not in st.session_state:
            st.session_state.add_user_form_cleared = False
        
        with st.form("add_user_form"):
            # Conditional field rendering
            if st.session_state.add_user_form_cleared:
                username = st.text_input("اسم المستخدم", value="")
                password = st.text_input("كلمة المرور", type="password", value="")
                st.session_state.add_user_form_cleared = False
            else:
                username = st.text_input("اسم المستخدم")
                password = st.text_input("كلمة المرور", type="password")
            
            role = st.selectbox("الدور", ["admin", "employee"])
            
            regions = get_regions()
            region_options = {r[0]: r[1] for r in regions}
            selected_region_id = st.selectbox(
                "المنطقة",
                options=list(region_options.keys()),
                format_func=lambda x: region_options[x]
            )
            
            submitted = st.form_submit_button("حفظ")
            
        if submitted:
            if username and password:  # Validate inputs
                if add_user(username, password, role, selected_region_id):
                    st.success("تمت إضافة المستخدم بنجاح")
                    st.session_state.add_user_form_cleared = True
            else:
                st.warning("يرجى إدخال اسم المستخدم وكلمة المرور")
        
        # Manual refresh button
        if st.button("تحديث القائمة"):
            st.rerun()
            


def manage_surveys():
    st.header("إدارة الاستبيانات")
    
    # Display existing surveys
    conn = sqlite3.connect(DATABASE_PATH)
    surveys = conn.execute("SELECT survey_id, survey_name, created_at, is_active FROM Surveys").fetchall()
    conn.close()
    
    st.dataframe(surveys, use_container_width=True)
    
    # Create new survey section
    with st.expander("إنشاء استبيان جديد"):
        if 'create_survey_form_cleared' not in st.session_state:
            st.session_state.create_survey_form_cleared = False
            st.session_state.fields = []
        
        with st.form("create_survey_form"):
            if st.session_state.create_survey_form_cleared:
                survey_name = st.text_input("اسم الاستبيان", value="")
                st.session_state.create_survey_form_cleared = False
            else:
                survey_name = st.text_input("اسم الاستبيان")
            
            # Dynamic fields management
            for i, field in enumerate(st.session_state.fields):
                st.subheader(f"الحقل {i+1}")
                col1, col2 = st.columns(2)
                with col1:
                    field['field_label'] = st.text_input("تسمية الحقل", value=field.get('field_label', ''), key=f"label_{i}")
                    field['field_type'] = st.selectbox(
                        "نوع الحقل",
                        ["text", "number", "dropdown", "checkbox", "date"],
                        index=["text", "number", "dropdown", "checkbox", "date"].index(field.get('field_type', 'text')),
                        key=f"type_{i}"
                    )
                with col2:
                    field['is_required'] = st.checkbox("مطلوب", value=field.get('is_required', False), key=f"required_{i}")
                    if field['field_type'] == 'dropdown':
                        options = st.text_area("خيارات القائمة المنسدلة (سطر لكل خيار)", value="\n".join(field.get('field_options', [])))
                        field['field_options'] = [opt.strip() for opt in options.split('\n') if opt.strip()]
            
            # Field management buttons
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("إضافة حقل جديد"):
                    st.session_state.fields.append({
                        'field_label': '',
                        'field_type': 'text',
                        'is_required': False,
                        'field_options': []
                    })
            with col2:
                if st.form_submit_button("حذف آخر حقل") and st.session_state.fields:
                    st.session_state.fields.pop()
            
            # Save survey button
            if st.form_submit_button("حفظ الاستبيان") and survey_name:
                save_survey(survey_name, st.session_state.fields)
                st.success("تم حفظ الاستبيان بنجاح")
                st.session_state.create_survey_form_cleared = True
                st.session_state.fields = []
        
        # Manual refresh button
        if st.button("تحديث القائمة", key="refresh_surveys"):
            st.rerun()
def display_survey_data(survey_id):
    """Display survey response data for the selected survey"""
    conn = sqlite3.connect(DATABASE_PATH)
    
    # Get survey name
    survey_name = conn.execute(
        "SELECT survey_name FROM Surveys WHERE survey_id = ?", 
        (survey_id,)
    ).fetchone()[0]
    
    st.subheader(f"بيانات الاستبيان: {survey_name}")
    
    # Get all responses for this survey
    responses = conn.execute('''
        SELECT r.response_id, u.username, reg.region_name, 
               r.submission_date, r.is_completed
        FROM Responses r
        JOIN Users u ON r.user_id = u.user_id
        JOIN Regions reg ON r.region_id = reg.region_id
        WHERE r.survey_id = ?
        ORDER BY r.submission_date DESC
    ''', (survey_id,)).fetchall()
    
    if not responses:
        st.info("لا توجد بيانات متاحة لهذا الاستبيان بعد")
        return
    
    # Display summary statistics
    total_responses = len(responses)
    completed_responses = sum(1 for r in responses if r[4])  # is_completed is at index 4
    regions_count = len(set(r[2] for r in responses))  # region_name is at index 2
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("إجمالي الإجابات", total_responses)
    with col2:
        st.metric("الإجابات المكتملة", completed_responses)
    with col3:
        st.metric("عدد المناطق", regions_count)
    
    # Display responses table
    st.subheader("تفاصيل الإجابات")
    st.dataframe(responses, use_container_width=True)
    
    # Allow drilling down into individual responses
    selected_response = st.selectbox(
        "اختر إجابة لعرض تفاصيلها",
        responses,
        format_func=lambda x: f"بواسطة {x[1]} (منطقة {x[2]}) في {x[3]}"
    )
    
    if selected_response:
        response_id = selected_response[0]
        details = conn.execute('''
            SELECT sf.field_label, rd.answer_value
            FROM Response_Details rd
            JOIN Survey_Fields sf ON rd.field_id = sf.field_id
            WHERE rd.response_id = ?
            ORDER BY sf.field_order
        ''', (response_id,)).fetchall()
        
        st.subheader("تفاصيل الإجابة المحددة")
        for field_label, answer_value in details:
            st.write(f"**{field_label}:** {answer_value}")
    
    conn.close()
def view_data():
    st.header("عرض البيانات المجمعة")
    
    # اختيار الاستبيان لعرض بياناته
    conn = sqlite3.connect("data/survey_app.db")
    surveys = conn.execute("SELECT survey_id, survey_name FROM Surveys").fetchall()
    conn.close()
    
    survey_id = st.selectbox("اختر استبيان", surveys, format_func=lambda x: x[1])
    
    if survey_id:
        survey_id = survey_id[0]
        display_survey_data(survey_id)

def manage_governorates():
    st.header("إدارة المحافظات")
    
    # عرض المحافظات الموجودة
    conn = sqlite3.connect(DATABASE_PATH)
    governorates = conn.execute("SELECT governorate_id, governorate_name, description FROM Governorates").fetchall()
    conn.close()
    
    st.dataframe(governorates, use_container_width=True)
    
    # إضافة محافظة جديدة
    with st.expander("إضافة محافظة جديدة"):
        with st.form("add_governorate_form"):
            governorate_name = st.text_input("اسم المحافظة")
            description = st.text_area("الوصف")
            
            submitted = st.form_submit_button("حفظ")
            
        if submitted:
            if governorate_name:
                conn = sqlite3.connect(DATABASE_PATH)
                try:
                    conn.execute(
                        "INSERT INTO Governorates (governorate_name, description) VALUES (?, ?)",
                        (governorate_name, description)
                    )
                    conn.commit()
                    st.success("تمت إضافة المحافظة بنجاح")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("هذه المحافظة موجودة بالفعل!")
                finally:
                    conn.close()
            else:
                st.warning("يرجى إدخال اسم المحافظة")

def manage_regions():
    st.header("إدارة المناطق")
    
    # عرض المناطق الموجودة مع محافظاتها
    conn = sqlite3.connect(DATABASE_PATH)
    regions = conn.execute('''
        SELECT r.region_id, r.region_name, r.description, g.governorate_name 
        FROM Regions r
        JOIN Governorates g ON r.governorate_id = g.governorate_id
    ''').fetchall()
    conn.close()
    
    st.dataframe(regions, use_container_width=True)
    
    # إضافة منطقة جديدة
    with st.expander("إضافة منطقة جديدة"):
        conn = sqlite3.connect(DATABASE_PATH)
        governorates = conn.execute("SELECT governorate_id, governorate_name FROM Governorates").fetchall()
        conn.close()
        
        if not governorates:
            st.warning("لا توجد محافظات متاحة. يرجى إضافة محافظة أولاً.")
            return
            
        with st.form("add_region_form"):
            region_name = st.text_input("اسم المنطقة")
            description = st.text_area("الوصف")
            governorate_id = st.selectbox(
                "المحافظة",
                options=[g[0] for g in governorates],
                format_func=lambda x: next(g[1] for g in governorates if g[0] == x))
            
            submitted = st.form_submit_button("حفظ")
            
        if submitted:
            if region_name:
                conn = sqlite3.connect(DATABASE_PATH)
                try:
                    conn.execute(
                        "INSERT INTO Regions (region_name, description, governorate_id) VALUES (?, ?, ?)",
                        (region_name, description, governorate_id)
                    )
                    conn.commit()
                    st.success("تمت إضافة المنطقة بنجاح")
                    st.rerun()
                except sqlite3.Error as e:
                    st.error(f"حدث خطأ: {str(e)}")
                finally:
                    conn.close()
            else:
                st.warning("يرجى إدخال اسم المنطقة")

