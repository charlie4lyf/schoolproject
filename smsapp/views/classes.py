from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import models
from ..models import SchoolClass, AcademicYear, Teacher, GradeSubjectConfig, ClassSubjectTeacher, Student, StudentEnrollment, ActivityLog
from ..forms import ClassForm
from ..decorators import admin_required

@login_required
@admin_required
def class_list(request):
    """List all classes with their details"""
    from django.db.models import Count
    
    classes = SchoolClass.objects.select_related(
        'academic_year', 
        'class_teacher__user'
    ).annotate(
        total_students=Count('enrollments', filter=models.Q(enrollments__is_active=True), distinct=True),
        total_subjects=Count('subject_assignments', distinct=True)
    ).order_by('-academic_year', 'grade_level', 'name')
    
    return render(request, 'classes/class_list.html', {'classes': classes})


@login_required
@admin_required
def class_create(request):
    """Create a new class"""
    if request.method == 'POST':
        form = ClassForm(request.POST)
        if form.is_valid():
            class_obj = form.save()

            configs = GradeSubjectConfig.objects.filter(grade_level=class_obj.grade_level)
            for config in configs:
                ClassSubjectTeacher.objects.get_or_create(
                    class_assigned=class_obj,
                    subject=config.subject,
                    academic_year=class_obj.academic_year,
                    defaults={'teacher': None}
                )

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
    
    students = Student.objects.filter(
        enrollments__class_assigned=class_obj,
        enrollments__is_active=True,
        is_active=True
    ).select_related('user').order_by('user__last_name', 'user__first_name')
    
    subject_assignments = ClassSubjectTeacher.objects.filter(
        class_assigned=class_obj
    ).select_related('subject', 'teacher__user', 'academic_year').order_by('subject__name')
    
    compulsory_subjects = GradeSubjectConfig.objects.filter(
        grade_level=class_obj.grade_level,
        is_compulsory=True
    ).select_related('subject')
    
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
    
    enrollment = StudentEnrollment.objects.filter(
        student=student, class_assigned=class_obj, is_active=True
    ).first()
    
    if not enrollment:
        messages.error(request, 'Student is not enrolled in this class.')
        return redirect('class_detail', pk=class_id)
    
    if request.method == 'POST':
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
    
    subject_configs = GradeSubjectConfig.objects.filter(
        grade_level=class_obj.grade_level
    ).select_related('subject')
    
    assigned_subjects = ClassSubjectTeacher.objects.filter(
        class_assigned=class_obj,
        academic_year=academic_year
    ).values_list('subject_id', flat=True)
    
    if request.method == 'POST':
        created_count = 0
        for config in subject_configs:
            if config.subject.id not in assigned_subjects:
                ClassSubjectTeacher.objects.create(
                    class_assigned=class_obj,
                    subject=config.subject,
                    academic_year=academic_year,
                    teacher=None
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
