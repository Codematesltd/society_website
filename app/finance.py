from flask import Blueprint, render_template

finance_bp = Blueprint('finance', __name__)

@finance_bp.route('/surety_info')
def surety_info():
    return render_template('surety_info.html')