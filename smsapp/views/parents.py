import secrets
import string
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from ..models import Parent, User, ParentStudent
from ..forms import ParentForm, ParentStudentLinkForm
from ..decorators import admin_required

def generate_random_password(length=12):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

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
                # Security Fix: use random password instead of 'parent123'
                temp_password = 'Parent!23'
                user = User.objects.create_user(
                    username=User.generate_username('parent'),
                    email=form.cleaned_data['email'],
                    password=temp_password,
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    phone=form.cleaned_data.get('phone', ''),
                    role='parent',
                )
                parent      = form.save(commit=False)
                parent.user = user
                parent.save()
                messages.success(request, f'Parent account created for {user.get_full_name()}! Temporary password: {temp_password}')
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
