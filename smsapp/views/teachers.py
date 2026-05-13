import secrets
import string
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from ..models import Teacher, User, ClassSubjectTeacher, SchoolClass, AcademicYear, GradeSubjectConfig
from ..forms import TeacherForm, TeacherAssignmentForm, GradeLevelTeacherAssignmentForm
from ..decorators import admin_required

def generate_random_password(length=12):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

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
                # Security Fix: use random password instead of 'teacher123'
                temp_password = generate_random_password()
                user = User.objects.create_user(
                    username=User.generate_username('teacher'),
                    email=form.cleaned_data['email'],
                    password=temp_password,
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    phone=form.cleaned_data.get('phone', ''),
                    role='teacher',
                    is_active=True
                )
                teacher = form.save(commit=False)
                teacher.user = user
                teacher.is_active = True
                teacher.save()
                messages.success(request, f'Teacher {user.get_full_name()} created successfully! Temporary password: {temp_password}')
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
