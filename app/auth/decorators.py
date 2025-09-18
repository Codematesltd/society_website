from functools import wraps
from flask import session, redirect, url_for, request, current_app


def login_required(view_func):
    """Redirect to auth.login if no user session is present."""
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        try:
            # treat any truthy session email as authenticated
            if not session.get('email'):
                # Preserve original destination (optional)
                try:
                    next_url = request.path or '/'
                except Exception:
                    next_url = '/'
                # Could add ?next=<path> if you later want post-login redirect support
                return redirect(url_for('auth.login'))
            return view_func(*args, **kwargs)
        except Exception as e:
            current_app.logger.error(f"Authentication error: {str(e)}")
            # Clear potentially corrupted session
            session.clear()
            return redirect(url_for('auth.login'))
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
