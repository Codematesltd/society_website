import os
from flask import Flask, redirect, url_for, render_template
from app import create_app
from app.certificate import certificate_bp

app = create_app()

# tell Jinja about our custom templates directory
from jinja2 import ChoiceLoader, FileSystemLoader
app.jinja_loader = ChoiceLoader([
    FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates')),
    app.jinja_loader
])

app.register_blueprint(certificate_bp)

@app.route('/')
def home_redirect():
    return render_template('landing_page.html')

@app.route('/login')
def login_redirect():
    return redirect(url_for('auth.login'))

if __name__ == "__main__":
    app.run(debug=True)
