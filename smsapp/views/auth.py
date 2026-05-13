from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..decorators import admin_required, teacher_required, student_required, parent_required

def user_login(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            if not remember_me:
                request.session.set_expiry(0)
            messages.success(request, f'Welcome back, {user.get_full_name()}!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'registration/login.html')


def user_logout(request):
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('login')


@login_required
def dashboard(request):
    user = request.user
    role_redirect = {
        'admin':   'admin_dashboard',
        'teacher': 'teacher_dashboard',
        'student': 'student_dashboard',
        'parent':  'parent_dashboard',
    }
    target = role_redirect.get(user.role)
    if target:
        return redirect(target)
    messages.error(request, 'Invalid user role.')
    return redirect('login')
