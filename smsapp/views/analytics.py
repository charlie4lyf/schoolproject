from collections import Counter
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from ..models import Term, Student, Assessment, Subject, SchoolClass, Teacher, ClassSubjectTeacher, AcademicYear, ParentStudent
from ..decorators import admin_required
from ..utils import get_term_subject_mark, get_grade_letter

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
            target_class = student.get_class_for_term(term)
            if target_class:
                subject_ids = Assessment.objects.filter(
                    term=term,
                    class_assigned=target_class,
                ).values_list('subject_id', flat=True).distinct()
                for subject_id in subject_ids:
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
    for year_data in history.values():
        for data in year_data.values():
            all_marks.append(data['average'])
    overall = sum(all_marks) / len(all_marks) if all_marks else 0

    return render(request, 'reports/student_transcript.html', {
        'student':          student,
        'history':          history,
        'overall_average':  round(overall, 1),
        'generated_date':   timezone.now(),
    })
