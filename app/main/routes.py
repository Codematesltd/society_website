from flask import render_template, redirect, url_for
from . import main_bp

@main_bp.route('/')
def home_redirect():
    return render_template('landing_page.html')

@main_bp.route('/login')
def login_redirect():
    return redirect(url_for('auth.login'))
