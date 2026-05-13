from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from ..models import Assignment, AssignmentSubmission, StudentEnrollment, ParentStudent, SchoolClass, Subject, Student
from ..forms import AssignmentForm, StudentSubmissionForm, GradingForm
from ..decorators import teacher_required, student_required

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
