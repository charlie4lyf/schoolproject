from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Authentication URLs
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    
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
    path('', views.dashboard, name='dashboard'),
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/teacher/', views.teacher_dashboard, name='teacher_dashboard'),
    path('dashboard/student/', views.student_dashboard, name='student_dashboard'),
    path('dashboard/parent/', views.parent_dashboard, name='parent_dashboard'),
    
    # Student Management URLs
    path('students/', views.student_list, name='student_list'),
    path('students/create/', views.student_create, name='student_create'),
    path('students/<int:pk>/', views.student_detail, name='student_detail'),
    path('students/<int:pk>/edit/', views.student_update, name='student_update'),
    path('students/import/', views.student_import, name='student_import'),
    path('students/import/confirm/', views.student_import_confirm, name='student_import_confirm'),
    path('students/import/template/', views.student_csv_template, name='student_csv_template'),
    
    # Teacher Management URLs
    path('teachers/', views.teacher_list, name='teacher_list'),
    path('teachers/create/', views.teacher_create, name='teacher_create'),
    
    # Class Management URLs
    path('classes/', views.class_list, name='class_list'),
    path('classes/create/', views.class_create, name='class_create'),
    path('classes/<int:pk>/', views.class_detail, name='class_detail'),
    path('classes/<int:pk>/edit/', views.class_update, name='class_update'),
    
    # Attendance URLs (Phase 4)
    path('attendance/mark/<int:class_id>/', views.mark_attendance, name='mark_attendance'),
    path('attendance/history/', views.attendance_history, name='attendance_history'),
    path('attendance/date/', views.attendance_by_date, name='attendance_by_date'),
    path('attendance/student/<int:student_id>/', views.student_attendance_report, name='student_attendance_report'),
    path('attendance/class/<int:class_id>/report/', views.class_attendance_report, name='class_attendance_report'),
    path('attendance/class/<int:class_id>/export/', views.export_class_attendance, name='export_class_attendance'),
    
    # Grade Management URLs (Phase 5)
    path('grades/assessment/create/', views.create_assessment, name='create_assessment'),
    path('grades/assessment/<int:assessment_id>/edit/', views.edit_assessment, name='edit_assessment'),
    path('grades/gradebook/<int:class_id>/<int:subject_id>/', views.view_gradebook, name='view_gradebook'),
    path('grades/assessment/<int:assessment_id>/enter/', views.enter_grades, name='enter_grades'),
    path('grades/calculate/<int:class_id>/<int:subject_id>/', views.calculate_term_averages, name='calculate_term_averages'),
    path('grades/my-grades/', views.student_grades_view, name='student_grades_view'),
    
    # Reports URLs (Phase 6)
    path('reports/', views.reports_menu, name='reports_menu'),
    path('reports/generate/', views.generate_report_cards, name='generate_report_cards'),
    path('reports/preview/', views.preview_report_card, name='preview_report_card'),
    path('reports/bulk-generate/', views.bulk_generate_reports, name='bulk_generate_reports'),
    path('reports/grades/', views.grade_reports, name='grade_reports'),
    path('reports/grades/export/', views.export_grade_report, name='export_grade_report'),
    path('reports/students/export/', views.export_student_list, name='export_student_list'),

    # Phase 10: Profile Management
    path('profile/', views.view_profile, name='view_profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/change-password/', views.change_password, name='change_password'),

    # Phase 11: Teacher Management (consolidated)
    path('teachers/add/', views.teacher_create, name='teacher_add'),
    path('teachers/<int:pk>/', views.teacher_detail, name='teacher_detail'),
    path('teachers/<int:pk>/edit/', views.teacher_update, name='teacher_update'),
    path('teachers/<int:pk>/delete/', views.teacher_delete, name='teacher_delete'),
    
    # Assignment Interface
    path('teachers/<int:pk>/assign/', views.teacher_assign_subject, name='teacher_assign_subject'),
    path('teachers/assignment/<int:pk>/delete/', views.delete_assignment, name='delete_assignment'),

    # Phase 12: Assignments
    path('assignments/', views.assignment_list, name='assignment_list'),
    path('assignments/create/', views.create_assignment, name='create_assignment'),
    path('assignments/<int:pk>/', views.assignment_detail, name='assignment_detail'),
    path('assignments/<int:pk>/submit/', views.submit_assignment, name='submit_assignment'),
    path('assignments/<int:pk>/submissions/', views.view_submissions, name='view_submissions'), # For teachers
    path('assignments/submission/<int:pk>/grade/', views.grade_submission, name='grade_submission'),

    # Phase 13: Parent Management
    path('parents/', views.parent_list, name='parent_list'),
    path('parents/add/', views.parent_create, name='parent_create'),
    path('parents/<int:pk>/', views.parent_detail, name='parent_detail'),
    path('parents/<int:pk>/edit/', views.parent_update, name='parent_update'),
    path('parents/<int:pk>/link-student/', views.link_student, name='link_student'),
    path('parents/unlink/<int:pk>/', views.unlink_student, name='unlink_student'),

    # Phase 14: User Management
    path('users/', views.user_list, name='user_list'),
    path('users/add/', views.user_create_admin, name='user_create_admin'), # Specifically for creating admins
    path('users/<int:pk>/edit/', views.user_update, name='user_update'),
    path('users/<int:pk>/toggle-status/', views.toggle_user_status, name='toggle_user_status'),
    path('users/<int:pk>/role/', views.manage_user_role, name='manage_user_role'),

    # Phase 15: System Settings
    path('settings/', views.settings_dashboard, name='settings_dashboard'),
    path('settings/years/', views.academic_year_list, name='academic_year_list'),
    path('settings/years/add/', views.academic_year_manage, name='academic_year_add'),
    path('settings/years/<int:pk>/edit/', views.academic_year_manage, name='academic_year_edit'),
    
    path('settings/terms/', views.term_list, name='term_list'),
    path('settings/terms/add/', views.term_manage, name='term_add'),
    path('settings/terms/<int:pk>/edit/', views.term_manage, name='term_edit'),
    
    path('settings/subjects/', views.subject_list, name='subject_list'),
    path('settings/subjects/add/', views.subject_manage, name='subject_add'),
    path('settings/subjects/<int:pk>/edit/', views.subject_manage, name='subject_edit'),
    path('settings/subjects/<int:pk>/delete/', views.subject_delete, name='subject_delete'),
    
    path('settings/grading-scale/', views.grading_scale, name='grading_scale'),
    path('settings/grading-scale/<int:pk>/delete/', views.grading_scale_delete, name='grading_scale_delete'),
    
    # Phase 17: Reports & Analytics
    path('reports/analytics/', views.analytics_dashboard, name='analytics_dashboard'),
    path('reports/teacher-performance/', views.teacher_performance_report, name='teacher_performance'),
    path('reports/transcript/<int:pk>/', views.student_transcript_view, name='student_transcript'),

    path('settings/grade-subjects/', views.grade_subject_config_list, name='grade_subject_config_list'),
    path('settings/grade-subjects/<str:grade_level>/add/', views.grade_subject_config_add, name='grade_subject_config_add'),
    path('settings/grade-subjects/<int:pk>/edit/', views.grade_subject_config_edit, name='grade_subject_config_edit'),
    path('settings/grade-subjects/<int:pk>/delete/', views.grade_subject_config_delete, name='grade_subject_config_delete'),
    
    # Class Subject Assignment
    path('classes/subjects/', views.class_subject_assignment_list, name='class_subject_list'),
    path('classes/<int:class_id>/subjects/', views.class_subject_assignment_list, name='class_subject_assignment_list'),
    path('classes/<int:class_id>/subjects/assign/', views.class_subject_assign, name='class_subject_assign'),
    path('classes/subjects/<int:assignment_id>/remove/', views.class_subject_remove, name='class_subject_remove'),
    
    # Student Subject Enrollment
    path('student/subjects/', views.student_subjects_view, name='student_subjects_view'),
    path('students/<int:student_id>/subjects/', views.student_subjects_view, name='student_subjects_view_admin'),
    path('students/<int:student_id>/subjects/manage/', views.admin_subject_enrollment, name='admin_subject_enrollment'),
    path('classes/<int:class_id>/bulk-enroll/', views.bulk_form4_subject_enrollment, name='bulk_subject_enrollment'),

    # Parent Grades View
    path('parent/grades/', views.parent_grades_view, name='parent_grades'),

]
