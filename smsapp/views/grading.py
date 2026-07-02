from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..models import Assessment, SchoolClass, Subject, Term, Grade, ClassSubjectTeacher, Student, Parent, ParentStudent
from ..forms import AssessmentCreationForm
from ..utils import get_term_subject_mark, get_grade_letter

@login_required
def create_assessment(request):
    if request.user.role not in ['admin', 'teacher']:
        messages.error(request, 'You do not have permission to create assessments.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = AssessmentCreationForm(request.POST)
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
        form = AssessmentCreationForm()

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
        form = AssessmentCreationForm(request.POST, instance=assessment)
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
        form = AssessmentCreationForm(instance=assessment)

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
    target_class = student.get_class_for_term(current_term_obj) if current_term_obj else None
    if current_term_obj and target_class:
        subject_ids = Assessment.objects.filter(
            class_assigned=target_class,
            term_id=selected_term_id,
        ).values_list('subject_id', flat=True).distinct()
        for subject_id in subject_ids:
            subject = Subject.objects.get(pk=subject_id)
            mark = get_term_subject_mark(student, subject, current_term_obj)
            if mark is not None:
                assessment_grades = []
                for a in Assessment.objects.filter(
                    class_assigned=target_class,
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


@login_required
def parent_grades_view(request):
    if request.user.role != 'parent':
        messages.error(request, 'Only parents can access this page.')
        return redirect('dashboard')
    
    try:
        parent = request.user.parent_profile
    except Parent.DoesNotExist:
        messages.error(request, 'Parent profile not found.')
        return redirect('dashboard')
    
    parent_student_links = ParentStudent.objects.filter(
        parent=parent
    ).select_related('student__user')
    
    children_ids = parent_student_links.values_list('student_id', flat=True)
    
    if not children_ids:
        messages.info(request, 'No children linked to your account yet.')
        return redirect('parent_dashboard')
    
    selected_child_id = request.GET.get('child')
    if selected_child_id:
        if int(selected_child_id) not in children_ids:
            messages.error(request, 'Invalid child selected.')
            return redirect('parent_grades')
        selected_child = get_object_or_404(Student.objects.select_related('user'), pk=selected_child_id)
    else:
        selected_child = parent_student_links.first().student
    
    terms = Term.objects.all().order_by('-start_date')
    selected_term_id = request.GET.get('term', terms.first().id if terms.exists() else None)
    current_term_obj = get_object_or_404(Term, pk=selected_term_id) if selected_term_id else None
    
    grade_summaries = []
    target_class = selected_child.get_class_for_term(current_term_obj) if current_term_obj else None
    if current_term_obj and target_class:
        subject_ids = Assessment.objects.filter(
            class_assigned=target_class,
            term_id=selected_term_id,
        ).values_list('subject_id', flat=True).distinct()
        for subject_id in subject_ids:
            subject = Subject.objects.get(pk=subject_id)
            mark = get_term_subject_mark(selected_child, subject, current_term_obj)
            if mark is not None:
                assessment_grades = []
                for a in Assessment.objects.filter(
                    class_assigned=target_class,
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
