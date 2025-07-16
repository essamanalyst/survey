import streamlit as st
import sqlite3
from database import DATABASE_PATH, get_user_by_username, add_governorate_admin, get_health_admins, update_user, update_survey, get_governorates_list, add_user,  save_survey, delete_survey
import json
import pandas as pd

def show_admin_dashboard():
    st.title("لوحة تحكم النظام")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "إدارة المستخدمين",
        "إدارة المحافظات", 
        "إدارة الإدارات الصحية",     
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
    
    # عرض المستخدمين الحاليين
    conn = sqlite3.connect(DATABASE_PATH)
    users = conn.execute('''
    SELECT u.user_id, u.username, u.role, 
           COALESCE(g.governorate_name, ga.governorate_name) as governorate_name, 
           h.admin_name
    FROM Users u
    LEFT JOIN HealthAdministrations h ON u.assigned_region = h.admin_id
    LEFT JOIN Governorates g ON h.governorate_id = g.governorate_id
    LEFT JOIN (
        SELECT ga.user_id, g.governorate_name 
        FROM GovernorateAdmins ga
        JOIN Governorates g ON ga.governorate_id = g.governorate_id
    ) ga ON u.user_id = ga.user_id
    ORDER BY u.user_id
''').fetchall()
    conn.close()
    
    # عرض جدول المستخدمين
    for user in users:
        col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 2, 2, 1, 1])
        with col1:
            st.write(user[1])
        with col2:
            role = "مسؤول نظام" if user[2] == "admin" else "مسؤول محافظة" if user[2] == "governorate_admin" else "موظف"
            st.write(role)
        with col3:
            st.write(user[3] if user[3] else "غير محدد")
        with col4:
            st.write(user[4] if user[4] else "غير محدد")
        with col5:
            if st.button("تعديل", key=f"edit_{user[0]}"):
                st.session_state.editing_user = user[0]
        with col6:
            if st.button("حذف", key=f"delete_{user[0]}"):
                delete_user(user[0])
                st.rerun()
    
    if 'editing_user' in st.session_state:
        edit_user_form(st.session_state.editing_user)
    
    with st.expander("إضافة مستخدم جديد"):
        add_user_form()

def add_user_form():
    conn = sqlite3.connect(DATABASE_PATH)
    governorates = conn.execute("SELECT governorate_id, governorate_name FROM Governorates").fetchall()
    surveys = conn.execute("SELECT survey_id, survey_name FROM Surveys").fetchall()
    conn.close()
    
    with st.form("add_user_form"):
        username = st.text_input("اسم المستخدم")
        password = st.text_input("كلمة المرور", type="password")
        role = st.selectbox("الدور", ["admin", "governorate_admin", "employee"])
        
        # عرض حقول إضافية حسب الدور المحدد
        if role == "governorate_admin":
            selected_gov = st.selectbox(
                "المحافظة",
                options=[g[0] for g in governorates],
                format_func=lambda x: next(g[1] for g in governorates if g[0] == x),
                key="gov_select"
            )
        elif role == "employee":
            selected_gov = st.selectbox(
                "المحافظة",
                options=[g[0] for g in governorates],
                format_func=lambda x: next(g[1] for g in governorates if g[0] == x),
                key="emp_gov_select"
            )
            
            conn = sqlite3.connect(DATABASE_PATH)
            health_admins = conn.execute(
                "SELECT admin_id, admin_name FROM HealthAdministrations WHERE governorate_id=?",
                (selected_gov,)
            ).fetchall()
            conn.close()
            
            selected_admin = st.selectbox(
                "الإدارة الصحية",
                options=[a[0] for a in health_admins],
                format_func=lambda x: next(a[1] for a in health_admins if a[0] == x),
                key="admin_select"
            )
            
            selected_surveys = st.multiselect(
                "الاستبيانات المسموح بها",
                options=[s[0] for s in surveys],
                format_func=lambda x: next(s[1] for s in surveys if s[0] == x),
                key="surveys_select"
            )
        
        submitted = st.form_submit_button("حفظ")
        
        if submitted:
            if username and password:
                if role == "governorate_admin":
                    if add_user(username, password, role):
                        add_governorate_admin(get_user_by_username(username)['user_id'], selected_gov)
                        st.success("تمت إضافة مسؤول المحافظة بنجاح")
                        st.rerun()
                elif role == "employee":
                    if add_user(username, password, role, selected_admin):
                        # حفظ الاستبيانات المسموح بها للموظف
                        pass  # يمكنك إضافة هذه الوظيفة
                        st.success("تمت إضافة الموظف بنجاح")
                        st.rerun()
                else:  # admin role
                    if add_user(username, password, role):
                        st.success("تمت إضافة مسؤول النظام بنجاح")
                        st.rerun()
            else:
                st.warning("يرجى إدخال اسم المستخدم وكلمة المرور")
def edit_user_form(user_id):
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        user = conn.execute('''
            SELECT username, role, assigned_region 
            FROM Users 
            WHERE user_id=?
        ''', (user_id,)).fetchone()
        
        if user is None:
            st.error("المستخدم غير موجود!")
            del st.session_state.editing_user
            return
            
        governorates = conn.execute("SELECT governorate_id, governorate_name FROM Governorates").fetchall()
        
        # الحصول على المحافظة الحالية للمستخدم (إذا كان مسؤول محافظة)
        current_gov = None
        current_admin = user[2]
        if user[1] == 'governorate_admin':
            gov_info = conn.execute('''
                SELECT governorate_id FROM GovernorateAdmins 
                WHERE user_id=?
            ''', (user_id,)).fetchone()
            current_gov = gov_info[0] if gov_info else None
        
    except sqlite3.Error as e:
        st.error(f"حدث خطأ في قاعدة البيانات: {str(e)}")
        return
    finally:
        conn.close()
    
    with st.form(f"edit_user_{user_id}"):
        new_username = st.text_input("اسم المستخدم", value=user[0])
        new_role = st.selectbox(
            "الدور", 
            ["admin", "governorate_admin", "employee"],
            index=["admin", "governorate_admin", "employee"].index(user[1])
        )
        
        # عرض حقول إضافية حسب الدور
        if new_role == "governorate_admin":
            selected_gov = st.selectbox(
                "المحافظة",
                options=[g[0] for g in governorates],
                index=[g[0] for g in governorates].index(current_gov) if current_gov else 0,
                format_func=lambda x: next(g[1] for g in governorates if g[0] == x),
                key=f"gov_edit_{user_id}"
            )
        elif new_role == "employee":
            # عرض حقول الموظف
            selected_gov = st.selectbox(
                "المحافظة",
                options=[g[0] for g in governorates],
                index=[g[0] for g in governorates].index(current_gov) if current_gov else 0,
                format_func=lambda x: next(g[1] for g in governorates if g[0] == x),
                key=f"emp_gov_{user_id}"
            )
            
            conn = sqlite3.connect(DATABASE_PATH)
            health_admins = conn.execute(
                "SELECT admin_id, admin_name FROM HealthAdministrations WHERE governorate_id=?",
                (selected_gov,)
            ).fetchall()
            conn.close()
            
            # Fix: Handle case where current_admin is not in health_admins
            admin_options = [a[0] for a in health_admins]
            try:
                admin_index = admin_options.index(current_admin) if current_admin else 0
            except ValueError:
                admin_index = 0
            
            selected_admin = st.selectbox(
                "الإدارة الصحية",
                options=admin_options,
                index=admin_index,
                format_func=lambda x: next(a[1] for a in health_admins if a[0] == x),
                key=f"admin_edit_{user_id}"
            )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("حفظ التعديلات"):
                if new_role == "governorate_admin":
                    # تحديث بيانات مسؤول المحافظة
                    update_user(user_id, new_username, new_role)
                    conn = sqlite3.connect(DATABASE_PATH)
                    try:
                        # حذف أي تعيينات سابقة
                        conn.execute("DELETE FROM GovernorateAdmins WHERE user_id=?", (user_id,))
                        # إضافة التعيين الجديد
                        conn.execute(
                            "INSERT INTO GovernorateAdmins (user_id, governorate_id) VALUES (?, ?)",
                            (user_id, selected_gov)
                        )
                        conn.commit()
                    finally:
                        conn.close()
                else:
                    update_user(user_id, new_username, new_role, selected_admin if new_role == "employee" else None)
                del st.session_state.editing_user
                st.rerun()
        with col2:
            if st.form_submit_button("إلغاء"):
                del st.session_state.editing_user
                st.rerun()

def delete_user(user_id):
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        # التحقق من وجود إجابات مرتبطة بالمستخدم
        has_responses = conn.execute("SELECT 1 FROM Responses WHERE user_id=?", (user_id,)).fetchone()
        if has_responses:
            st.error("لا يمكن حذف المستخدم لأنه لديه إجابات مسجلة!")
            return False
        
        conn.execute("DELETE FROM Users WHERE user_id=?", (user_id,))
        conn.commit()
        st.success("تم حذف المستخدم بنجاح")
        return True
    except sqlite3.Error as e:
        st.error(f"حدث خطأ أثناء الحذف: {str(e)}")
        return False
    finally:
        conn.close()

def manage_surveys():
    st.header("إدارة الاستبيانات")
    
    # Display existing surveys
    conn = sqlite3.connect(DATABASE_PATH)
    surveys = conn.execute("SELECT survey_id, survey_name, created_at, is_active FROM Surveys").fetchall()
    conn.close()
    
    # عرض الاستبيانات مع أزرار الإدارة
    for survey in surveys:
        col1, col2, col3, col4 = st.columns([4, 2, 1, 1])
        with col1:
            st.write(f"**{survey[1]}** (تم الإنشاء في {survey[2]})")
        with col2:
            status = "نشط" if survey[3] else "غير نشط"
            st.write(f"الحالة: {status}")
        with col3:
            if st.button("تعديل", key=f"edit_survey_{survey[0]}"):
                st.session_state.editing_survey = survey[0]
        with col4:
            if st.button("حذف", key=f"delete_survey_{survey[0]}"):
                delete_survey(survey[0])
                st.rerun()
    
    # معالجة تعديل الاستبيان
    if 'editing_survey' in st.session_state:
        edit_survey(st.session_state.editing_survey)
    
    # إنشاء استبيان جديد
    with st.expander("إنشاء استبيان جديد"):
        create_survey_form()

def edit_survey(survey_id):
    conn = sqlite3.connect(DATABASE_PATH)
    
    # الحصول على بيانات الاستبيان
    survey = conn.execute("SELECT survey_name, is_active FROM Surveys WHERE survey_id=?", (survey_id,)).fetchone()
    
    # الحصول على حقول الاستبيان
    fields = conn.execute('''
        SELECT field_id, field_label, field_type, field_options, is_required, field_order
        FROM Survey_Fields
        WHERE survey_id = ?
        ORDER BY field_order
    ''', (survey_id,)).fetchall()
    
    conn.close()
    
    with st.form(f"edit_survey_{survey_id}"):
        st.subheader("تعديل الاستبيان")
        
        # اسم الاستبيان وحالته
        new_name = st.text_input("اسم الاستبيان", value=survey[0])
        is_active = st.checkbox("نشط", value=bool(survey[1]))
        
        # عرض الحقول الحالية للتعديل
        st.subheader("حقول الاستبيان")
        
        updated_fields = []
        for field in fields:
            field_id = field[0]
            with st.expander(f"حقل: {field[1]} (نوع: {field[2]})"):
                col1, col2 = st.columns(2)
                with col1:
                    new_label = st.text_input("تسمية الحقل", value=field[1], key=f"label_{field_id}")
                    new_type = st.selectbox(
                        "نوع الحقل",
                        ["text", "number", "dropdown", "checkbox", "date"],
                        index=["text", "number", "dropdown", "checkbox", "date"].index(field[2]),
                        key=f"type_{field_id}"
                    )
                with col2:
                    new_required = st.checkbox("مطلوب", value=bool(field[4]), key=f"required_{field_id}")
                    if new_type == 'dropdown':
                        options = "\n".join(json.loads(field[3])) if field[3] else ""
                        new_options = st.text_area(
                            "خيارات القائمة المنسدلة (سطر لكل خيار)",
                            value=options,
                            key=f"options_{field_id}"
                        )
                    else:
                        new_options = None
                
                updated_fields.append({
                    'field_id': field_id,
                    'field_label': new_label,
                    'field_type': new_type,
                    'field_options': [opt.strip() for opt in new_options.split('\n')] if new_options else None,
                    'is_required': new_required
                })
        
        # أزرار الإدارة
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("حفظ التعديلات"):
                update_survey(survey_id, new_name, is_active, updated_fields)
                del st.session_state.editing_survey
                st.rerun()
        with col2:
            if st.form_submit_button("إلغاء"):
                del st.session_state.editing_survey
                st.rerun()

def create_survey_form():
    if 'create_survey_fields' not in st.session_state:
        st.session_state.create_survey_fields = []
    
    with st.form("create_survey_form"):
        survey_name = st.text_input("اسم الاستبيان")
        
        # إدارة الحقول
        st.subheader("حقول الاستبيان")
        
        for i, field in enumerate(st.session_state.create_survey_fields):
            st.subheader(f"الحقل {i+1}")
            col1, col2 = st.columns(2)
            with col1:
                field['field_label'] = st.text_input("تسمية الحقل", value=field.get('field_label', ''), key=f"new_label_{i}")
                field['field_type'] = st.selectbox(
                    "نوع الحقل",
                    ["text", "number", "dropdown", "checkbox", "date"],
                    index=["text", "number", "dropdown", "checkbox", "date"].index(field.get('field_type', 'text')),
                    key=f"new_type_{i}"
                )
            with col2:
                field['is_required'] = st.checkbox("مطلوب", value=field.get('is_required', False), key=f"new_required_{i}")
                if field['field_type'] == 'dropdown':
                    options = st.text_area(
                        "خيارات القائمة المنسدلة (سطر لكل خيار)",
                        value="\n".join(field.get('field_options', [])),
                        key=f"new_options_{i}"
                    )
                    field['field_options'] = [opt.strip() for opt in options.split('\n') if opt.strip()]
        
        # أزرار إدارة الحقول
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.form_submit_button("إضافة حقل جديد"):
                st.session_state.create_survey_fields.append({
                    'field_label': '',
                    'field_type': 'text',
                    'is_required': False,
                    'field_options': []
                })
        with col2:
            if st.form_submit_button("حذف آخر حقل") and st.session_state.create_survey_fields:
                st.session_state.create_survey_fields.pop()
        with col3:
            if st.form_submit_button("حفظ الاستبيان") and survey_name:
                save_survey(survey_name, st.session_state.create_survey_fields)
                st.session_state.create_survey_fields = []
                st.rerun()

def display_survey_data(survey_id):
    """عرض بيانات استجابات الاستبيان"""
    conn = sqlite3.connect(DATABASE_PATH)
    
    try:
        # الحصول على اسم الاستبيان
        survey_name = conn.execute(
            "SELECT survey_name FROM Surveys WHERE survey_id = ?", 
            (survey_id,)
        ).fetchone()
        
        if not survey_name:
            st.error("الاستبيان المحدد غير موجود")
            return
            
        survey_name = survey_name[0]
        st.subheader(f"بيانات الاستبيان: {survey_name}")

        # الحصول على عدد الإجابات
        total_responses = conn.execute(
            "SELECT COUNT(*) FROM Responses WHERE survey_id = ?", 
            (survey_id,)
        ).fetchone()[0]

        if total_responses == 0:
            st.info("لا توجد بيانات متاحة لهذا الاستبيان بعد")
            return

        # الحصول على جميع الإجابات
        responses = conn.execute('''
            SELECT r.response_id, u.username, h.admin_name, 
                   r.submission_date, r.is_completed
            FROM Responses r
            JOIN Users u ON r.user_id = u.user_id
            JOIN HealthAdministrations h ON r.region_id = h.admin_id
            WHERE r.survey_id = ?
            ORDER BY r.submission_date DESC
        ''', (survey_id,)).fetchall()

        # عرض الإحصائيات
        completed_responses = sum(1 for r in responses if r[4])
        regions_count = len(set(r[2] for r in responses))

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("إجمالي الإجابات", total_responses)
        with col2:
            st.metric("الإجابات المكتملة", completed_responses)
        with col3:
            st.metric("عدد المناطق", regions_count)

        # تحضير البيانات للعرض في DataFrame
        df = pd.DataFrame(
            [(r[0], r[1], r[2], r[3], "مكتملة" if r[4] else "مسودة") for r in responses],
            columns=["ID", "المستخدم", "المنطقة", "تاريخ التقديم", "الحالة"]
        )
        
        # عرض البيانات
        st.dataframe(df)

        # زر تصدير إلى Excel
        if st.button("تصدير إلى Excel"):
            # إنشاء اسم ملف مناسب
            import re
            from io import BytesIO
            
            filename = re.sub(r'[^\w\-_]', '_', survey_name) + ".xlsx"
            
            # إنشاء ملف Excel في الذاكرة
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            
            # تقديم ملف للتنزيل
            st.download_button(
                label="تنزيل ملف Excel",
                data=output.getvalue(),
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            st.success("تم إنشاء ملف Excel بنجاح")

        # عرض تفاصيل إجابة محددة
        response_ids = [r[0] for r in responses]
        selected_response_id = st.selectbox(
            "اختر إجابة لعرض تفاصيلها",
            options=response_ids,
            format_func=lambda x: f"إجابة #{x}"
        )

        if selected_response_id:
            details = conn.execute('''
                SELECT sf.field_label, rd.answer_value
                FROM Response_Details rd
                JOIN Survey_Fields sf ON rd.field_id = sf.field_id
                WHERE rd.response_id = ?
                ORDER BY sf.field_order
            ''', (selected_response_id,)).fetchall()

            st.subheader("تفاصيل الإجابة المحددة")
            for field, answer in details:
                st.write(f"**{field}:** {answer if answer else 'غير مدخل'}")

    except sqlite3.Error as e:
        st.error(f"حدث خطأ في قاعدة البيانات: {str(e)}")
    finally:
        conn.close()
        
def view_data():
    st.header("عرض البيانات المجمعة")
    
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        surveys = conn.execute(
            "SELECT survey_id, survey_name FROM Surveys ORDER BY survey_name"
        ).fetchall()
        
        if not surveys:
            st.warning("لا توجد استبيانات متاحة")
            return
            
        selected_survey = st.selectbox(
            "اختر استبيان",
            surveys,
            format_func=lambda x: x[1],
            key="survey_select"
        )
        
        if selected_survey:
            display_survey_data(selected_survey[0])
    except sqlite3.Error as e:
        st.error(f"حدث خطأ في قاعدة البيانات: {str(e)}")
    finally:
        conn.close()

def manage_governorates():
    st.header("إدارة المحافظات")
    conn = sqlite3.connect(DATABASE_PATH)
    governorates = conn.execute("SELECT governorate_id, governorate_name, description FROM Governorates").fetchall()
    conn.close()
    
    for gov in governorates:
        col1, col2, col3, col4 = st.columns([4, 3, 1, 1])
        with col1:
            st.write(f"**{gov[1]}**")
        with col2:
            st.write(gov[2] if gov[2] else "لا يوجد وصف")
        with col3:
            if st.button("تعديل", key=f"edit_gov_{gov[0]}"):
                st.session_state.editing_gov = gov[0]
        with col4:
            if st.button("حذف", key=f"delete_gov_{gov[0]}"):
                delete_governorate(gov[0])
                st.rerun()
    
    if 'editing_gov' in st.session_state:
        edit_governorate(st.session_state.editing_gov)
    
    with st.expander("إضافة محافظة جديدة"):
        with st.form("add_governorate_form"):
            governorate_name = st.text_input("اسم المحافظة")
            description = st.text_area("الوصف")
            
            submitted = st.form_submit_button("حفظ")
            
            if submitted:
                if governorate_name:
                    conn = sqlite3.connect(DATABASE_PATH)
                    try:
                        existing = conn.execute("SELECT 1 FROM Governorates WHERE governorate_name=?", 
                                              (governorate_name,)).fetchone()
                        if existing:
                            st.error("هذه المحافظة موجودة بالفعل!")
                        else:
                            conn.execute(
                                "INSERT INTO Governorates (governorate_name, description) VALUES (?, ?)",
                                (governorate_name, description)
                            )
                            conn.commit()
                            st.success("تمت إضافة المحافظة بنجاح")
                            st.rerun()
                    except sqlite3.Error as e:
                        st.error(f"حدث خطأ: {str(e)}")
                    finally:
                        conn.close()
                else:
                    st.warning("يرجى إدخال اسم المحافظة")

def edit_governorate(gov_id):
    conn = sqlite3.connect(DATABASE_PATH)
    gov = conn.execute("SELECT governorate_name, description FROM Governorates WHERE governorate_id=?", 
                      (gov_id,)).fetchone()
    conn.close()
    
    with st.form(f"edit_gov_{gov_id}"):
        new_name = st.text_input("اسم المحافظة", value=gov[0])
        new_desc = st.text_area("الوصف", value=gov[1] if gov[1] else "")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("حفظ التعديلات"):
                conn = sqlite3.connect(DATABASE_PATH)
                try:
                    existing = conn.execute("SELECT 1 FROM Governorates WHERE governorate_name=? AND governorate_id!=?", 
                                          (new_name, gov_id)).fetchone()
                    if existing:
                        st.error("هذا الاسم مستخدم بالفعل لمحافظة أخرى!")
                    else:
                        conn.execute(
                            "UPDATE Governorates SET governorate_name=?, description=? WHERE governorate_id=?",
                            (new_name, new_desc, gov_id)
                        )
                        conn.commit()
                        st.success("تم تحديث المحافظة بنجاح")
                        del st.session_state.editing_gov
                        st.rerun()
                except sqlite3.Error as e:
                    st.error(f"حدث خطأ: {str(e)}")
                finally:
                    conn.close()
        with col2:
            if st.form_submit_button("إلغاء"):
                del st.session_state.editing_gov
                st.rerun()

def delete_governorate(gov_id):
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        has_regions = conn.execute("SELECT 1 FROM HealthAdministrations WHERE governorate_id=?", 
                                 (gov_id,)).fetchone()
        if has_regions:
            st.error("لا يمكن حذف المحافظة لأنها تحتوي على إدارات صحية!")
            return False
        
        conn.execute("DELETE FROM Governorates WHERE governorate_id=?", (gov_id,))
        conn.commit()
        st.success("تم حذف المحافظة بنجاح")
        return True
    except sqlite3.Error as e:
        st.error(f"حدث خطأ أثناء الحذف: {str(e)}")
        return False
    finally:
        conn.close()

def manage_regions():
    st.header("إدارة الإدارات الصحية")
    
    conn = sqlite3.connect(DATABASE_PATH)
    regions = conn.execute('''
        SELECT h.admin_id, h.admin_name, h.description, g.governorate_name 
        FROM HealthAdministrations h
        JOIN Governorates g ON h.governorate_id = g.governorate_id
    ''').fetchall()
    conn.close()
    for reg in regions:
        col1, col2, col3, col4, col5 = st.columns([3, 3, 2, 1, 1])
        with col1:
            st.write(f"**{reg[1]}**")
        with col2:
            st.write(reg[2] if reg[2] else "لا يوجد وصف")
        with col3:
            st.write(reg[3])
        with col4:
            if st.button("تعديل", key=f"edit_reg_{reg[0]}"):
                st.session_state.editing_reg = reg[0]
        with col5:
            if st.button("حذف", key=f"delete_reg_{reg[0]}"):
                delete_health_admin(reg[0])
                st.rerun()
    if 'editing_reg' in st.session_state:
        edit_health_admin(st.session_state.editing_reg)
    
    with st.expander("إضافة إدارة صحية جديدة"):
        conn = sqlite3.connect(DATABASE_PATH)
        governorates = conn.execute("SELECT governorate_id, governorate_name FROM Governorates").fetchall()
        conn.close()
        
        if not governorates:
            st.warning("لا توجد محافظات متاحة. يرجى إضافة محافظة أولاً.")
            return
            
        with st.form("add_health_admin_form"):
            admin_name = st.text_input("اسم الإدارة الصحية")
            description = st.text_area("الوصف")
            governorate_id = st.selectbox(
                "المحافظة",
                options=[g[0] for g in governorates],
                format_func=lambda x: next(g[1] for g in governorates if g[0] == x))
            
            submitted = st.form_submit_button("حفظ")
            
            if submitted:
                if admin_name:
                    conn = sqlite3.connect(DATABASE_PATH)
                    try:
                        existing = conn.execute('''
                            SELECT 1 FROM HealthAdministrations 
                            WHERE admin_name=? AND governorate_id=?
                        ''', (admin_name, governorate_id)).fetchone()
                        
                        if existing:
                            st.error("هذه الإدارة الصحية موجودة بالفعل في هذه المحافظة!")
                        else:
                            conn.execute(
                                "INSERT INTO HealthAdministrations (admin_name, description, governorate_id) VALUES (?, ?, ?)",
                                (admin_name, description, governorate_id)
                            )
                            conn.commit()
                            st.success("تمت إضافة الإدارة الصحية بنجاح")
                            st.rerun()
                    except sqlite3.Error as e:
                        st.error(f"حدث خطأ: {str(e)}")
                    finally:
                        conn.close()
                else:
                    st.warning("يرجى إدخال اسم الإدارة الصحية")

def edit_health_admin(admin_id):
    conn = sqlite3.connect(DATABASE_PATH)
    admin = conn.execute('''
        SELECT h.admin_name, h.description, h.governorate_id, g.governorate_name
        FROM HealthAdministrations h
        JOIN Governorates g ON h.governorate_id = g.governorate_id
        WHERE h.admin_id=?
    ''', (admin_id,)).fetchone()
    conn.close()
    
    # Check if admin exists
    if admin is None:
        st.error("الإدارة الصحية المطلوبة غير موجودة!")
        del st.session_state.editing_reg
        return
    
    governorates = get_governorates_list()
    
    with st.form(f"edit_admin_{admin_id}"):
        new_name = st.text_input("اسم الإدارة الصحية", value=admin[0])
        new_desc = st.text_area("الوصف", value=admin[1] if admin[1] else "")
        new_gov = st.selectbox(
            "المحافظة",
            options=[g[0] for g in governorates],
            index=[g[0] for g in governorates].index(admin[2]),
            format_func=lambda x: next(g[1] for g in governorates if g[0] == x))
        
        col1, col2 = st.columns(2)
        with col1:
            if st.form_submit_button("حفظ التعديلات"):
                conn = sqlite3.connect(DATABASE_PATH)
                try:
                    existing = conn.execute('''
                        SELECT 1 FROM HealthAdministrations 
                        WHERE admin_name=? AND governorate_id=? AND admin_id!=?
                    ''', (new_name, new_gov, admin_id)).fetchone()
                    
                    if existing:
                        st.error("هذا الاسم مستخدم بالفعل لإدارة صحية أخرى في هذه المحافظة!")
                    else:
                        conn.execute(
                            "UPDATE HealthAdministrations SET admin_name=?, description=?, governorate_id=? WHERE admin_id=?",
                            (new_name, new_desc, new_gov, admin_id)
                        )
                        conn.commit()
                        st.success("تم تحديث الإدارة الصحية بنجاح")
                        del st.session_state.editing_reg
                        st.rerun()
                except sqlite3.Error as e:
                    st.error(f"حدث خطأ: {str(e)}")
                finally:
                    conn.close()
        with col2:
            if st.form_submit_button("إلغاء"):
                del st.session_state.editing_reg
                st.rerun()

def delete_health_admin(admin_id):
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        has_users = conn.execute("SELECT 1 FROM Users WHERE assigned_region=?", 
                               (admin_id,)).fetchone()
        if has_users:
            st.error("لا يمكن حذف الإدارة الصحية لأنها مرتبطة بمستخدمين!")
            return False
        
        conn.execute("DELETE FROM HealthAdministrations WHERE admin_id=?", (admin_id,))
        conn.commit()
        st.success("تم حذف الإدارة الصحية بنجاح")
        return True
    except sqlite3.Error as e:
        st.error(f"حدث خطأ أثناء الحذف: {str(e)}")
        return False
    finally:
        conn.close()
        
     
