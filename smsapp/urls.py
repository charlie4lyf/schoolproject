from django.urls import path
from django.contrib.auth import views as auth_views
from .views import auth, dashboards, students, teachers, classes, attendance, grading, reports, profiles, assignments, parents, users, settings, analytics

urlpatterns = [
    # Authentication URLs
    path('login/', auth.user_login, name='login'),
    path('logout/', auth.user_logout, name='logout'),
    
    # Password reset URLs
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(template_name='registration/password_reset_form.html'),
         name='password_reset'),
    
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'),
         name='password_reset_done'),
    
    path('password-reset-confirm/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'),
         name='password_reset_confirm'),
    
    path('password-reset-complete/', 
         auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'),
         name='password_reset_complete'),
    
    # Dashboard URLs
    path('', dashboards.dashboard, name='dashboard'),
    path('dashboard/admin/', dashboards.admin_dashboard, name='admin_dashboard'),
    path('dashboard/teacher/', dashboards.teacher_dashboard, name='teacher_dashboard'),
    path('dashboard/student/', dashboards.student_dashboard, name='student_dashboard'),
    path('dashboard/parent/', dashboards.parent_dashboard, name='parent_dashboard'),
    
    # Student Management URLs
    path('students/', students.student_list, name='student_list'),
    path('students/create/', students.student_create, name='student_create'),
    path('students/<int:pk>/', students.student_detail, name='student_detail'),
    path('students/<int:pk>/edit/', students.student_update, name='student_update'),
    path('students/<int:pk>/promote/', students.promote_student, name='promote_student'),
    path('students/import/', students.student_import, name='student_import'),
    path('students/import/confirm/', students.student_import_confirm, name='student_import_confirm'),
    path('students/import/template/', students.student_csv_template, name='student_csv_template'),
    
    # Teacher Management URLs
    path('teachers/', teachers.teacher_list, name='teacher_list'),
    path('teachers/create/', teachers.teacher_create, name='teacher_create'),
    
    # Class Management URLs
    path('classes/', classes.class_list, name='class_list'),
    path('classes/create/', classes.class_create, name='class_create'),
    path('classes/<int:pk>/', classes.class_detail, name='class_detail'),
    path('classes/<int:pk>/edit/', classes.class_update, name='class_update'),
    
    # Attendance URLs
    path('attendance/mark/<int:class_id>/', attendance.mark_attendance, name='mark_attendance'),
    path('attendance/history/', attendance.attendance_history, name='attendance_history'),
    path('attendance/date/', attendance.attendance_by_date, name='attendance_by_date'),
    path('attendance/student/<int:student_id>/', attendance.student_attendance_report, name='student_attendance_report'),
    path('attendance/class/<int:class_id>/report/', attendance.class_attendance_report, name='class_attendance_report'),
    path('attendance/class/<int:class_id>/export/', attendance.export_class_attendance, name='export_class_attendance'),
    
    # Grade Management URLs
    path('grades/assessment/create/', grading.create_assessment, name='create_assessment'),
    path('grades/assessment/<int:assessment_id>/edit/', grading.edit_assessment, name='edit_assessment'),
    path('grades/gradebook/<int:class_id>/<int:subject_id>/', grading.view_gradebook, name='view_gradebook'),
    path('grades/assessment/<int:assessment_id>/enter/', grading.enter_grades, name='enter_grades'),
    path('grades/calculate/<int:class_id>/<int:subject_id>/', grading.calculate_term_averages, name='calculate_term_averages'),
    path('grades/my-grades/', grading.student_grades_view, name='student_grades_view'),
    
    # Reports URLs
    path('reports/', reports.reports_menu, name='reports_menu'),
    path('reports/generate/', reports.generate_report_cards, name='generate_report_cards'),
    path('reports/preview/', reports.preview_report_card, name='preview_report_card'),
    path('reports/bulk-generate/', reports.bulk_generate_reports, name='bulk_generate_reports'),
    path('reports/grades/', reports.grade_reports, name='grade_reports'),
    path('reports/grades/export/', reports.export_grade_report, name='export_grade_report'),
    path('reports/students/export/', reports.export_student_list, name='export_student_list'),

    # Profile Management
    path('profile/', profiles.view_profile, name='view_profile'),
    path('profile/edit/', profiles.edit_profile, name='edit_profile'),
    path('profile/change-password/', profiles.change_password, name='change_password'),

    # Teacher Management (consolidated)
    path('teachers/add/', teachers.teacher_create, name='teacher_add'),
    path('teachers/<int:pk>/', teachers.teacher_detail, name='teacher_detail'),
    path('teachers/<int:pk>/edit/', teachers.teacher_update, name='teacher_update'),
    path('teachers/<int:pk>/delete/', teachers.teacher_delete, name='teacher_delete'),
    
    # Assignment Interface
    path('teachers/<int:pk>/assign/', teachers.teacher_assign_subject, name='teacher_assign_subject'),
    path('teachers/assignment/<int:pk>/delete/', teachers.delete_assignment, name='delete_assignment'),

    # Assignments
    path('assignments/', assignments.assignment_list, name='assignment_list'),
    path('assignments/create/', assignments.create_assignment, name='create_assignment'),
    path('assignments/<int:pk>/', assignments.assignment_detail, name='assignment_detail'),
    path('assignments/<int:pk>/submit/', assignments.submit_assignment, name='submit_assignment'),
    path('assignments/<int:pk>/submissions/', assignments.view_submissions, name='view_submissions'),
    path('assignments/submission/<int:pk>/grade/', assignments.grade_submission, name='grade_submission'),

    # Parent Management
    path('parents/', parents.parent_list, name='parent_list'),
    path('parents/add/', parents.parent_create, name='parent_create'),
    path('parents/<int:pk>/', parents.parent_detail, name='parent_detail'),
    path('parents/<int:pk>/edit/', parents.parent_update, name='parent_update'),
    path('parents/<int:pk>/link-student/', parents.link_student, name='link_student'),
    path('parents/unlink/<int:pk>/', parents.unlink_student, name='unlink_student'),

    # User Management
    path('users/', users.user_list, name='user_list'),
    path('users/add/', users.user_create_admin, name='user_create_admin'),
    path('users/<int:pk>/edit/', users.user_update, name='user_update'),
    path('users/<int:pk>/toggle-status/', users.toggle_user_status, name='toggle_user_status'),
    path('users/<int:pk>/role/', users.manage_user_role, name='manage_user_role'),

    # System Settings
    path('settings/', settings.settings_dashboard, name='settings_dashboard'),
    path('settings/years/', settings.academic_year_list, name='academic_year_list'),
    path('settings/years/add/', settings.academic_year_manage, name='academic_year_add'),
    path('settings/years/<int:pk>/edit/', settings.academic_year_manage, name='academic_year_edit'),
    
    path('settings/terms/', settings.term_list, name='term_list'),
    path('settings/terms/add/', settings.term_manage, name='term_add'),
    path('settings/terms/<int:pk>/edit/', settings.term_manage, name='term_edit'),
    
    path('settings/subjects/', settings.subject_list, name='subject_list'),
    path('settings/subjects/add/', settings.subject_manage, name='subject_add'),
    path('settings/subjects/<int:pk>/edit/', settings.subject_manage, name='subject_edit'),
    path('settings/subjects/<int:pk>/delete/', settings.subject_delete, name='subject_delete'),
    
    path('settings/grading-scale/', settings.grading_scale, name='grading_scale'),
    path('settings/grading-scale/<int:pk>/delete/', settings.grading_scale_delete, name='grading_scale_delete'),
    
    # Reports & Analytics
    path('reports/analytics/', analytics.analytics_dashboard, name='analytics_dashboard'),
    path('reports/teacher-performance/', analytics.teacher_performance_report, name='teacher_performance'),
    path('reports/transcript/<int:pk>/', analytics.student_transcript_view, name='student_transcript'),

    path('settings/grade-subjects/', settings.grade_subject_config_list, name='grade_subject_config_list'),
    path('settings/grade-subjects/<str:grade_level>/add/', settings.grade_subject_config_add, name='grade_subject_config_add'),
    path('settings/grade-subjects/<int:pk>/edit/', settings.grade_subject_config_edit, name='grade_subject_config_edit'),
    path('settings/grade-subjects/<int:pk>/delete/', settings.grade_subject_config_delete, name='grade_subject_config_delete'),
    
    # Class Subject Assignment
    path('classes/subjects/', settings.class_subject_assignment_list, name='class_subject_list'),
    path('classes/<int:class_id>/subjects/', settings.class_subject_assignment_list, name='class_subject_assignment_list'),
    path('classes/<int:class_id>/subjects/assign/', settings.class_subject_assign, name='class_subject_assign'),
    path('classes/subjects/<int:assignment_id>/remove/', settings.class_subject_remove, name='class_subject_remove'),

    # Bulk Grade-Level Teacher Assignment
    path('settings/bulk-teacher-assignment/', teachers.bulk_grade_teacher_assignment, name='bulk_grade_teacher_assignment'),
    
    # Parent Grades View
    path('parent/grades/', grading.parent_grades_view, name='parent_grades'),
]
