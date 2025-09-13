from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models import Role

common_bp = Blueprint('common', __name__, template_folder="../templates")

@common_bp.get('/')
def index():
    return render_template('common/index.html')

@common_bp.get('/after_login')
def after_login():
    if current_user.role == Role.ADMIN:
        return render_template('administrator/dashboard.html')
    elif current_user.role == Role.DRIVER:
        return render_template('driver/dashboard.html')
    elif current_user.role == Role.SPONSOR:
        return render_template('sponsor/dashboard.html')
    else:
        return render_template('common/index.html')
    return "unknown role", 403