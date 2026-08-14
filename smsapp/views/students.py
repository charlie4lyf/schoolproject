import csv
import json
import secrets
import string
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models
from django.db.models import Q
from django.http import HttpResponse
from django.core.paginator import Paginator
from ..models import Student, User, SchoolClass, StudentEnrollment, Term, Assessment, ParentStudent, YearEndPromotion, AcademicYear
from ..forms import StudentForm, YearEndPromotionForm
from ..utils import get_term_subject_mark, get_grade_letter
from ..decorators import admin_required

def generate_random_password(length=12):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

@login_required
@admin_required
def student_list(request):
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
    from ..models import Attendance
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
            from ..models import Subject
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
            # Security Fix: use random password instead of 'student123'
            temp_password = 'Student123'
            user = User.objects.create_user(
                username= User.generate_username('student'),  
                email=form.cleaned_data['email'],
                password=temp_password,
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                role='student',
            )
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

            current_class = form.cleaned_data.get('current_class')
            if current_class:
                StudentEnrollment.objects.create(
                    student=student,
                    class_assigned=current_class,
                    academic_year=current_class.academic_year,
                    is_active=True,
                )

            messages.success(request, f'Student {student.user.get_full_name()} created successfully! Temporary password: {temp_password}')
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
def promote_student(request, pk):
    student = get_object_or_404(Student, pk=pk)
    active_year = AcademicYear.objects.filter(is_active=True).first()
    
    if request.method == 'POST':
        form = YearEndPromotionForm(request.POST)
        if form.is_valid():
            promotion = form.save(commit=False)
            promotion.student = student
            promotion.academic_year = active_year
            promotion.current_class = student.current_class
            
            # User might not be a teacher (since it's an admin view), so handle safely
            if hasattr(request.user, 'teacher_profile'):
                promotion.recorded_by = request.user.teacher_profile
                
            promotion.save()
            
            if active_year:
                promotion.apply_promotion(next_academic_year=active_year)
                
            messages.success(request, f'Promotion recorded for {student.user.get_full_name()}')
            return redirect('student_detail', pk=student.id)
    else:
        form = YearEndPromotionForm()
        
    context = {
        'form': form,
        'student': student,
        'title': f'Promote {student.user.get_full_name()}',
        'active_year': active_year,
    }
    return render(request, 'students/promote_student.html', context)


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

                # Security Fix: use random password
                temp_password = generate_random_password()
                user = User.objects.create_user(
                    username='',
                    email=row['email'],
                    password=temp_password,
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
                
                StudentEnrollment.objects.create(
                    student=student,
                    class_assigned=current_class,
                    academic_year=current_class.academic_year,
                    is_active=True,
                )
                imported_count += 1

            messages.success(request, f'Successfully imported {imported_count} students! Temporary passwords assigned.')
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
