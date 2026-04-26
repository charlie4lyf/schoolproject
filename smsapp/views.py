import uuid
from django.db import models
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q, Avg, Max, Min
from django.utils import timezone
from datetime import datetime, timedelta
from django.http import HttpResponse
from django.core.paginator import Paginator
from decimal import Decimal
from collections import defaultdict, Counter
import csv
import json
import io
import zipfile
import openpyxl
from openpyxl.styles import Font, PatternFill
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER

from .models import (
    AcademicYear, Assessment, Grade, ReportCard, StudentEnrollment,
    User, Student, Teacher, Parent, SchoolClass, Subject,
    ClassSubjectTeacher, Attendance,
    ActivityLog, Term, ParentStudent, Assignment,
    AssignmentSubmission, GradingScale, GradeSubjectConfig
)
from .utils import get_term_subject_mark, get_grade_letter
from .decorators import admin_required, teacher_required, student_required, parent_required
from .forms import (
    GRADE_CHOICES, ClassSubjectTeacherForm, StudentForm, ClassForm, TeacherAssignmentForm, TeacherForm,
    AssessmentForm, UserProfileForm, StudentProfileForm,
    TeacherProfileForm, ParentProfileForm, CustomPasswordChangeForm,
    AssignmentForm, StudentSubmissionForm, GradingForm,
    ParentForm, ParentStudentLinkForm, UserAdminForm, RoleChangeForm,
    AcademicYearForm, TermForm, SubjectForm, GradingScaleForm,
    GradeSubjectConfigForm, GradeLevelTeacherAssignmentForm
)

from django.db import transaction
from django.http import JsonResponse


# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

def user_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            if not remember_me:
                request.session.set_expiry(0)
            messages.success(request, f'Welcome back, {user.get_full_name()}!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'registration/login.html')


def user_logout(request):
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('login')


@login_required
def dashboard(request):
    user = request.user
    role_redirect = {
        'admin':   'admin_dashboard',
        'teacher': 'teacher_dashboard',
        'student': 'student_dashboard',
        'parent':  'parent_dashboard',
    }
    target = role_redirect.get(user.role)
    if target:
        return redirect(target)
    messages.error(request, 'Invalid user role.')
    return redirect('login')


# ─────────────────────────────────────────────
# DASHBOARDS
# ─────────────────────────────────────────────

@login_required
@admin_required
def admin_dashboard(request):
    today = timezone.now().date()
    total_students = Student.objects.filter(is_active=True).count()
    total_teachers = Teacher.objects.filter(is_active=True).count()
    total_classes = SchoolClass.objects.count()

    if total_students > 0:
        present_count = Attendance.objects.filter(date=today, status='present').count()
        attendance_percentage = round((present_count / total_students) * 100, 1)
    else:
        attendance_percentage = 0

    recent_activities = ActivityLog.objects.select_related('user').order_by('-timestamp')[:10]

    context = {
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_classes': total_classes,
        'attendance_percentage': attendance_percentage,
        'recent_activities': recent_activities,
    }
    return render(request, 'dashboard/admin_dashboard.html', context)


@login_required
@teacher_required
def teacher_dashboard(request):
    try:
        teacher = request.user.teacher_profile
    except Teacher.DoesNotExist:
        messages.error(request, 'Teacher profile not found. Please contact admin.')
        return redirect('login')

    teaching_assignments = ClassSubjectTeacher.objects.filter(
        teacher=teacher
    ).select_related('class_assigned', 'subject', 'academic_year')

    today = timezone.now().date()
    marked_class_ids = set(
        Attendance.objects.filter(
            class_assigned_id__in=teaching_assignments.values_list('class_assigned_id', flat=True),
            date=today,
        ).values_list('class_assigned_id', flat=True)
    )
    attendance_pending = [a for a in teaching_assignments if a.class_assigned_id not in marked_class_ids]

    total_students = sum(a.class_assigned.student_count for a in teaching_assignments)  # <-- added

    context = {
        'teacher': teacher,
        'teaching_assignments': teaching_assignments,
        'attendance_pending': attendance_pending,
        'total_students': total_students,  # <-- added
    }
    return render(request, 'dashboard/teacher_dashboard.html', context)

@login_required
@student_required
def student_dashboard(request):
    try:
        student = request.user.student_profile
    except Student.DoesNotExist:
        messages.error(request, 'Student profile not found. Please contact admin.')
        return redirect('login')

    current_term = Term.objects.filter(is_active=True).first()
    grades = []
    if current_term and student.current_class:
        subject_ids = Assessment.objects.filter(
            term=current_term,
            class_assigned=student.current_class,
        ).values_list('subject_id', flat=True).distinct()
        for subject_id in subject_ids:
            from .models import Subject
            subject = Subject.objects.get(pk=subject_id)
            mark = get_term_subject_mark(student, subject, current_term)
            if mark is not None:
                grades.append({
                    'subject': subject,
                    'average_score': mark,
                    'grade_letter': get_grade_letter(mark),
                })

    total_days = Attendance.objects.filter(student=student).count()
    if total_days > 0:
        present_days = Attendance.objects.filter(
            student=student, status__in=['present', 'late']
        ).count()
        attendance_percentage = round((present_days / total_days) * 100, 1)
    else:
        attendance_percentage = 0

    recent_attendance = Attendance.objects.filter(student=student).order_by('-date')[:10]

    context = {
        'student': student,
        'grades': grades,
        'attendance_percentage': attendance_percentage,
        'recent_attendance': recent_attendance,
    }
    return render(request, 'dashboard/student_dashboard.html', context)


@login_required
@parent_required
def parent_dashboard(request):
    try:
        parent = request.user.parent_profile
    except Parent.DoesNotExist:
        messages.error(request, 'Parent profile not found. Please contact admin.')
        return redirect('login')

    parent_student_links = ParentStudent.objects.filter(
        parent=parent
    ).select_related('student__user').prefetch_related('student__enrollments', 'student__enrollments__class_assigned')

    current_term = Term.objects.filter(is_active=True).first()
    children = []
    student_ids = [link.student_id for link in parent_student_links]

    attendance_stats = {
        row['student_id']: row
        for row in Attendance.objects.filter(student_id__in=student_ids).values('student_id').annotate(
            total_days=Count('id'),
            present_days=Count('id', filter=Q(status__in=['present', 'late'])),
        )
    }
    recent_attendance_rows = Attendance.objects.filter(
        student_id__in=student_ids
    ).values('student_id', 'status').order_by('student_id', '-date')
    consecutive_absences_by_student = {}
    streak_closed = set()
    for row in recent_attendance_rows:
        student_id = row['student_id']
        if student_id in streak_closed:
            continue
        if row['status'] == 'absent':
            consecutive_absences_by_student[student_id] = consecutive_absences_by_student.get(student_id, 0) + 1
        else:
            consecutive_absences_by_student[student_id] = consecutive_absences_by_student.get(student_id, 0)
            streak_closed.add(student_id)
    grades_by_student = defaultdict(list)
    if current_term:
        for student_id in student_ids:
            from .models import Subject
            student_obj = Student.objects.get(pk=student_id)
            if student_obj.current_class:
                subject_ids = Assessment.objects.filter(
                    term=current_term,
                    class_assigned=student_obj.current_class,
                ).values_list('subject_id', flat=True).distinct()
                subject_marks = []
                for subject_id in subject_ids:
                    subject = Subject.objects.get(pk=subject_id)
                    mark = get_term_subject_mark(student_obj, subject, current_term)
                    if mark is not None:
                        subject_marks.append({
                            'subject': subject,
                            'average_score': mark,
                            'grade_letter': get_grade_letter(mark),
                        })
                subject_marks.sort(key=lambda x: x['average_score'], reverse=True)
                grades_by_student[student_id] = subject_marks[:5]

    for link in parent_student_links:
        student = link.student
        stats = attendance_stats.get(student.id, {})
        total_days = stats.get('total_days', 0)
        if total_days > 0:
            present_days = stats.get('present_days', 0)
            absent_days = total_days - present_days
            attendance_percentage = round((present_days / total_days) * 100, 1)
        else:
            present_days = absent_days = 0
            attendance_percentage = 0

        consecutive_absences = consecutive_absences_by_student.get(student.id, 0)

        grades = grades_by_student.get(student.id, [])

        children.append({
            'student': student,
            'relationship': link.relationship,
            'attendance_percentage': attendance_percentage,
            'days_present': present_days,
            'days_absent': absent_days,
            'consecutive_absences': consecutive_absences,
            'grades': grades,
        })

    context = {
        'parent': parent,
        'children': children,
    }
    return render(request, 'dashboard/parent_dashboard.html', context)

# ─────────────────────────────────────────────
# STUDENT MANAGEMENT
# ─────────────────────────────────────────────

@login_required
@admin_required
def student_list(request):
    # Use prefetch_related for enrollments since current_class is a property
    students = Student.objects.filter(is_active=True).prefetch_related('enrollments', 'enrollments__class_assigned')

    search_query = request.GET.get('search', '')
    if search_query:
        students = students.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(student_id_number__icontains=search_query) |
            Q(user__email__icontains=search_query)
        )

    class_filter = request.GET.get('class', '')
    if class_filter:
        # Filter through enrollments since current_class is a property
        students = students.filter(enrollments__class_assigned_id=class_filter, enrollments__is_active=True)

    status_filter = request.GET.get('status', '')
    if status_filter == 'inactive':
        students = Student.objects.filter(is_active=False).prefetch_related('enrollments', 'enrollments__class_assigned')

    students = students.select_related('user').order_by('user__last_name', 'user__first_name')

    paginator = Paginator(students, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    classes = SchoolClass.objects.all().order_by('name')

    context = {
        'students': page_obj,
        'page_obj': page_obj,
        'classes': classes,
        'search_query': search_query,
        'class_filter': class_filter,
        'status_filter': status_filter,
    }
    return render(request, 'students/student_list.html', context)


@login_required
@admin_required
def student_detail(request, pk):
    student = get_object_or_404(Student.objects.select_related('user').prefetch_related('enrollments', 'enrollments__class_assigned'), pk=pk)

    total_attendance = Attendance.objects.filter(student=student).count()
    if total_attendance > 0:
        present_count = Attendance.objects.filter(
            student=student, status__in=['present', 'late']
        ).count()
        days_present = present_count
        days_absent = total_attendance - present_count
        attendance_percentage = round((present_count / total_attendance) * 100, 1)
    else:
        days_present = days_absent = 0
        attendance_percentage = 0

    current_term = Term.objects.filter(is_active=True).first()
    current_average = 0
    if current_term and student.current_class:
        subject_ids = Assessment.objects.filter(
            term=current_term,
            class_assigned=student.current_class,
        ).values_list('subject_id', flat=True).distinct()
        marks = []
        for subject_id in subject_ids:
            from .models import Subject
            subject = Subject.objects.get(pk=subject_id)
            mark = get_term_subject_mark(student, subject, current_term)
            if mark is not None:
                marks.append(mark)
        if marks:
            current_average = round(sum(marks) / len(marks), 1)

    parents = ParentStudent.objects.filter(student=student).select_related('parent__user')

    context = {
        'student': student,
        'attendance_percentage': attendance_percentage,
        'days_present': days_present,
        'days_absent': days_absent,
        'current_average': current_average,
        'parents': parents,
    }
    return render(request, 'students/student_detail.html', context)


@login_required
@admin_required
def student_create(request):
    if request.method == 'POST':
        form = StudentForm(request.POST)
        if form.is_valid():
            # Create User — username auto-generated by User.save() since role != 'admin'
            user = User.objects.create_user(
                username= User.generate_username('student'),  
                email=form.cleaned_data['email'],
                password='student123',
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                role='student',
            )
            # Re-fetch to get the auto-generated username
            user.refresh_from_db()

            student = Student.objects.create(
                user=user,
                date_of_birth=form.cleaned_data['date_of_birth'],
                gender=form.cleaned_data['gender'],
                emergency_contact_name=form.cleaned_data['emergency_contact_name'],
                emergency_contact_phone=form.cleaned_data['emergency_contact_phone'],
                emergency_contact_relationship=form.cleaned_data['emergency_contact_relationship'],
                blood_group=form.cleaned_data.get('blood_group', ''),
                allergies=form.cleaned_data.get('allergies', ''),
                medical_notes=form.cleaned_data.get('medical_notes', ''),
                is_active=form.cleaned_data.get('is_active', True),
            )

            # Create enrollment for the student
            current_class = form.cleaned_data.get('current_class')
            if current_class:
                StudentEnrollment.objects.create(
                    student=student,
                    class_assigned=current_class,
                    academic_year=current_class.academic_year,
                    is_active=True,
                )

            messages.success(request, f'Student {student.user.get_full_name()} created successfully!')
            return redirect('student_detail', pk=student.id)
    else:
        form = StudentForm()

    context = {
        'form': form,
        'classes': SchoolClass.objects.all().order_by('name'),
        'student': None,
    }
    return render(request, 'students/student_form.html', context)


@login_required
@admin_required
def student_update(request, pk):
    student = get_object_or_404(Student.objects.select_related('user'), pk=pk)

    if request.method == 'POST':
        form = StudentForm(request.POST, instance=student)
        if form.is_valid():
            u = student.user
            u.first_name = form.cleaned_data['first_name']
            u.last_name  = form.cleaned_data['last_name']
            u.email      = form.cleaned_data['email']
            u.save()

            student.date_of_birth                  = form.cleaned_data['date_of_birth']
            student.gender                         = form.cleaned_data['gender']
            student.emergency_contact_name         = form.cleaned_data['emergency_contact_name']
            student.emergency_contact_phone        = form.cleaned_data['emergency_contact_phone']
            student.emergency_contact_relationship = form.cleaned_data['emergency_contact_relationship']
            student.blood_group                    = form.cleaned_data.get('blood_group', '')
            student.allergies                      = form.cleaned_data.get('allergies', '')
            student.medical_notes                  = form.cleaned_data.get('medical_notes', '')
            student.is_active                      = form.cleaned_data.get('is_active', True)
            student.save()

            # Update or create enrollment
            current_class = form.cleaned_data.get('current_class')
            if current_class:
                StudentEnrollment.objects.update_or_create(
                    student=student,
                    academic_year=current_class.academic_year,
                    defaults={'class_assigned': current_class, 'is_active': True}
                )

            messages.success(request, f'Student {student.user.get_full_name()} updated successfully!')
            return redirect('student_detail', pk=student.id)
    else:
        form = StudentForm(instance=student)

    context = {
        'form': form,
        'classes': SchoolClass.objects.all().order_by('name'),
        'student': student,
    }
    return render(request, 'students/student_form.html', context)


@login_required
@admin_required
def student_import(request):
    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']
        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'Please upload a valid CSV file.')
            return redirect('student_import')

        try:
            decoded_file = csv_file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)
            preview_data, errors = [], []

            for row_num, row in enumerate(reader, start=2):
                required_fields = [
                    'first_name', 'last_name', 'email',
                    'date_of_birth', 'gender', 'class_name',
                ]
                is_valid = True
                for field in required_fields:
                    if not row.get(field):
                        errors.append(f'Row {row_num}: Missing {field}')
                        is_valid = False

                if row.get('class_name') and not SchoolClass.objects.filter(name=row['class_name']).exists():
                    errors.append(f'Row {row_num}: Class "{row["class_name"]}" not found')
                    is_valid = False

                # FIX: only M and F are valid — 'O' removed
                if row.get('gender') not in ['M', 'F']:
                    errors.append(f'Row {row_num}: Gender must be M or F')
                    is_valid = False

                row['is_valid'] = is_valid
                preview_data.append(row)

            context = {
                'preview_data': preview_data,
                'errors': errors,
                'csv_data_json': json.dumps(preview_data),
            }
            return render(request, 'students/student_import.html', context)

        except Exception as e:
            messages.error(request, f'Error reading CSV file: {str(e)}')
            return redirect('student_import')

    return render(request, 'students/student_import.html')


@login_required
@admin_required
def student_import_confirm(request):
    if request.method == 'POST':
        csv_data_json = request.POST.get('csv_data')
        if not csv_data_json:
            messages.error(request, 'No data to import.')
            return redirect('student_import')

        try:
            csv_data = json.loads(csv_data_json)
            imported_count = 0

            for row in csv_data:
                if not row.get('is_valid'):
                    continue
                if User.objects.filter(email=row['email']).exists():
                    continue

                current_class = SchoolClass.objects.filter(name=row['class_name']).first()
                if not current_class:
                    continue

                user = User.objects.create_user(
                    username='',
                    email=row['email'],
                    password='student123',
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    role='student',
                )

                student = Student.objects.create(
                    user=user,
                    date_of_birth=row['date_of_birth'],
                    gender=row['gender'],
                    emergency_contact_name=row.get('emergency_contact_name', ''),
                    emergency_contact_phone=row.get('emergency_contact_phone', ''),
                    emergency_contact_relationship=row.get('emergency_contact_relationship', 'Parent'),
                    blood_group=row.get('blood_group', ''),
                    allergies=row.get('allergies', ''),
                    medical_notes=row.get('medical_notes', ''),
                )
                
                # Create enrollment
                StudentEnrollment.objects.create(
                    student=student,
                    class_assigned=current_class,
                    academic_year=current_class.academic_year,
                    is_active=True,
                )
                imported_count += 1

            messages.success(request, f'Successfully imported {imported_count} students!')
            return redirect('student_list')

        except Exception as e:
            messages.error(request, f'Error importing students: {str(e)}')
            return redirect('student_import')

    return redirect('student_import')


@login_required
@admin_required
def student_csv_template(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="student_import_template.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'first_name', 'last_name', 'email',
        'date_of_birth', 'gender', 'class_name',
        'emergency_contact_name', 'emergency_contact_phone', 'emergency_contact_relationship',
        'blood_group', 'allergies', 'medical_notes',
    ])
    writer.writerow([
        'John', 'Doe', 'john.doe@student.com',
        '2010-05-15', 'M', 'Form 1A',
        'Jane Doe', '1234567890', 'Mother',
        'O+', 'None', 'No medical issues',
    ])
    return response


# ─────────────────────────────────────────────
# CLASS MANAGEMENT
# ─────────────────────────────────────────────

# Add/Update these in your views.py

@login_required
@admin_required
def class_list(request):
    """List all classes with their details"""
    from django.db.models import Count
    
    # Get all classes with annotations instead of setting properties
    classes = SchoolClass.objects.select_related(
        'academic_year', 
        'class_teacher__user'
    ).annotate(
        # Annotate with counts directly
        total_students=Count('enrollments', filter=models.Q(enrollments__is_active=True), distinct=True),
        total_subjects=Count('subject_assignments', distinct=True)
    ).order_by('-academic_year', 'grade_level', 'name')
    
    # Debug output
    print(f"Total classes: {classes.count()}")
    for class_obj in classes:
        print(f"Class: {class_obj.name}")
        print(f"  - Students: {class_obj.total_students}")
        print(f"  - Subjects: {class_obj.total_subjects}")
    
    return render(request, 'classes/class_list.html', {'classes': classes})


@login_required
@admin_required
def class_create(request):
    """Create a new class"""
    if request.method == 'POST':
        form = ClassForm(request.POST)
        if form.is_valid():
            class_obj = form.save()

            # Auto-populate subjects from GradeSubjectConfig for this grade level
            configs = GradeSubjectConfig.objects.filter(grade_level=class_obj.grade_level)
            for config in configs:
                ClassSubjectTeacher.objects.get_or_create(
                    class_assigned=class_obj,
                    subject=config.subject,
                    academic_year=class_obj.academic_year,
                    defaults={'teacher': None}
                )

            # Log the activity
            ActivityLog.objects.create(
                user=request.user,
                action='create',
                model_name='Class',
                object_id=class_obj.id,
                description=f'Created class {class_obj.name}'
            )

            messages.success(
                request,
                f'Class {class_obj.name} created successfully! {configs.count()} subjects auto-populated from grade configuration.'
            )
            return redirect('class_detail', pk=class_obj.id)
    else:
        form = ClassForm()
        
        # Pre-select active academic year
        active_year = AcademicYear.objects.filter(is_active=True).first()
        if active_year:
            form.fields['academic_year'].initial = active_year

    context = {
        'form': form,
        'academic_years': AcademicYear.objects.all().order_by('-start_date'),
        'teachers': Teacher.objects.filter(is_active=True).select_related('user'),
        'class': None,
        'title': 'Create New Class'
    }
    return render(request, 'classes/class_form.html', context)


@login_required
@admin_required
def class_update(request, pk):
    """Update an existing class"""
    class_obj = get_object_or_404(SchoolClass, pk=pk)

    if request.method == 'POST':
        form = ClassForm(request.POST, instance=class_obj)
        if form.is_valid():
            form.save()
            
            ActivityLog.objects.create(
                user=request.user,
                action='update',
                model_name='Class',
                object_id=class_obj.id,
                description=f'Updated class {class_obj.name}'
            )
            
            messages.success(request, f'Class {class_obj.name} updated successfully!')
            return redirect('class_detail', pk=class_obj.id)
    else:
        form = ClassForm(instance=class_obj)

    context = {
        'form': form,
        'academic_years': AcademicYear.objects.all().order_by('-start_date'),
        'teachers': Teacher.objects.filter(is_active=True).select_related('user'),
        'class': class_obj,
        'title': f'Edit Class: {class_obj.name}'
    }
    return render(request, 'classes/class_form.html', context)


@login_required
@admin_required
def class_detail(request, pk):
    """View class details including students and subject assignments"""
    class_obj = get_object_or_404(
        SchoolClass.objects.select_related('academic_year', 'class_teacher__user'), 
        pk=pk
    )
    
    # Get students in this class (through enrollments since current_class is a property)
    students = Student.objects.filter(
        enrollments__class_assigned=class_obj,
        enrollments__is_active=True,
        is_active=True
    ).select_related('user').order_by('user__last_name', 'user__first_name')
    
    # Get subject assignments with teachers
    subject_assignments = ClassSubjectTeacher.objects.filter(
        class_assigned=class_obj
    ).select_related('subject', 'teacher__user', 'academic_year').order_by('subject__name')
    
    # Get compulsory subjects for this grade level
    compulsory_subjects = GradeSubjectConfig.objects.filter(
        grade_level=class_obj.grade_level,
        is_compulsory=True
    ).select_related('subject')
    
    # Get elective subjects available for this grade level
    elective_subjects = GradeSubjectConfig.objects.filter(
        grade_level=class_obj.grade_level,
        is_elective=True
    ).select_related('subject')
    
    context = {
        'class': class_obj,
        'students': students,
        'subject_assignments': subject_assignments,
        'compulsory_subjects': compulsory_subjects,
        'elective_subjects': elective_subjects,
        'student_count': students.count(),
        'subject_count': subject_assignments.count(),
    }
    return render(request, 'classes/class_detail.html', context)


@login_required
@admin_required
def class_delete(request, pk):
    """Delete or archive a class"""
    class_obj = get_object_or_404(SchoolClass, pk=pk)
    
    # Check if class has students
    if class_obj.student_count > 0:
        messages.error(request, f'Cannot delete {class_obj.name} because it has {class_obj.student_count} students. Remove students first.')
        return redirect('class_detail', pk=pk)
    
    if request.method == 'POST':
        class_name = class_obj.name
        class_obj.delete()
        
        ActivityLog.objects.create(
            user=request.user,
            action='delete',
            model_name='Class',
            description=f'Deleted class {class_name}'
        )
        
        messages.success(request, f'Class {class_name} deleted successfully!')
        return redirect('class_list')
    
    return render(request, 'classes/class_confirm_delete.html', {'class': class_obj})


@login_required
@admin_required
def class_student_enrollment(request, class_id):
    """Enroll students into a class"""
    class_obj = get_object_or_404(SchoolClass, pk=class_id)
    
    # Get students not already in this class (through enrollments)
    enrolled_students = StudentEnrollment.objects.filter(
        class_assigned=class_obj, is_active=True
    ).values_list('student_id', flat=True)
    available_students = Student.objects.filter(
        is_active=True
    ).exclude(
        id__in=enrolled_students
    ).select_related('user').order_by('user__last_name', 'user__first_name')
    
    if request.method == 'POST':
        student_ids = request.POST.getlist('students')
        if student_ids:
            for student_id in student_ids:
                student = Student.objects.get(id=student_id)
                
                # Create enrollment record (current_class is now a property)
                StudentEnrollment.objects.get_or_create(
                    student=student,
                    academic_year=class_obj.academic_year,
                    defaults={'class_assigned': class_obj, 'is_active': True}
                )
            
            messages.success(request, f'{len(student_ids)} students enrolled in {class_obj.name}')
            return redirect('class_detail', pk=class_id)
    
    context = {
        'class': class_obj,
        'available_students': available_students,
    }
    return render(request, 'classes/class_enroll_students.html', context)


@login_required
@admin_required
def class_remove_student(request, class_id, student_id):
    """Remove a student from a class"""
    class_obj = get_object_or_404(SchoolClass, pk=class_id)
    student = get_object_or_404(Student, pk=student_id)
    
    # Check if student is enrolled in this class
    enrollment = StudentEnrollment.objects.filter(
        student=student, class_assigned=class_obj, is_active=True
    ).first()
    
    if not enrollment:
        messages.error(request, 'Student is not enrolled in this class.')
        return redirect('class_detail', pk=class_id)
    
    if request.method == 'POST':
        # Deactivate the enrollment instead of setting current_class
        enrollment.is_active = False
        enrollment.save()
        
        messages.success(request, f'{student.user.get_full_name()} removed from {class_obj.name}')
        return redirect('class_detail', pk=class_id)
    
    return render(request, 'classes/class_remove_student.html', {
        'class': class_obj,
        'student': student
    })


@login_required
@admin_required
def class_subject_assignment(request, class_id):
    """Assign subjects to a class (auto-populate based on grade level)"""
    class_obj = get_object_or_404(SchoolClass, pk=class_id)
    academic_year = class_obj.academic_year
    
    # Get subject configuration for this grade level
    subject_configs = GradeSubjectConfig.objects.filter(
        grade_level=class_obj.grade_level
    ).select_related('subject')
    
    # Get already assigned subjects
    assigned_subjects = ClassSubjectTeacher.objects.filter(
        class_assigned=class_obj,
        academic_year=academic_year
    ).values_list('subject_id', flat=True)
    
    if request.method == 'POST':
        # Auto-assign all configured subjects (compulsory + elective)
        created_count = 0
        for config in subject_configs:
            if config.subject.id not in assigned_subjects:
                ClassSubjectTeacher.objects.create(
                    class_assigned=class_obj,
                    subject=config.subject,
                    academic_year=academic_year,
                    teacher=None  # To be assigned later
                )
                created_count += 1

        messages.success(
            request,
            f'{created_count} subjects auto-assigned to {class_obj.name} from grade configuration.'
        )
        return redirect('class_detail', pk=class_id)
    
    context = {
        'class': class_obj,
        'configured_subjects': subject_configs,
        'assigned_count': len(assigned_subjects),
        'total_configured': subject_configs.count(),
    }
    return render(request, 'classes/class_auto_assign_subjects.html', context)


# ─────────────────────────────────────────────
# TEACHER MANAGEMENT
# ─────────────────────────────────────────────

@login_required
@admin_required
def teacher_list(request):
    teachers = Teacher.objects.filter(is_active=True).select_related('user')

    search_query = request.GET.get('search', '')
    if search_query:
        teachers = teachers.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(employee_id__icontains=search_query) |
            Q(user__email__icontains=search_query)
        )

    teachers = teachers.annotate(
        assignment_count=Count('teaching_assignments')
    ).order_by('user__last_name')

    return render(request, 'teachers/teacher_list.html', {
        'teachers': teachers,
        'search_query': search_query,
    })


@login_required
@admin_required
def teacher_create(request):
    if request.method == 'POST':
        form = TeacherForm(request.POST)
        if form.is_valid():
            try:
                user = User.objects.create_user(
                    username=User.generate_username('teacher'),
                    email=form.cleaned_data['email'],
                    password='teacher123',
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    phone=form.cleaned_data.get('phone', ''),
                    role='teacher',
                    is_active = True
                )
                teacher = form.save(commit=False)
                teacher.user = user
                teacher.is_active = True
                teacher.save()
                messages.success(request, f'Teacher {user.get_full_name()} created successfully!')
                return redirect('teacher_detail', pk=teacher.pk)
            except Exception as e:
                messages.error(request, f'Error creating teacher: {str(e)}')
    else:
        form = TeacherForm()

    return render(request, 'teachers/teacher_form.html', {'form': form, 'title': 'Add Teacher'})


@login_required
@admin_required
def teacher_detail(request, pk):
    teacher = get_object_or_404(Teacher.objects.select_related('user'), pk=pk)
    assignments = ClassSubjectTeacher.objects.filter(
        teacher=teacher
    ).select_related('class_assigned', 'subject', 'academic_year').order_by('academic_year', 'class_assigned')
    class_teacher_of = SchoolClass.objects.filter(class_teacher=teacher)

    return render(request, 'teachers/teacher_detail.html', {
        'teacher': teacher,
        'assignments': assignments,
        'class_teacher_of': class_teacher_of,
    })


@login_required
@admin_required
def teacher_update(request, pk):
    teacher = get_object_or_404(Teacher.objects.select_related('user'), pk=pk)

    if request.method == 'POST':
        form = TeacherForm(request.POST, instance=teacher)
        if form.is_valid():
            u = teacher.user
            u.first_name = form.cleaned_data['first_name']
            u.last_name  = form.cleaned_data['last_name']
            u.email      = form.cleaned_data['email']
            u.phone      = form.cleaned_data.get('phone', '')
            u.save()
            form.save()
            messages.success(request, 'Teacher profile updated successfully!')
            return redirect('teacher_detail', pk=teacher.pk)
    else:
        form = TeacherForm(instance=teacher, initial={
            'first_name': teacher.user.first_name,
            'last_name':  teacher.user.last_name,
            'email':      teacher.user.email,
            'phone':      teacher.user.phone,
        })

    return render(request, 'teachers/teacher_form.html', {
        'form': form,
        'title': 'Edit Teacher',
        'teacher': teacher,
    })


@login_required
@admin_required
def teacher_delete(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)
    if request.method == 'POST':
        teacher.is_active = False
        teacher.user.is_active = False
        teacher.user.save()
        teacher.save()
        messages.success(request, 'Teacher deactivated successfully.')
        return redirect('teacher_list')
    return render(request, 'teachers/teacher_confirm_delete.html', {'teacher': teacher})


@login_required
@admin_required
def teacher_assign_subject(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)

    if request.method == 'POST':
        form = TeacherAssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.teacher = teacher

            # Validate that the subject is configured for this class's grade level
            is_configured = GradeSubjectConfig.objects.filter(
                grade_level=assignment.class_assigned.grade_level,
                subject=assignment.subject
            ).exists()
            if not is_configured:
                messages.error(
                    request,
                    f'"{assignment.subject.name}" is not configured for {assignment.class_assigned.grade_level}. '
                    f'Add it to Grade-Subject Config first.'
                )
                return redirect('teacher_assign_subject', pk=pk)

            exists = ClassSubjectTeacher.objects.filter(
                class_assigned=assignment.class_assigned,
                subject=assignment.subject,
                academic_year=assignment.academic_year,
            ).exists()

            if exists:
                messages.error(request, 'This subject is already assigned to a teacher for this class and year.')
            else:
                assignment.save()
                messages.success(request, 'Subject assigned successfully!')
                return redirect('teacher_assign_subject', pk=pk)
    else:
        active_year = AcademicYear.objects.filter(is_active=True).first()
        form = TeacherAssignmentForm(initial={'academic_year': active_year})

    current_assignments = ClassSubjectTeacher.objects.filter(
        teacher=teacher
    ).select_related('class_assigned', 'subject', 'academic_year')

    return render(request, 'teachers/assign_subjects.html', {
        'teacher': teacher,
        'form': form,
        'current_assignments': current_assignments,
    })


@login_required
@admin_required
def delete_assignment(request, pk):
    assignment = get_object_or_404(ClassSubjectTeacher, pk=pk)
    teacher_id = assignment.teacher.id
    assignment.delete()
    messages.success(request, 'Assignment removed.')
    return redirect('teacher_assign_subject', pk=teacher_id)


@login_required
@admin_required
def bulk_grade_teacher_assignment(request):
    """Assign a teacher to ALL classes of a specific grade + subject."""
    active_year = AcademicYear.objects.filter(is_active=True).first()

    if request.method == 'POST':
        form = GradeLevelTeacherAssignmentForm(request.POST)
        if form.is_valid():
            grade_level = form.cleaned_data['grade_level']
            subject = form.cleaned_data['subject']
            teacher = form.cleaned_data['teacher']
            academic_year = form.cleaned_data['academic_year']

            # Get all classes for this grade level and academic year
            classes = SchoolClass.objects.filter(
                grade_level=grade_level,
                academic_year=academic_year
            )

            created_count = 0
            updated_count = 0

            for cls in classes:
                assignment, created = ClassSubjectTeacher.objects.update_or_create(
                    class_assigned=cls,
                    subject=subject,
                    academic_year=academic_year,
                    defaults={'teacher': teacher}
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1

            messages.success(
                request,
                f'Assigned {teacher.user.get_full_name()} to {subject} for all {grade_level} classes. '
                f'({created_count} new, {updated_count} updated)'
            )
            return redirect('bulk_grade_teacher_assignment')
    else:
        initial_data = {}
        if active_year:
            initial_data['academic_year'] = active_year
        form = GradeLevelTeacherAssignmentForm(initial=initial_data)

    # Show current grade-level assignments
    assignments = ClassSubjectTeacher.objects.filter(
        academic_year=active_year
    ).select_related('class_assigned', 'subject', 'teacher__user').order_by(
        'class_assigned__grade_level', 'class_assigned__name', 'subject__name'
    ) if active_year else []

    return render(request, 'settings/bulk_grade_teacher_assignment.html', {
        'form': form,
        'assignments': assignments,
        'title': 'Bulk Grade-Level Teacher Assignment',
    })


# ─────────────────────────────────────────────
# ATTENDANCE
# ─────────────────────────────────────────────

@login_required
def mark_attendance(request, class_id):
    class_obj = get_object_or_404(SchoolClass, pk=class_id)

    if request.user.role == 'teacher':
        teacher = request.user.teacher_profile
        if not ClassSubjectTeacher.objects.filter(teacher=teacher, class_assigned=class_obj).exists():
            messages.error(request, 'You do not have permission to mark attendance for this class.')
            return redirect('teacher_dashboard')
    elif request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('dashboard')

    selected_date = request.GET.get('date', timezone.now().date().isoformat())
    selected_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
    today = timezone.now().date()
    can_edit = selected_date >= today or request.user.role == 'admin'

    students = Student.objects.filter(
        enrollments__class_assigned=class_obj,
        enrollments__is_active=True,
        is_active=True,
    ).select_related('user').distinct().order_by('user__last_name', 'user__first_name')

    attendance_records = Attendance.objects.filter(class_assigned=class_obj, date=selected_date)
    existing_attendance = {
        r.student_id: {'status': r.status, 'remarks': r.remarks}
        for r in attendance_records
    }
    already_marked = attendance_records.exists()

    for student in students:
        info = existing_attendance.get(student.id, {})
        student.attendance_status  = info.get('status', 'present')
        student.attendance_remarks = info.get('remarks', '')

    if request.method == 'POST' and can_edit:
        marked_by = request.user.teacher_profile if request.user.role == 'teacher' else None

        # get active term for attendance record
        current_term = Term.objects.filter(is_active=True).first()

        for student in students:
            status  = request.POST.get(f'status_{student.id}', 'present')
            remarks = request.POST.get(f'remarks_{student.id}', '')

            defaults = {
                'class_assigned': class_obj,
                'status':         status,
                'remarks':        remarks,
                'marked_by':      marked_by,
            }
            if current_term:
                defaults['term'] = current_term

            Attendance.objects.update_or_create(
                student=student,
                date=selected_date,
                defaults=defaults,
            )

        messages.success(request, f'Attendance marked for {class_obj.name} on {selected_date}')
        return redirect('teacher_dashboard' if request.user.role == 'teacher' else 'admin_dashboard')

    context = {
        'class': class_obj,
        'students': students,
        'selected_date': selected_date,
        'today': today,
        'can_edit': can_edit,
        'already_marked': already_marked,
    }
    return render(request, 'attendance/mark_attendance.html', context)


@login_required
def attendance_history(request):
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'You do not have permission to view this attendance page.')
        if request.user.role == 'student':
            return redirect('student_attendance_report', student_id=request.user.student_profile.id)
        return redirect('parent_dashboard')

    selected_class = request.GET.get('class', '')
    start_date = datetime.strptime(
        request.GET.get('start_date', (timezone.now().date() - timedelta(days=30)).isoformat()),
        '%Y-%m-%d'
    ).date()
    end_date = datetime.strptime(
        request.GET.get('end_date', timezone.now().date().isoformat()),
        '%Y-%m-%d'
    ).date()

    if request.user.role == 'teacher':
        teacher = request.user.teacher_profile
        classes = SchoolClass.objects.filter(subject_assignments__teacher=teacher).distinct()
    else:
        classes = SchoolClass.objects.all()

    attendance_query = Attendance.objects.filter(date__gte=start_date, date__lte=end_date)
    if selected_class:
        attendance_query = attendance_query.filter(class_assigned_id=selected_class)
    elif request.user.role == 'teacher':
        attendance_query = attendance_query.filter(
            class_assigned_id__in=classes.values_list('id', flat=True)
        )

    attendance_by_date = {}
    current = start_date
    while current <= end_date:
        day_records = attendance_query.filter(date=current)
        if day_records.exists():
            total   = day_records.count()
            present = day_records.filter(status='present').count()
            attendance_by_date[current] = {
                'is_marked':     True,
                'present_count': present,
                'absent_count':  day_records.filter(status='absent').count(),
                'late_count':    day_records.filter(status='late').count(),
                'excused_count': day_records.filter(status='excused').count(),
                'percentage':    round((present / total * 100), 1) if total else 0,
            }
        else:
            attendance_by_date[current] = {'is_marked': False}
        current += timedelta(days=1)

    context = {
        'classes': classes,
        'selected_class': selected_class,
        'start_date': start_date,
        'end_date': end_date,
        'attendance_by_date': attendance_by_date,
    }
    return render(request, 'attendance/attendance_history.html', context)


@login_required
def attendance_by_date(request):
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'You do not have permission to view this attendance page.')
        if request.user.role == 'student':
            return redirect('student_attendance_report', student_id=request.user.student_profile.id)
        return redirect('parent_dashboard')

    selected_date = datetime.strptime(
        request.GET.get('date', timezone.now().date().isoformat()), '%Y-%m-%d'
    ).date()
    selected_class = request.GET.get('class', '')

    attendance_records = Attendance.objects.filter(
        date=selected_date
    ).select_related('student__user', 'class_assigned')

    if selected_class:
        attendance_records = attendance_records.filter(class_assigned_id=selected_class)

    total   = attendance_records.count()
    present = attendance_records.filter(status='present').count()

    context = {
        'selected_date': selected_date,
        'selected_class': selected_class,
        'classes': SchoolClass.objects.all(),
        'attendance_records': attendance_records,
        'summary': {
            'total':      total,
            'present':    present,
            'absent':     attendance_records.filter(status='absent').count(),
            'late':       attendance_records.filter(status='late').count(),
            'excused':    attendance_records.filter(status='excused').count(),
            'percentage': round((present / total * 100), 1) if total else 0,
        },
    }
    return render(request, 'attendance/attendance_by_date.html', context)


@login_required
def student_attendance_report(request, student_id):
    student = get_object_or_404(Student.objects.select_related('user'), pk=student_id)

    if request.user.role == 'student':
        if request.user.student_profile.id != student.id:
            messages.error(request, 'You can only view your own attendance.')
            return redirect('student_dashboard')
    elif request.user.role == 'parent':
        if not ParentStudent.objects.filter(
            parent=request.user.parent_profile, student=student
        ).exists():
            messages.error(request, "You can only view your children's attendance.")
            return redirect('parent_dashboard')

    end_date   = timezone.now().date()
    start_date = datetime.strptime(
        request.GET.get('start_date', (end_date - timedelta(days=90)).isoformat()), '%Y-%m-%d'
    ).date()
    end_date = datetime.strptime(
        request.GET.get('end_date', end_date.isoformat()), '%Y-%m-%d'
    ).date()

    attendance_records = Attendance.objects.filter(
        student=student, date__gte=start_date, date__lte=end_date
    ).order_by('-date')

    total_days    = attendance_records.count()
    present_count = attendance_records.filter(status__in=['present', 'late']).count()
    absent_count  = attendance_records.filter(status='absent').count()
    percentage    = round((present_count / total_days * 100), 1) if total_days else 0

    consecutive_absences = 0
    for record in attendance_records[:10]:
        if record.status == 'absent':
            consecutive_absences += 1
        else:
            break

    context = {
        'student': student,
        'attendance_records': attendance_records,
        'stats': {
            'total_days':           total_days,
            'present_count':        present_count,
            'absent_count':         absent_count,
            'percentage':           percentage,
            'consecutive_absences': consecutive_absences,
        },
        'start_date': start_date,
        'end_date':   end_date,
    }
    return render(request, 'attendance/student_attendance.html', context)


@login_required
@admin_required
def class_attendance_report(request, class_id):
    class_obj = get_object_or_404(SchoolClass, pk=class_id)
    end_date   = timezone.now().date()
    start_date = datetime.strptime(
        request.GET.get('start_date', (end_date - timedelta(days=30)).isoformat()), '%Y-%m-%d'
    ).date()
    end_date = datetime.strptime(
        request.GET.get('end_date', end_date.isoformat()), '%Y-%m-%d'
    ).date()

    # Get students through enrollments since current_class is a property
    students = Student.objects.filter(
        enrollments__class_assigned=class_obj,
        enrollments__is_active=True,
        is_active=True
    ).distinct()
    student_stats, alerts = [], []

    for student in students:
        records    = Attendance.objects.filter(student=student, date__gte=start_date, date__lte=end_date)
        total_days = records.count()
        present    = records.filter(status__in=['present', 'late']).count()
        absent     = records.filter(status='absent').count()
        late       = records.filter(status='late').count()
        percentage = round((present / total_days * 100), 1) if total_days else 0

        consecutive = 0
        for r in Attendance.objects.filter(student=student).order_by('-date')[:10]:
            if r.status == 'absent':
                consecutive += 1
            else:
                break

        student_stats.append({
            'student': student, 'total_days': total_days,
            'present_count': present, 'absent_count': absent,
            'late_count': late, 'percentage': percentage,
            'consecutive_absences': consecutive,
        })

        if consecutive >= 3:
            alerts.append(f"{student.user.get_full_name()} absent for {consecutive} consecutive days")
        if percentage < 85 and total_days > 0:
            alerts.append(f"{student.user.get_full_name()} has low attendance ({percentage}%)")

    context = {
        'class': class_obj,
        'student_stats': student_stats,
        'start_date': start_date,
        'end_date': end_date,
        'alerts': alerts,
    }
    return render(request, 'attendance/class_attendance_report.html', context)


@login_required
@admin_required
def export_class_attendance(request, class_id):
    class_obj  = get_object_or_404(SchoolClass, pk=class_id)
    end_date   = timezone.now().date()
    start_date = datetime.strptime(
        request.GET.get('start_date', (end_date - timedelta(days=30)).isoformat()), '%Y-%m-%d'
    ).date()
    end_date = datetime.strptime(
        request.GET.get('end_date', end_date.isoformat()), '%Y-%m-%d'
    ).date()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Attendance Report"
    ws['A1'] = f"Attendance Report — {class_obj.name}"
    ws['A1'].font = Font(bold=True, size=14)
    ws['A2'] = f"Period: {start_date} to {end_date}"
    ws.append([])
    ws.append(['Student ID', 'Student Name', 'Total Days', 'Present', 'Absent', 'Late', 'Percentage'])
    for cell in ws[4]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")

    for student in Student.objects.filter(
        enrollments__class_assigned=class_obj,
        enrollments__is_active=True,
        is_active=True
    ).distinct():
        records    = Attendance.objects.filter(student=student, date__gte=start_date, date__lte=end_date)
        total      = records.count()
        present    = records.filter(status__in=['present', 'late']).count()
        percentage = round((present / total * 100), 1) if total else 0
        ws.append([
            student.student_id_number,
            student.user.get_full_name(),
            total,
            present,
            records.filter(status='absent').count(),
            records.filter(status='late').count(),
            f"{percentage}%",
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = (
        f'attachment; filename=attendance_{class_obj.name}_{start_date}_{end_date}.xlsx'
    )
    wb.save(response)
    return response


# ─────────────────────────────────────────────
# GRADE MANAGEMENT
# ─────────────────────────────────────────────

@login_required
def create_assessment(request):
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'You do not have permission to create assessments.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = AssessmentForm(request.POST)
        if form.is_valid():
            if request.user.role == 'teacher':
                teacher = request.user.teacher_profile
                allowed = ClassSubjectTeacher.objects.filter(
                    teacher=teacher,
                    class_assigned=form.cleaned_data['class_assigned'],
                    subject=form.cleaned_data['subject'],
                ).exists()
                if not allowed:
                    messages.error(request, 'You can only create assessments for your assigned class-subject combinations.')
                    return redirect('create_assessment')

            assessment = Assessment.objects.create(
                name=form.cleaned_data['name'],
                term=form.cleaned_data['term'],
                class_assigned=form.cleaned_data['class_assigned'],
                subject=form.cleaned_data['subject'],
                max_score=form.cleaned_data['max_score'],
                assessment_date=form.cleaned_data['assessment_date'],
                description=form.cleaned_data.get('description', ''),
            )
            messages.success(request, f'Assessment "{assessment.name}" created successfully!')
            return redirect('view_gradebook',
                            class_id=assessment.class_assigned.id,
                            subject_id=assessment.subject.id)
    else:
        form = AssessmentForm()

    if request.user.role == 'teacher':
        teacher = request.user.teacher_profile
        classes  = SchoolClass.objects.filter(subject_assignments__teacher=teacher).distinct()
        subjects = Subject.objects.filter(class_assignments__teacher=teacher).distinct()
    else:
        classes  = SchoolClass.objects.all()
        subjects = Subject.objects.all()

    context = {
        'form': form,
        'terms': Term.objects.all().order_by('-start_date'),
        'classes': classes,
        'subjects': subjects,
        'assessment': None,
    }
    return render(request, 'grades/assessment_form.html', context)


@login_required
def edit_assessment(request, assessment_id):
    assessment = get_object_or_404(Assessment, pk=assessment_id)

    if request.user.role == 'teacher':
        teacher = request.user.teacher_profile
        if not ClassSubjectTeacher.objects.filter(
            teacher=teacher,
            class_assigned=assessment.class_assigned,
            subject=assessment.subject,
        ).exists():
            messages.error(request, 'You do not have permission to edit this assessment.')
            return redirect('teacher_dashboard')
    elif request.user.role != 'admin':
        messages.error(request, 'You do not have permission to edit assessments.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = AssessmentForm(request.POST, instance=assessment)
        if form.is_valid():
            assessment.name              = form.cleaned_data['name']
            assessment.term              = form.cleaned_data['term']
            assessment.class_assigned    = form.cleaned_data['class_assigned']
            assessment.subject           = form.cleaned_data['subject']
            assessment.max_score         = form.cleaned_data['max_score']
            assessment.assessment_date   = form.cleaned_data['assessment_date']
            assessment.description       = form.cleaned_data.get('description', '')
            assessment.save()
            messages.success(request, f'Assessment "{assessment.name}" updated successfully!')
            return redirect('view_gradebook',
                            class_id=assessment.class_assigned.id,
                            subject_id=assessment.subject.id)
    else:
        form = AssessmentForm(instance=assessment)

    context = {
        'form': form,
        'terms': Term.objects.all().order_by('-start_date'),
        'classes': SchoolClass.objects.all(),
        'subjects': Subject.objects.all(),
        'assessment': assessment,
    }
    return render(request, 'grades/assessment_form.html', context)


@login_required
def view_gradebook(request, class_id, subject_id):
    class_obj = get_object_or_404(SchoolClass, pk=class_id)
    subject   = get_object_or_404(Subject, pk=subject_id)

    if request.user.role == 'teacher':
        teacher = request.user.teacher_profile
        if not ClassSubjectTeacher.objects.filter(
            teacher=teacher, class_assigned=class_obj, subject=subject
        ).exists():
            messages.error(request, 'You do not have permission to view this gradebook.')
            return redirect('teacher_dashboard')
    elif request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'You do not have permission to view gradebooks.')
        return redirect('dashboard')

    terms = Term.objects.all().order_by('-start_date')
    selected_term_id = request.GET.get('term', terms.first().id if terms.exists() else None)
    current_term = get_object_or_404(Term, pk=selected_term_id) if selected_term_id else None

    assessments = Assessment.objects.filter(
        class_assigned=class_obj, subject=subject, term_id=selected_term_id
    ).order_by('assessment_date')

    for a in assessments:
        a.grades_count = Grade.objects.filter(assessment=a).count()

    students = Student.objects.filter(
        enrollments__class_assigned=class_obj,
        enrollments__is_active=True,
        is_active=True,
    ).select_related('user').distinct().order_by('user__last_name', 'user__first_name')

    grades_data = {}
    for student in students:
        grades_data[student.id] = {}
        for a in assessments:
            grade = Grade.objects.filter(assessment=a, student=student).first()
            if grade:
                pct = (grade.score / a.max_score) * 100
                grades_data[student.id][a.id] = {
                    'score': round(pct, 1),
                    'comment': grade.comment,
                }

    for student in students:
        mark = get_term_subject_mark(student, subject, current_term) if current_term else None
        student.term_average = mark
        student.grade_letter = get_grade_letter(mark) if mark is not None else None

    context = {
        'class': class_obj,
        'subject': subject,
        'terms': terms,
        'selected_term': str(selected_term_id),
        'current_term': current_term,
        'assessments': assessments,
        'students': students,
        'grades_data': grades_data,
    }
    return render(request, 'grades/gradebook.html', context)


@login_required
def enter_grades(request, assessment_id):
    assessment = get_object_or_404(
        Assessment.objects.select_related('class_assigned', 'subject', 'term'),
        pk=assessment_id,
    )

    if request.user.role == 'teacher':
        teacher = request.user.teacher_profile
        if not ClassSubjectTeacher.objects.filter(
            teacher=teacher,
            class_assigned=assessment.class_assigned,
            subject=assessment.subject,
        ).exists():
            messages.error(request, 'You do not have permission to enter grades for this assessment.')
            return redirect('teacher_dashboard')
    elif request.user.role != 'admin':
        messages.error(request, 'You do not have permission to enter grades.')
        return redirect('dashboard')

    students = Student.objects.filter(
        enrollments__class_assigned=assessment.class_assigned,
        enrollments__is_active=True,
        is_active=True,
    ).select_related('user').distinct().order_by('user__last_name', 'user__first_name')

    existing_grades = {
        g.student_id: g
        for g in Grade.objects.filter(assessment=assessment)
    }

    for student in students:
        grade = existing_grades.get(student.id)
        student.grade_score      = round(grade.score, 2) if grade else None
        student.grade_percentage = round((grade.score / assessment.max_score) * 100, 1) if grade else None
        student.grade_comment    = grade.comment if grade else ''

    if request.method == 'POST':
        entered_by = request.user.teacher_profile if request.user.role == 'teacher' else None

        for student in students:
            score_str = request.POST.get(f'score_{student.id}', '').strip()
            comment   = request.POST.get(f'comment_{student.id}', '')

            if score_str:
                Grade.objects.update_or_create(
                    assessment=assessment,
                    student=student,
                    defaults={
                        'score':      Decimal(score_str),
                        'comment':    comment,
                        'entered_by': entered_by,
                    },
                )

        messages.success(request, f'Grades saved for {assessment.name}')
        return redirect('view_gradebook',
                        class_id=assessment.class_assigned.id,
                        subject_id=assessment.subject.id)

    return render(request, 'grades/grade_entry.html', {
        'assessment': assessment,
        'students': students,
    })


@login_required
def calculate_term_averages(request, class_id, subject_id):
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'You do not have permission to calculate term averages.')
        return redirect('dashboard')

    class_obj  = get_object_or_404(SchoolClass, pk=class_id)
    subject    = get_object_or_404(Subject, pk=subject_id)
    term       = get_object_or_404(Term, pk=request.GET.get('term'))
    assessments = Assessment.objects.filter(class_assigned=class_obj, subject=subject, term=term)

    for student in Student.objects.filter(
        enrollments__class_assigned=class_obj,
        enrollments__is_active=True,
        is_active=True
    ).distinct():
        get_term_subject_mark(student, subject, term)

    messages.success(request, 'Term averages calculated successfully!')
    return redirect('view_gradebook', class_id=class_id, subject_id=subject_id)


@login_required
def student_grades_view(request):
    if request.user.role != 'student':
        messages.error(request, 'Only students can access this page.')
        return redirect('dashboard')

    student = request.user.student_profile
    terms   = Term.objects.all().order_by('-start_date')
    selected_term_id = request.GET.get('term', terms.first().id if terms.exists() else None)
    current_term_obj = get_object_or_404(Term, pk=selected_term_id) if selected_term_id else None

    grade_summaries = []
    if current_term_obj and student.current_class:
        subject_ids = Assessment.objects.filter(
            class_assigned=student.current_class,
            term_id=selected_term_id,
        ).values_list('subject_id', flat=True).distinct()
        for subject_id in subject_ids:
            from .models import Subject
            subject = Subject.objects.get(pk=subject_id)
            mark = get_term_subject_mark(student, subject, current_term_obj)
            if mark is not None:
                assessment_grades = []
                for a in Assessment.objects.filter(
                    class_assigned=student.current_class,
                    subject=subject,
                    term_id=selected_term_id,
                ).order_by('assessment_date'):
                    grade = Grade.objects.filter(assessment=a, student=student).first()
                    if grade:
                        grade.score      = round((grade.score / a.max_score) * 100, 1)
                        grade.assessment = a
                        assessment_grades.append(grade)
                grade_summaries.append({
                    'subject': subject,
                    'average_score': mark,
                    'grade_letter': get_grade_letter(mark),
                    'assessments': assessment_grades,
                })

    overall_average = 0
    if grade_summaries:
        overall_average = round(sum(g['average_score'] for g in grade_summaries) / len(grade_summaries), 1)

    context = {
        'student': student,
        'terms': terms,
        'selected_term': str(selected_term_id),
        'current_term_obj': current_term_obj,
        'grade_summaries': grade_summaries,
        'overall_average': overall_average,
        'subjects_count': len(grade_summaries),
    }
    return render(request, 'grades/student_grades.html', context)


# ─────────────────────────────────────────────
# REPORT GENERATION
# ─────────────────────────────────────────────

@login_required
@admin_required
def reports_menu(request):
    return render(request, 'reports/reports_menu.html')


@login_required
@admin_required
def generate_report_cards(request):
    context = {
        'terms':    Term.objects.all().order_by('-start_date'),
        'classes':  SchoolClass.objects.all().order_by('name'),
        'students': Student.objects.filter(is_active=True).select_related('user').prefetch_related('enrollments', 'enrollments__class_assigned'),
    }
    return render(request, 'reports/generate_reports.html', context)


def generate_single_report_card_pdf(request, student, term):
    grades = []
    if student.current_class:
        subject_ids = Assessment.objects.filter(
            class_assigned=student.current_class,
            term=term,
        ).values_list('subject_id', flat=True).distinct()
        for subject_id in subject_ids:
            from .models import Subject
            subject = Subject.objects.get(pk=subject_id)
            mark = get_term_subject_mark(student, subject, term)
            if mark is not None:
                grades.append({
                    'subject': subject,
                    'average_score': mark,
                    'grade_letter': get_grade_letter(mark),
                    'teacher_comment': '',
                })
        grades.sort(key=lambda g: g['subject'].name)

    if not grades:
        messages.warning(request, 'No grades found for this student in the selected term.')
        return redirect('generate_report_cards')

    overall_average = round(sum(g['average_score'] for g in grades) / len(grades), 1)
    overall_grade   = get_grade_letter(overall_average)

    att = Attendance.objects.filter(
        student=student, date__gte=term.start_date, date__lte=term.end_date
    )
    total_days          = att.count()
    days_present        = att.filter(status='present').count()
    days_absent         = att.filter(status='absent').count()
    days_late           = att.filter(status='late').count()
    attendance_pct      = round((days_present / total_days * 100), 1) if total_days else 0

    buffer = io.BytesIO()
    doc    = SimpleDocTemplate(buffer, pagesize=A4,
                               rightMargin=0.5*inch, leftMargin=0.5*inch,
                               topMargin=0.5*inch, bottomMargin=0.5*inch)
    elements = []
    styles   = getSampleStyleSheet()

    title_style = ParagraphStyle('Title', parent=styles['Heading1'],
                                 fontSize=18, alignment=TA_CENTER, spaceAfter=6)
    h2_style    = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=12, spaceAfter=6)

    elements.append(Paragraph("YOUR SCHOOL NAME", title_style))
    elements.append(Paragraph("School Address | Phone | Email", styles['Normal']))
    elements.append(Spacer(1, 0.2*inch))
    elements.append(Paragraph("STUDENT REPORT CARD", h2_style))
    elements.append(Paragraph(f"{term.name} — {term.academic_year.name}", styles['Normal']))
    elements.append(Spacer(1, 0.3*inch))

    student_class_name = student.current_class.name if student.current_class else 'N/A'

    student_table = Table([
        ['Student Name:', student.user.get_full_name(), 'Student ID:', student.student_id_number],
        ['Class:', student_class_name, 'Academic Year:', term.academic_year.name],
        ['Term:', term.name, 'Report Date:', timezone.now().date().strftime('%Y-%m-%d')],
    ], colWidths=[1.5*inch, 2.5*inch, 1.5*inch, 2*inch])
    student_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('BACKGROUND', (2, 0), (2, -1), colors.lightgrey),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(student_table)
    elements.append(Spacer(1, 0.3*inch))
    elements.append(Paragraph("Academic Performance", h2_style))

    grade_data = [['Subject', 'Score (%)', 'Grade', 'Teacher Comment']]
    for g in grades:
        grade_data.append([g['subject'].name, f"{g['average_score']}%", g['grade_letter'], g['teacher_comment'] or '-'])

    grade_table = Table(grade_data, colWidths=[2*inch, 1*inch, 1*inch, 3.5*inch])
    grade_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#333333')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(grade_table)
    elements.append(Spacer(1, 0.2*inch))

    summary_table = Table([
        ['Overall Average:', f"{overall_average}%", 'Overall Grade:', overall_grade],
        ['Total Subjects:', str(len(grades)), '', ''],
    ], colWidths=[1.5*inch]*4)
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0f0f0')),
        ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#333333')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 0.3*inch))
    elements.append(Paragraph("Attendance Record", h2_style))

    att_table = Table([
        ['Days Present:', str(days_present), 'Days Absent:', str(days_absent)],
        ['Days Late:', str(days_late), 'Attendance Rate:', f"{attendance_pct}%"],
    ], colWidths=[1.5*inch]*4)
    att_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('BACKGROUND', (2, 0), (2, -1), colors.lightgrey),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(att_table)
    elements.append(Spacer(1, 0.3*inch))

    report_card = ReportCard.objects.filter(student=student, term=term).first()
    if report_card and report_card.class_teacher_comment:
        elements.append(Paragraph("Class Teacher's Comment:", h2_style))
        elements.append(Paragraph(report_card.class_teacher_comment, styles['Normal']))
        elements.append(Spacer(1, 0.2*inch))
    if report_card and report_card.principal_comment:
        elements.append(Paragraph("Principal's Comment:", h2_style))
        elements.append(Paragraph(report_card.principal_comment, styles['Normal']))
        elements.append(Spacer(1, 0.2*inch))

    elements.append(Spacer(1, 0.4*inch))
    ct_name = (
        student.current_class.class_teacher.user.get_full_name()
        if student.current_class and student.current_class.class_teacher
        else "Not Assigned"
    )
    sig_table = Table([
        ['_________________________', '_________________________'],
        [f'Class Teacher: {ct_name}', 'Principal'],
    ], colWidths=[3.5*inch, 3.5*inch])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 1), (-1, 1), 10),
    ]))
    elements.append(sig_table)
    elements.append(Spacer(1, 0.3*inch))
    elements.append(Paragraph(
        f"Official document — YOUR SCHOOL NAME<br/>Generated on {timezone.now().date()}",
        styles['Normal'],
    ))

    doc.build(elements)
    pdf_data = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf_data, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="report_card_{student.student_id_number}_{term.name}.pdf"'
    )
    return response


@login_required
def preview_report_card(request):
    term_id    = request.GET.get('term')
    class_id   = request.GET.get('class')
    student_id = request.GET.get('student')

    if not term_id or not class_id:
        messages.error(request, 'Please select term and class.')
        return redirect('generate_report_cards')

    term = get_object_or_404(Term, pk=term_id)

    if student_id:
        student = get_object_or_404(Student, pk=student_id)
    else:
        class_obj = get_object_or_404(SchoolClass, pk=class_id)
        student   = Student.objects.filter(
            enrollments__class_assigned=class_obj,
            enrollments__is_active=True,
            is_active=True
        ).first()
        if not student:
            messages.error(request, 'No students found in this class.')
            return redirect('generate_report_cards')

    return generate_single_report_card_pdf(request, student, term)


@login_required
@admin_required
def bulk_generate_reports(request):
    if request.method != 'POST':
        return redirect('generate_report_cards')

    term_id  = request.POST.get('term')
    class_id = request.POST.get('class')
    if not term_id or not class_id:
        messages.error(request, 'Please select term and class.')
        return redirect('generate_report_cards')

    term      = get_object_or_404(Term, pk=term_id)
    class_obj = get_object_or_404(SchoolClass, pk=class_id)
    students  = Student.objects.filter(
        enrollments__class_assigned=class_obj,
        enrollments__is_active=True,
        is_active=True
    ).distinct()

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for student in students:
            has_grades = Grade.objects.filter(
                student=student, assessment__term=term
            ).exists()
            if not has_grades:
                continue
            pdf_response = generate_single_report_card_pdf(request, student, term)
            filename = f"{student.student_id_number}_{student.user.last_name}_{student.user.first_name}.pdf"
            zf.writestr(filename, pdf_response.content)

    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer.read(), content_type='application/zip')
    response['Content-Disposition'] = (
        f'attachment; filename="report_cards_{class_obj.name}_{term.name}.zip"'
    )
    return response


@login_required
@admin_required
def grade_reports(request):
    terms    = Term.objects.all().order_by('-start_date')
    selected_term    = request.GET.get('term', terms.first().id if terms.exists() else None)
    selected_class   = request.GET.get('class', '')
    selected_subject = request.GET.get('subject', '')

    term = get_object_or_404(Term, pk=selected_term) if selected_term else None
    students = Student.objects.filter(is_active=True)
    if selected_class:
        students = students.filter(
            enrollments__class_assigned_id=selected_class,
            enrollments__is_active=True
        ).distinct()

    grade_summaries = []
    if term:
        if selected_subject:
            subject = get_object_or_404(Subject, pk=selected_subject)
            for student in students:
                mark = get_term_subject_mark(student, subject, term)
                if mark is not None:
                    grade_summaries.append({
                        'student': student,
                        'subject': subject,
                        'average_score': mark,
                        'grade_letter': get_grade_letter(mark),
                    })
        else:
            for student in students:
                if student.current_class:
                    subject_ids = Assessment.objects.filter(
                        term=term,
                        class_assigned=student.current_class,
                    ).values_list('subject_id', flat=True).distinct()
                    marks = []
                    for subject_id in subject_ids:
                        from .models import Subject
                        subject = Subject.objects.get(pk=subject_id)
                        mark = get_term_subject_mark(student, subject, term)
                        if mark is not None:
                            marks.append(mark)
                    if marks:
                        avg = round(sum(marks) / len(marks), 1)
                        grade_summaries.append({
                            'student': student,
                            'average_score': avg,
                            'grade_letter': get_grade_letter(avg),
                        })

    if grade_summaries:
        scores = [g['average_score'] for g in grade_summaries]
        stats = {
            'total_students': len(set(g['student'].id for g in grade_summaries)),
            'average_score':  round(sum(scores) / len(scores), 1),
            'highest_score':  round(max(scores), 1),
            'lowest_score':   round(min(scores), 1),
        }
    else:
        stats = {'total_students': 0, 'average_score': 0, 'highest_score': 0, 'lowest_score': 0}

    grade_letters    = [g['grade_letter'] for g in grade_summaries]
    grade_counts     = Counter(grade_letters)
    total            = len(grade_letters) or 1
    grade_distribution = [
        {'grade': g, 'count': grade_counts.get(g, 0),
         'percentage': round(grade_counts.get(g, 0) / total * 100, 1)}
        for g in ['A+', 'A', 'B+', 'B', 'C+', 'C', 'D+', 'D', 'F']
    ]

    top_students = []
    selected_subject_name = ''
    if selected_subject:
        top_students = sorted(grade_summaries, key=lambda x: x['average_score'], reverse=True)[:10]
        selected_subject_name = get_object_or_404(Subject, pk=selected_subject).name

    context = {
        'terms': terms,
        'selected_term': str(selected_term),
        'selected_class': selected_class,
        'selected_subject': selected_subject,
        'selected_subject_name': selected_subject_name,
        'classes': SchoolClass.objects.all(),
        'subjects': Subject.objects.all(),
        'stats': stats,
        'grade_distribution': grade_distribution,
        'top_students': top_students,
    }
    return render(request, 'reports/grade_reports.html', context)


@login_required
@admin_required
def export_grade_report(request):
    term_id    = request.GET.get('term')
    class_id   = request.GET.get('class', '')
    subject_id = request.GET.get('subject', '')
    term       = get_object_or_404(Term, pk=term_id)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Grade Report"
    ws['A1'] = "Grade Report"
    ws['A1'].font = Font(bold=True, size=14)
    ws['A2'] = f"Term: {term.name}"
    ws.append([])
    ws.append(['Student ID', 'Name', 'Class', 'Subject', 'Score (%)', 'Grade'])
    for cell in ws[4]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")

    students = Student.objects.filter(is_active=True)
    if class_id:
        students = students.filter(
            enrollments__class_assigned_id=class_id,
            enrollments__is_active=True
        ).distinct()

    if subject_id:
        subject = get_object_or_404(Subject, pk=subject_id)
        for student in students:
            mark = get_term_subject_mark(student, subject, term)
            if mark is not None:
                ws.append([
                    student.student_id_number,
                    student.user.get_full_name(),
                    student.current_class.name if student.current_class else 'N/A',
                    subject.name,
                    mark,
                    get_grade_letter(mark),
                ])
    else:
        for student in students:
            if student.current_class:
                subject_ids = Assessment.objects.filter(
                    term=term,
                    class_assigned=student.current_class,
                ).values_list('subject_id', flat=True).distinct()
                for subject_id in subject_ids:
                    from .models import Subject
                    subject = Subject.objects.get(pk=subject_id)
                    mark = get_term_subject_mark(student, subject, term)
                    if mark is not None:
                        ws.append([
                            student.student_id_number,
                            student.user.get_full_name(),
                            student.current_class.name if student.current_class else 'N/A',
                            subject.name,
                            mark,
                            get_grade_letter(mark),
                        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename=grade_report_{term.name}.xlsx'
    wb.save(response)
    return response


@login_required
@admin_required
def export_student_list(request):
    class_id = request.GET.get('class', '')
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Student List"
    ws.append(['Student ID', 'First Name', 'Last Name', 'Email', 'Gender',
               'Class', 'Emergency Contact', 'Phone', 'Status'])
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")

    students = Student.objects.select_related('user').prefetch_related('enrollments', 'enrollments__class_assigned')
    if class_id:
        # Filter through enrollments since current_class is a property
        students = students.filter(
            enrollments__class_assigned_id=class_id,
            enrollments__is_active=True
        ).distinct()

    for s in students:
        ws.append([
            s.student_id_number,
            s.user.first_name,
            s.user.last_name,
            s.user.email,
            s.get_gender_display(),
            s.current_class.name if s.current_class else 'N/A',
            s.emergency_contact_name,
            s.emergency_contact_phone,
            'Active' if s.is_active else 'Inactive',
        ])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=student_list.xlsx'
    wb.save(response)
    return response


# ─────────────────────────────────────────────
# PROFILE MANAGEMENT
# ─────────────────────────────────────────────

@login_required
def view_profile(request):
    user    = request.user
    context = {'user': user}

    if user.role == 'student':
        try:
            student = user.student_profile
            context['student'] = student
            current_term = Term.objects.filter(is_active=True).first()
            if current_term and student.current_class:
                subject_ids = Assessment.objects.filter(
                    term=current_term,
                    class_assigned=student.current_class,
                ).values_list('subject_id', flat=True).distinct()
                marks = []
                for subject_id in subject_ids:
                    from .models import Subject
                    subject = Subject.objects.get(pk=subject_id)
                    mark = get_term_subject_mark(student, subject, current_term)
                    if mark is not None:
                        marks.append(mark)
                context['current_average'] = round(sum(marks) / len(marks), 1) if marks else 0
            else:
                context['current_average'] = 0
            total_att = Attendance.objects.filter(student=student).count()
            if total_att > 0:
                present = Attendance.objects.filter(
                    student=student, status__in=['present', 'late']
                ).count()
                context['attendance_percentage'] = round((present / total_att) * 100, 1)
            else:
                context['attendance_percentage'] = 0
        except Student.DoesNotExist:
            messages.error(request, 'Student profile not found.')

    elif user.role == 'teacher':
        try:
            context['teacher'] = user.teacher_profile
            context['teaching_assignments'] = ClassSubjectTeacher.objects.filter(
                teacher=user.teacher_profile
            ).select_related('class_assigned', 'subject')[:5]
        except Teacher.DoesNotExist:
            messages.error(request, 'Teacher profile not found.')

    elif user.role == 'parent':
        try:
            context['parent'] = user.parent_profile
            context['children'] = ParentStudent.objects.filter(
                parent=user.parent_profile
            ).select_related('student__user').prefetch_related('student__enrollments', 'student__enrollments__class_assigned')
        except Parent.DoesNotExist:
            messages.error(request, 'Parent profile not found.')

    return render(request, 'profile/view_profile.html', context)


@login_required
def edit_profile(request):
    user = request.user

    if request.method == 'POST':
        # FIX: no request.FILES — profile_picture removed from User model
        user_form = UserProfileForm(request.POST, instance=user)
        role_form = _get_role_form(request, user, request.POST)

        if user_form.is_valid() and (role_form is None or role_form.is_valid()):
            user_form.save()
            if role_form:
                role_form.save()
            ActivityLog.objects.create(
                user=user, action='update', model_name='User',
                object_id=user.id,
                description=f'{user.get_full_name()} updated their profile',
            )
            messages.success(request, 'Profile updated successfully!')
            return redirect('view_profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        user_form = UserProfileForm(instance=user)
        role_form = _get_role_form(request, user)

    return render(request, 'profile/edit_profile.html', {
        'user_form': user_form,
        'role_form': role_form,
        'user': user,
    })


def _get_role_form(request, user, post_data=None):
    """Helper: returns the appropriate role-specific profile form or None."""
    role_map = {
        'student': (StudentProfileForm, 'student_profile'),
        'teacher': (TeacherProfileForm, 'teacher_profile'),
        'parent':  (ParentProfileForm,  'parent_profile'),
    }
    entry = role_map.get(user.role)
    if not entry:
        return None
    FormClass, profile_attr = entry
    try:
        instance = getattr(user, profile_attr)
        return FormClass(post_data, instance=instance) if post_data else FormClass(instance=instance)
    except Exception:
        return None


@login_required
def change_password(request):
    if request.method == 'POST':
        form = CustomPasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            ActivityLog.objects.create(
                user=user, action='update', model_name='User',
                object_id=user.id,
                description=f'{user.get_full_name()} changed their password',
            )
            messages.success(request, 'Password changed successfully!')
            return redirect('view_profile')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomPasswordChangeForm(request.user)

    return render(request, 'profile/change_password.html', {'form': form})


# ─────────────────────────────────────────────
# ASSIGNMENTS
# ─────────────────────────────────────────────

@login_required
def assignment_list(request):
    user = request.user

    if user.role == 'student':
        student     = user.student_profile
        assignments = Assignment.objects.filter(
            class_assigned=student.current_class
        ).select_related('subject', 'teacher__user').order_by('-due_date')
        for assignment in assignments:
            sub = AssignmentSubmission.objects.filter(
                assignment=assignment, student=student
            ).first()
            assignment.submission_status = sub.status if sub else 'missing'

    elif user.role == 'teacher':
        teacher     = user.teacher_profile
        assignments = Assignment.objects.filter(
            teacher=teacher
        ).select_related('class_assigned', 'subject').order_by('-due_date')
        for assignment in assignments:
            assignment.submission_count = assignment.submissions.count()

    elif user.role == 'parent':
        parent   = user.parent_profile
        children = ParentStudent.objects.filter(parent=parent).values_list('student', flat=True)
        assignments = Assignment.objects.filter(
            class_assigned__enrollments__student_id__in=children,
            class_assigned__enrollments__is_active=True,
        ).distinct().select_related('class_assigned', 'subject').order_by('-due_date')

    else:
        assignments = Assignment.objects.all().order_by('-due_date')

    return render(request, 'assignments/assignment_list.html', {'assignments': assignments})


@login_required
@teacher_required
def create_assignment(request):
    teacher = request.user.teacher_profile

    if request.method == 'POST':
        form = AssignmentForm(request.POST, request.FILES)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.teacher = teacher
            assignment.save()
            messages.success(request, 'Assignment published successfully!')
            return redirect('assignment_list')
    else:
        form = AssignmentForm()
        form.fields['class_assigned'].queryset = SchoolClass.objects.filter(
            subject_assignments__teacher=teacher
        ).distinct()
        form.fields['subject'].queryset = Subject.objects.filter(
            class_assignments__teacher=teacher
        ).distinct()

    return render(request, 'assignments/assignment_form.html', {'form': form, 'title': 'Create Assignment'})


@login_required
def assignment_detail(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk)
    submission = None
    if request.user.role == 'student':
        student = request.user.student_profile
        is_enrolled = StudentEnrollment.objects.filter(
            student=student,
            class_assigned=assignment.class_assigned,
            is_active=True,
        ).exists()
        if not is_enrolled:
            messages.error(request, 'Access denied.')
            return redirect('assignment_list')
        submission = AssignmentSubmission.objects.filter(
            assignment=assignment, student=student
        ).first()
    elif request.user.role == 'teacher':
        if assignment.teacher != request.user.teacher_profile:
            messages.error(request, 'Access denied.')
            return redirect('assignment_list')
    elif request.user.role == 'parent':
        child_ids = ParentStudent.objects.filter(
            parent=request.user.parent_profile
        ).values_list('student_id', flat=True)
        has_child_in_class = StudentEnrollment.objects.filter(
            student_id__in=child_ids,
            class_assigned=assignment.class_assigned,
            is_active=True,
        ).exists()
        if not has_child_in_class:
            messages.error(request, 'Access denied.')
            return redirect('assignment_list')
    elif request.user.role != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('dashboard')

    return render(request, 'assignments/assignment_detail.html', {
        'assignment': assignment,
        'submission': submission,
        'now': timezone.now(),
    })


@login_required
@student_required
def submit_assignment(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk)
    student    = request.user.student_profile

    if timezone.now() > assignment.due_date and not assignment.allow_late_submission:
        messages.error(request, 'The deadline for this assignment has passed.')
        return redirect('assignment_detail', pk=pk)

    existing_submission = AssignmentSubmission.objects.filter(
        assignment=assignment, student=student
    ).first()

    if request.method == 'POST':
        form = StudentSubmissionForm(request.POST, request.FILES, instance=existing_submission)
        if form.is_valid():
            submission          = form.save(commit=False)
            submission.assignment = assignment
            submission.student    = student
            submission.save()
            messages.success(request, 'Assignment submitted successfully!')
            return redirect('assignment_detail', pk=pk)
    else:
        form = StudentSubmissionForm(instance=existing_submission)

    return render(request, 'assignments/submit_assignment.html', {
        'form': form,
        'assignment': assignment,
    })


@login_required
@teacher_required
def view_submissions(request, pk):
    assignment = get_object_or_404(Assignment, pk=pk)

    if assignment.teacher != request.user.teacher_profile:
        messages.error(request, 'Access denied.')
        return redirect('assignment_list')

    submissions    = AssignmentSubmission.objects.filter(
        assignment=assignment
    ).select_related('student__user')
    submitted_ids  = submissions.values_list('student_id', flat=True)
    pending_students = Student.objects.filter(
        enrollments__class_assigned=assignment.class_assigned,
        enrollments__is_active=True,
        is_active=True,
    ).exclude(id__in=submitted_ids).distinct()

    return render(request, 'assignments/view_submissions.html', {
        'assignment': assignment,
        'submissions': submissions,
        'pending_students': pending_students,
    })


@login_required
@teacher_required
def grade_submission(request, pk):
    submission = get_object_or_404(AssignmentSubmission, pk=pk)
    if submission.assignment.teacher != request.user.teacher_profile:
        messages.error(request, 'Access denied.')
        return redirect('assignment_list')

    if request.method == 'POST':
        form = GradingForm(request.POST, instance=submission)
        if form.is_valid():
            graded            = form.save(commit=False)
            graded.graded_by  = request.user.teacher_profile
            graded.graded_at  = timezone.now()
            if graded.score is not None and graded.status == 'pending':
                graded.status = 'graded'
            graded.save()
            messages.success(request, f'Graded submission for {submission.student.user.get_full_name()}')
            return redirect('view_submissions', pk=submission.assignment.id)
    else:
        form = GradingForm(instance=submission)

    return render(request, 'assignments/grade_submission.html', {
        'form': form,
        'submission': submission,
    })


# ─────────────────────────────────────────────
# PARENT MANAGEMENT
# ─────────────────────────────────────────────

@login_required
@admin_required
def parent_list(request):
    parents = Parent.objects.select_related('user').prefetch_related(
        'student_relationships__student__user'
    )
    search_query = request.GET.get('search', '')
    if search_query:
        parents = parents.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__email__icontains=search_query)
        )
    return render(request, 'parents/parent_list.html', {
        'parents': parents,
        'search_query': search_query,
    })


@login_required
@admin_required
def parent_create(request):
    if request.method == 'POST':
        form = ParentForm(request.POST)
        if form.is_valid():
            try:
                user = User.objects.create_user(
                    username=User.generate_username('parent'),
                    email=form.cleaned_data['email'],
                    password='parent123',
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    phone=form.cleaned_data.get('phone', ''),
                    role='parent',
                )
                parent      = form.save(commit=False)
                parent.user = user
                parent.save()
                messages.success(request, f'Parent account created for {user.get_full_name()}')
                return redirect('parent_detail', pk=parent.pk)
            except Exception as e:
                messages.error(request, f'Error creating parent: {str(e)}')
    else:
        form = ParentForm()

    return render(request, 'parents/parent_form.html', {'form': form, 'title': 'Add Parent'})


@login_required
@admin_required
def parent_update(request, pk):
    parent = get_object_or_404(Parent, pk=pk)

    if request.method == 'POST':
        form = ParentForm(request.POST, instance=parent)
        if form.is_valid():
            u = parent.user
            u.first_name = form.cleaned_data['first_name']
            u.last_name  = form.cleaned_data['last_name']
            u.email      = form.cleaned_data['email']
            u.phone      = form.cleaned_data.get('phone', '')
            u.save()
            form.save()
            messages.success(request, 'Parent profile updated.')
            return redirect('parent_detail', pk=parent.pk)
    else:
        form = ParentForm(instance=parent, initial={
            'first_name': parent.user.first_name,
            'last_name':  parent.user.last_name,
            'email':      parent.user.email,
            'phone':      parent.user.phone,
        })

    return render(request, 'parents/parent_form.html', {'form': form, 'title': 'Edit Parent'})


@login_required
@admin_required
def parent_detail(request, pk):
    parent = get_object_or_404(Parent, pk=pk)
    links  = ParentStudent.objects.filter(parent=parent).select_related('student__user')
    return render(request, 'parents/parent_detail.html', {'parent': parent, 'links': links})


@login_required
@admin_required
def link_student(request, pk):
    parent = get_object_or_404(Parent, pk=pk)

    if request.method == 'POST':
        form = ParentStudentLinkForm(request.POST)
        if form.is_valid():
            student = form.cleaned_data['student']
            if ParentStudent.objects.filter(parent=parent, student=student).exists():
                messages.error(request, 'This student is already linked to this parent.')
            else:
                link        = form.save(commit=False)
                link.parent = parent
                link.save()
                messages.success(request, 'Student linked successfully.')
                return redirect('parent_detail', pk=pk)
    else:
        form = ParentStudentLinkForm()

    return render(request, 'parents/link_student.html', {'form': form, 'parent': parent})


@login_required
@admin_required
def unlink_student(request, pk):
    link      = get_object_or_404(ParentStudent, pk=pk)
    parent_id = link.parent.id
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('parent_detail', pk=parent_id)
    link.delete()
    messages.success(request, 'Student unlinked successfully.')
    return redirect('parent_detail', pk=parent_id)


# ─────────────────────────────────────────────
# USER MANAGEMENT
# ─────────────────────────────────────────────

@login_required
@admin_required
def user_list(request):
    users = User.objects.all().order_by('-date_joined')

    role_filter = request.GET.get('role', '')
    if role_filter:
        users = users.filter(role=role_filter)

    search_query = request.GET.get('search', '')
    if search_query:
        users = users.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )

    paginator = Paginator(users, 50)
    page_obj  = paginator.get_page(request.GET.get('page'))

    return render(request, 'users/user_list.html', {
        'users': page_obj,
        'role_filter': role_filter,
        'search_query': search_query,
    })


@login_required
@admin_required
def user_create_admin(request):
    if request.method == 'POST':
        form = UserAdminForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = 'admin'
            user.save()
            messages.success(request, f'Admin user {user.get_full_name()} created!')
            return redirect('user_list')
    else:
        form = UserAdminForm()

    return render(request, 'users/user_form.html', {'form': form, 'title': 'Create Administrator'})


@login_required
@admin_required
def user_update(request, pk):
    user_obj = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        form = UserAdminForm(request.POST, instance=user_obj)
        if form.is_valid():
            form.save()
            messages.success(request, f'User {user_obj.get_full_name()} updated successfully.')
            return redirect('user_list')
    else:
        form = UserAdminForm(instance=user_obj)

    return render(request, 'users/user_form.html', {
        'form': form,
        'title': f'Edit User: {user_obj.get_full_name()}',
        'editing_user': user_obj,
    })


@login_required
@admin_required
def toggle_user_status(request, pk):
    user_obj = get_object_or_404(User, pk=pk)

    if user_obj == request.user:
        messages.error(request, 'You cannot deactivate your own account.')
        return redirect('user_list')

    if request.method == 'POST':
        user_obj.is_active = not user_obj.is_active
        user_obj.save()

        if user_obj.role == 'teacher' and hasattr(user_obj, 'teacher_profile'):
            user_obj.teacher_profile.is_active = user_obj.is_active
            user_obj.teacher_profile.save()
        elif user_obj.role == 'student' and hasattr(user_obj, 'student_profile'):
            user_obj.student_profile.is_active = user_obj.is_active
            user_obj.student_profile.save()

        status = 'activated' if user_obj.is_active else 'deactivated'
        messages.success(request, f'User {user_obj.email} has been {status}.')

    return redirect('user_list')


@login_required
@admin_required
def manage_user_role(request, pk):
    user_obj = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        form = RoleChangeForm(request.POST, instance=user_obj)
        if form.is_valid():
            new_role = form.cleaned_data['role']

            if new_role == 'teacher' and not hasattr(user_obj, 'teacher_profile'):
                Teacher.objects.create(user=user_obj)
                messages.warning(request, 'User promoted to Teacher. Please complete the profile.')
            elif new_role == 'student' and not hasattr(user_obj, 'student_profile'):
                messages.warning(request, 'Cannot auto-convert to Student due to required fields. Use Student Management.')
                return redirect('manage_user_role', pk=pk)
            elif new_role == 'parent' and not hasattr(user_obj, 'parent_profile'):
                Parent.objects.create(user=user_obj)
                messages.info(request, 'User converted to Parent.')

            form.save()
            messages.success(request, f'Role changed to {new_role}.')
            return redirect('user_list')
    else:
        form = RoleChangeForm(instance=user_obj)

    return render(request, 'users/manage_roles.html', {'form': form, 'target_user': user_obj})


# ─────────────────────────────────────────────
# SETTINGS
# ─────────────────────────────────────────────

@login_required
@admin_required
def settings_dashboard(request):
    # FIX: SchoolInfo model does not exist in models.py — removed reference.
    # Add a SchoolInfo model to models.py if you need this feature.
    return render(request, 'settings/dashboard.html')


@login_required
@admin_required
def academic_year_list(request):
    years = AcademicYear.objects.all().order_by('-start_date')
    return render(request, 'settings/academic_year_list.html', {'years': years})


@login_required
@admin_required
def academic_year_manage(request, pk=None):
    """Handle both adding and editing academic years"""
    if pk:
        year = get_object_or_404(AcademicYear, pk=pk)
        title = 'Edit Academic Year'
    else:
        year = None
        title = 'Add Academic Year'

    if request.method == 'POST':
        form = AcademicYearForm(request.POST, instance=year)
        if form.is_valid():
            # If this year is set as active, deactivate all others
            if form.cleaned_data['is_active']:
                AcademicYear.objects.all().update(is_active=False)
            form.save()
            messages.success(request, 'Academic Year saved successfully.')
            return redirect('academic_year_list')
    else:
        form = AcademicYearForm(instance=year)

    return render(request, 'settings/form_base.html', {
        'form': form, 
        'title': title,
        'cancel_url': 'academic_year_list'
    })


@login_required
@admin_required
def term_manage(request, pk=None):
    """Handle both adding and editing terms"""
    if pk:
        term = get_object_or_404(Term, pk=pk)
        title = 'Edit Term'
    else:
        term = None
        title = 'Add Term'

    if request.method == 'POST':
        form = TermForm(request.POST, instance=term)
        if form.is_valid():
            # If this term is set as active, deactivate all others
            if form.cleaned_data['is_active']:
                Term.objects.all().update(is_active=False)
            form.save()
            messages.success(request, 'Term saved successfully.')
            return redirect('term_list')
    else:
        form = TermForm(instance=term)

    return render(request, 'settings/form_base.html', {
        'form': form, 
        'title': title,
        'cancel_url': 'term_list'
    })


@login_required
@admin_required
def subject_manage(request, pk=None):
    """Handle both adding and editing subjects"""
    if pk:
        subject = get_object_or_404(Subject, pk=pk)
        title = 'Edit Subject'
    else:
        subject = None
        title = 'Add Subject'

    if request.method == 'POST':
        form = SubjectForm(request.POST, instance=subject)
        if form.is_valid():
            form.save()
            messages.success(request, 'Subject saved successfully.')
            return redirect('subject_list')
    else:
        form = SubjectForm(instance=subject)

    return render(request, 'settings/form_base.html', {
        'form': form, 
        'title': title,
        'cancel_url': 'subject_list'
    })


@login_required
@admin_required
def term_list(request):
    terms = Term.objects.all().order_by('-start_date')
    return render(request, 'settings/term_list.html', {'terms': terms})


@login_required
@admin_required
def subject_list(request):
    subjects = Subject.objects.annotate(
        class_count=Count('class_assignments')
    ).order_by('name')
    return render(request, 'settings/subject_list.html', {'subjects': subjects})


@login_required
@admin_required
def subject_delete(request, pk):
    subject = get_object_or_404(Subject, pk=pk)
    if request.method == 'POST':
        subject.delete()
        messages.success(request, 'Subject deleted.')
        return redirect('subject_list')
    return render(request, 'settings/confirm_delete.html', {'object': subject, 'type': 'Subject'})


@login_required
@admin_required
def grading_scale(request):
    scales = GradingScale.objects.all().order_by('-min_score')
    form   = GradingScaleForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Grade scale added.')
        return redirect('grading_scale')
    return render(request, 'settings/grading_scale.html', {'scales': scales, 'form': form})


@login_required
@admin_required
def grading_scale_delete(request, pk):
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('grading_scale')
    get_object_or_404(GradingScale, pk=pk).delete()
    messages.success(request, 'Grade scale removed.')
    return redirect('grading_scale')


# ─────────────────────────────────────────────
# ANALYTICS
# ─────────────────────────────────────────────

@login_required
@admin_required
def analytics_dashboard(request):
    current_term = Term.objects.filter(is_active=True).first()

    all_marks = []
    if current_term:
        for student in Student.objects.filter(is_active=True):
            if student.current_class:
                subject_ids = Assessment.objects.filter(
                    term=current_term,
                    class_assigned=student.current_class,
                ).values_list('subject_id', flat=True).distinct()
                for subject_id in subject_ids:
                    from .models import Subject
                    subject = Subject.objects.get(pk=subject_id)
                    mark = get_term_subject_mark(student, subject, current_term)
                    if mark is not None:
                        all_marks.append(mark)

    grade_counts = Counter(get_grade_letter(m) for m in all_marks)
    grade_distribution = [
        {'grade_letter': g, 'count': grade_counts.get(g, 0)}
        for g in ['A+', 'A', 'B+', 'B', 'C+', 'C', 'D+', 'D', 'F']
    ]

    subject_performance = []
    if current_term:
        for subject in Subject.objects.all():
            marks = []
            for student in Student.objects.filter(is_active=True):
                if student.current_class:
                    mark = get_term_subject_mark(student, subject, current_term)
                    if mark is not None:
                        marks.append(mark)
            if marks:
                subject_performance.append({
                    'name': subject.name,
                    'avg_score': round(sum(marks) / len(marks), 1),
                })
        subject_performance.sort(key=lambda x: x['avg_score'], reverse=True)
    subject_performance = subject_performance[:5]

    class_performance = []
    if current_term:
        for class_obj in SchoolClass.objects.all():
            marks = []
            for student in Student.objects.filter(
                enrollments__class_assigned=class_obj,
                enrollments__is_active=True,
                is_active=True,
            ).distinct():
                subject_ids = Assessment.objects.filter(
                    term=current_term,
                    class_assigned=class_obj,
                ).values_list('subject_id', flat=True).distinct()
                for subject_id in subject_ids:
                    from .models import Subject
                    subject = Subject.objects.get(pk=subject_id)
                    mark = get_term_subject_mark(student, subject, current_term)
                    if mark is not None:
                        marks.append(mark)
            if marks:
                class_performance.append({
                    'name': class_obj.name,
                    'avg_score': round(sum(marks) / len(marks), 1),
                })
        class_performance.sort(key=lambda x: x['avg_score'], reverse=True)

    return render(request, 'reports/analytics_dashboard.html', {
        'grade_distribution': grade_distribution,
        'subject_performance': subject_performance,
        'class_performance': class_performance,
    })


@login_required
@admin_required
def teacher_performance_report(request):
    teachers         = Teacher.objects.filter(is_active=True).select_related('user')
    performance_data = []
    current_term     = Term.objects.filter(is_active=True).first()

    for teacher in teachers:
        assignments = ClassSubjectTeacher.objects.filter(teacher=teacher)
        marks = []
        student_ids = set()
        if current_term:
            for assignment in assignments:
                for student in Student.objects.filter(
                    enrollments__class_assigned=assignment.class_assigned,
                    enrollments__is_active=True,
                    is_active=True,
                ).distinct():
                    mark = get_term_subject_mark(student, assignment.subject, current_term)
                    if mark is not None:
                        marks.append(mark)
                        student_ids.add(student.id)

        avg_score = round(sum(marks) / len(marks), 1) if marks else 0
        student_count = len(student_ids)

        performance_data.append({
            'teacher':       teacher,
            'avg_score':     avg_score,
            'student_count': student_count,
            'classes_count': assignments.count(),
        })

    performance_data.sort(key=lambda x: x['avg_score'], reverse=True)
    return render(request, 'reports/teacher_performance.html', {'performance_data': performance_data})


@login_required
def student_transcript_view(request, pk):
    student = get_object_or_404(Student.objects.select_related('user').prefetch_related('enrollments', 'enrollments__class_assigned'), pk=pk)

    if request.user.role == 'student' and request.user.student_profile != student:
        messages.error(request, 'Access denied.')
        return redirect('dashboard')
    if request.user.role == 'parent':
        if not ParentStudent.objects.filter(
            parent=request.user.parent_profile, student=student
        ).exists():
            messages.error(request, 'Access denied.')
            return redirect('dashboard')

    history = {}
    for year in AcademicYear.objects.all().order_by('start_date'):
        year_data = {}
        for term in Term.objects.filter(academic_year=year).order_by('start_date'):
            grades = []
            if student.current_class:
                subject_ids = Assessment.objects.filter(
                    term=term,
                    class_assigned=student.current_class,
                ).values_list('subject_id', flat=True).distinct()
                for subject_id in subject_ids:
                    from .models import Subject
                    subject = Subject.objects.get(pk=subject_id)
                    mark = get_term_subject_mark(student, subject, term)
                    if mark is not None:
                        grades.append({
                            'subject': subject,
                            'average_score': mark,
                            'grade_letter': get_grade_letter(mark),
                            'teacher_comment': '',
                        })
                grades.sort(key=lambda g: g['subject'].name)
            if grades:
                avg = sum(g['average_score'] for g in grades) / len(grades)
                year_data[term] = {'grades': grades, 'average': round(avg, 1)}
        if year_data:
            history[year] = year_data

    all_marks = []
    for year, year_data in history.items():
        for term, data in year_data.items():
            all_marks.append(data['average'])
    overall = sum(all_marks) / len(all_marks) if all_marks else 0

    return render(request, 'reports/student_transcript.html', {
        'student':          student,
        'history':          history,
        'overall_average':  round(overall, 1),
        'generated_date':   timezone.now(),
    })


# ─────────────────────────────────────────────
# GRADE-LEVEL SUBJECT CONFIGURATION
# ─────────────────────────────────────────────

@login_required
@admin_required
def grade_subject_config_list(request):
    """List all grade level subject configurations - shows all grades even if empty."""
    configs = GradeSubjectConfig.objects.select_related('subject').order_by('grade_level', 'subject__name')

    # Initialize ALL grade levels (even if no configs exist)
    grouped_configs = {grade[0]: [] for grade in GRADE_CHOICES}

    # Populate with existing configs
    for config in configs:
        grouped_configs[config.grade_level].append(config)

    context = {
        'grouped_configs': grouped_configs,
        'grade_choices': GRADE_CHOICES,
    }
    return render(request, 'settings/grade_subject_config.html', context)


@login_required
@admin_required
def grade_subject_config_add(request, grade_level):
    """Add subjects to a specific grade level"""
    if request.method == 'POST':
        form = GradeSubjectConfigForm(request.POST)
        if form.is_valid():
            config = form.save(commit=False)
            config.grade_level = grade_level
            config.save()
            messages.success(request, f'Subject added to {dict(GradeSubjectConfig.GRADE_CHOICES).get(grade_level)}')
            return redirect('grade_subject_config_list')
    else:
        form = GradeSubjectConfigForm()
        # Filter subjects not already configured for this grade
        existing_subjects = GradeSubjectConfig.objects.filter(grade_level=grade_level).values_list('subject_id', flat=True)
        form.fields['subject'].queryset = Subject.objects.exclude(id__in=existing_subjects)
    
    context = {
        'form': form,
        'grade_level': grade_level,
        'grade_name': dict(GradeSubjectConfig.GRADE_CHOICES).get(grade_level),
        'title': f'Add Subject to {dict(GradeSubjectConfig.GRADE_CHOICES).get(grade_level)}',
    }
    return render(request, 'settings/form_base.html', context)


@login_required
@admin_required
def grade_subject_config_edit(request, pk):
    """Edit grade subject configuration"""
    config = get_object_or_404(GradeSubjectConfig, pk=pk)
    
    if request.method == 'POST':
        form = GradeSubjectConfigForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configuration updated successfully')
            return redirect('grade_subject_config_list')
    else:
        form = GradeSubjectConfigForm(instance=config)
    
    context = {
        'form': form,
        'title': f'Edit {config.subject.name} for {config.get_grade_level_display()}',
        'cancel_url': 'grade_subject_config_list',
    }
    return render(request, 'settings/form_base.html', context)


@login_required
@admin_required
def grade_subject_config_delete(request, pk):
    """Delete grade subject configuration"""
    config = get_object_or_404(GradeSubjectConfig, pk=pk)
    if request.method == 'POST':
        config.delete()
        messages.success(request, 'Configuration removed successfully')
        return redirect('grade_subject_config_list')
    
    return render(request, 'settings/confirm_delete.html', {
        'object': config,
        'type': f'Subject {config.subject.name} from {config.get_grade_level_display()}'
    })


# ─────────────────────────────────────────────
# CLASS-SUBJECT-TEACHER ASSIGNMENT
# ─────────────────────────────────────────────

@login_required
@admin_required
def class_subject_assignment_list(request, class_id=None):
    """List subject assignments for classes"""
    if class_id:
        class_obj = get_object_or_404(SchoolClass, pk=class_id)
        assignments = ClassSubjectTeacher.objects.filter(
            class_assigned=class_obj
        ).select_related('subject', 'teacher__user', 'academic_year')
        context = {
            'class_obj': class_obj,
            'assignments': assignments,
        }
        return render(request, 'classes/class_subject_assignments.html', context)
    else:
        # Show all classes with assignment counts
        classes = SchoolClass.objects.select_related('academic_year', 'class_teacher__user').annotate(
            subject_count=Count('subject_assignments')
        ).order_by('academic_year', 'grade_level', 'name')
        
        context = {
            'classes': classes,
        }
        return render(request, 'classes/class_subject_list.html', context)


@login_required
@admin_required
def class_subject_assign(request, class_id):
    """Assign a subject to a class with a teacher"""
    class_obj = get_object_or_404(SchoolClass, pk=class_id)
    
    if request.method == 'POST':
        form = ClassSubjectTeacherForm(request.POST)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.class_assigned = class_obj
            
            # Check if already exists for this class, subject, and academic year
            exists = ClassSubjectTeacher.objects.filter(
                class_assigned=class_obj,
                subject=assignment.subject,
                academic_year=assignment.academic_year
            ).exists()
            
            if exists:
                messages.error(
                    request, 
                    f'Subject "{assignment.subject.name}" is already assigned to {class_obj.name} for {assignment.academic_year.name}'
                )
            else:
                assignment.save()
                messages.success(
                    request, 
                    f'Subject "{assignment.subject.name}" assigned to {class_obj.name} successfully!'
                )
                return redirect('class_subject_assignment_list', class_id=class_id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        # Get active academic year
        active_year = AcademicYear.objects.filter(is_active=True).first()
        
        # Create form with initial values
        initial_data = {}
        if active_year:
            initial_data['academic_year'] = active_year.id  # Pass the ID, not the object
        
        # Initialize the form
        form = ClassSubjectTeacherForm(initial=initial_data)
        
        # Only allow subjects configured for this grade level in GradeSubjectConfig
        configured_subject_ids = GradeSubjectConfig.objects.filter(
            grade_level=class_obj.grade_level
        ).values_list('subject_id', flat=True)

        if active_year:
            assigned_subjects = ClassSubjectTeacher.objects.filter(
                class_assigned=class_obj,
                academic_year=active_year
            ).values_list('subject_id', flat=True)

            # Set the queryset for the subject field
            form.fields['subject'].queryset = Subject.objects.filter(
                id__in=configured_subject_ids
            ).exclude(
                id__in=assigned_subjects
            ).order_by('name')
        else:
            form.fields['subject'].queryset = Subject.objects.filter(
                id__in=configured_subject_ids
            ).order_by('name')

        # Add helpful message if no subjects available
        if hasattr(form.fields['subject'], 'queryset') and form.fields['subject'].queryset.count() == 0:
            messages.info(
                request,
                f'All grade-configured subjects have been assigned to {class_obj.name} for this academic year.'
            )
    
    context = {
        'form': form,
        'class_obj': class_obj,
        'title': f'Assign Subject to {class_obj.name}',
        'cancel_url': 'class_subject_assignment_list',
        'cancel_args': [class_id],
    }
    return render(request, 'settings/form_base.html', context)

@login_required
@admin_required
def class_subject_remove(request, assignment_id):
    """Remove a subject assignment from a class"""
    assignment = get_object_or_404(ClassSubjectTeacher, pk=assignment_id)
    class_id = assignment.class_assigned.id
    
    if request.method == 'POST':
        assignment.delete()
        messages.success(request, 'Subject assignment removed successfully')
        return redirect('class_subject_assignment_list', class_id=class_id)
    
    return render(request, 'settings/confirm_delete.html', {
        'object': assignment,
        'type': f'Subject {assignment.subject.name} from {assignment.class_assigned.name}',
    })


# ─────────────────────────────────────────────
# PARENT GRADES VIEW
# ─────────────────────────────────────────────

@login_required
def parent_grades_view(request):
    """Allow parents to view their children's grades"""
    if request.user.role != 'parent':
        messages.error(request, 'Only parents can access this page.')
        return redirect('dashboard')
    
    try:
        parent = request.user.parent_profile
    except Parent.DoesNotExist:
        messages.error(request, 'Parent profile not found.')
        return redirect('dashboard')
    
    # Get parent's children
    parent_student_links = ParentStudent.objects.filter(
        parent=parent
    ).select_related('student__user')
    
    children_ids = parent_student_links.values_list('student_id', flat=True)
    
    if not children_ids:
        messages.info(request, 'No children linked to your account yet.')
        return redirect('parent_dashboard')
    
    # Get selected child (if any)
    selected_child_id = request.GET.get('child')
    if selected_child_id:
        # Verify child belongs to parent
        if int(selected_child_id) not in children_ids:
            messages.error(request, 'Invalid child selected.')
            return redirect('parent_grades')
        selected_child = get_object_or_404(Student.objects.select_related('user'), pk=selected_child_id)
    else:
        # Default to first child
        selected_child = parent_student_links.first().student
    
    # Get terms and selected term
    terms = Term.objects.all().order_by('-start_date')
    selected_term_id = request.GET.get('term', terms.first().id if terms.exists() else None)
    current_term_obj = get_object_or_404(Term, pk=selected_term_id) if selected_term_id else None
    
    grade_summaries = []
    if current_term_obj and selected_child.current_class:
        subject_ids = Assessment.objects.filter(
            class_assigned=selected_child.current_class,
            term_id=selected_term_id,
        ).values_list('subject_id', flat=True).distinct()
        for subject_id in subject_ids:
            from .models import Subject
            subject = Subject.objects.get(pk=subject_id)
            mark = get_term_subject_mark(selected_child, subject, current_term_obj)
            if mark is not None:
                assessment_grades = []
                for a in Assessment.objects.filter(
                    class_assigned=selected_child.current_class,
                    subject=subject,
                    term_id=selected_term_id,
                ).order_by('assessment_date'):
                    grade = Grade.objects.filter(assessment=a, student=selected_child).first()
                    if grade:
                        grade.score = round((grade.score / a.max_score) * 100, 1)
                        grade.assessment = a
                        assessment_grades.append(grade)
                grade_summaries.append({
                    'subject': subject,
                    'average_score': mark,
                    'grade_letter': get_grade_letter(mark),
                    'assessments': assessment_grades,
                })

    overall_average = 0
    if grade_summaries:
        overall_average = round(sum(g['average_score'] for g in grade_summaries) / len(grade_summaries), 1)

    context = {
        'parent': parent,
        'children': parent_student_links,
        'selected_child': selected_child,
        'terms': terms,
        'selected_term': str(selected_term_id),
        'current_term_obj': current_term_obj,
        'grade_summaries': grade_summaries,
        'overall_average': overall_average,
        'subjects_count': len(grade_summaries),
    }
    return render(request, 'grades/parent_grades.html', context)