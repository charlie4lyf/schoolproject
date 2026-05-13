import secrets
import string
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from ..models import User, Teacher, Student, Parent
from ..forms import UserAdminForm, RoleChangeForm
from ..decorators import admin_required

def generate_random_password(length=12):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

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
            # Security Fix: Use random password instead of relying on default (if any)
            temp_password = generate_random_password()
            user = form.save(commit=False)
            user.role = 'admin'
            user.username = User.generate_username('admin')
            user.set_password(temp_password)
            user.save()
            messages.success(request, f'Admin user {user.get_full_name()} created! Temporary password: {temp_password}')
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
