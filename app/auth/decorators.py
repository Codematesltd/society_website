from functools import wraps
from flask import session, redirect, url_for, request, current_app


def login_required(view_func):
    """Redirect to auth.login if no user session is present."""
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if not session.get('email'):
            return redirect(url_for('auth.login'))
        return view_func(*args, **kwargs)
    return wrapper


def role_required(*roles):
    """Ensure the logged-in user has one of the required roles (e.g., 'staff', 'members')."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            role = session.get('role')
            if not role or (roles and role not in roles):
                return redirect(url_for('auth.login'))
            return view_func(*args, **kwargs)
        return wrapper
    return decorator
