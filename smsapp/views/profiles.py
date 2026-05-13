from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from ..models import Term, Assessment, Subject, Student, Teacher, Parent, ParentStudent, Attendance, ClassSubjectTeacher, ActivityLog
from ..forms import UserProfileForm, StudentProfileForm, TeacherProfileForm, ParentProfileForm, CustomPasswordChangeForm
from ..utils import get_term_subject_mark

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
