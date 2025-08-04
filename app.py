import os
from flask import Flask
from app import create_app

app = create_app()

# tell Jinja about our custom templates directory
from jinja2 import ChoiceLoader, FileSystemLoader
app.jinja_loader = ChoiceLoader([
    FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates')),
    app.jinja_loader
])


if __name__ == "__main__":
    app.run(debug=True)
