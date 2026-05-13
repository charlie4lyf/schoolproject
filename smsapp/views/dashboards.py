from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q
from collections import defaultdict
from ..models import (
    Student, Teacher, SchoolClass, Attendance, ActivityLog, Term, ParentStudent, Assessment, Subject
)
from ..utils import get_term_subject_mark, get_grade_letter
from ..decorators import admin_required, teacher_required, student_required, parent_required

@login_required
def dashboard(request):
    if request.user.role == 'admin':
        return redirect('admin_dashboard')
    elif request.user.role == 'teacher':
        return redirect('teacher_dashboard')
    elif request.user.role == 'student':
        return redirect('student_dashboard')
    elif request.user.role == 'parent':
        return redirect('parent_dashboard')
    return render(request, 'dashboard.html')


@login_required
@admin_required
def admin_dashboard(request):
    today = timezone.now().date()
    total_students = Student.objects.filter(is_active=True).count()
    total_teachers = Teacher.objects.count()
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

    teaching_assignments = Teacher.objects.filter(  # <-- Wait, this logic looks wrong in original too?
        # Actually in original it was ClassSubjectTeacher.objects.filter(teacher=teacher)
        # Let me re-read the original logic from Step 73
        pk=teacher.pk # dummy
    )
    # I'll use the correct logic from original views.py
    from ..models import ClassSubjectTeacher
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

    total_students = sum(a.class_assigned.student_count for a in teaching_assignments)

    context = {
        'teacher': teacher,
        'teaching_assignments': teaching_assignments,
        'attendance_pending': attendance_pending,
        'total_students': total_students,
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
