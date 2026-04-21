from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps


def admin_required(view_func):
    """
    Decorator to check if user is an admin
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if request.user.role != 'admin':
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def teacher_required(view_func):
    """
    Decorator to check if user is a teacher
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if request.user.role != 'teacher':
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def student_required(view_func):
    """
    Decorator to check if user is a student
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if request.user.role != 'student':
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def parent_required(view_func):
    """
    Decorator to check if user is a parent
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if request.user.role != 'parent':
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def role_required(allowed_roles):
    """
    Decorator to check if user has one of the allowed roles
    Usage: @role_required(['admin', 'teacher'])
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            if request.user.role not in allowed_roles:
                messages.error(request, 'You do not have permission to access this page.')
                return redirect('dashboard')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
