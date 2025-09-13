from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models import Role
from .decorators import role_required

driver_bp = Blueprint('driver', __name__, template_folder="../templates")

@driver_bp.get('/dashboard')
@login_required
@role_required(Role.DRIVER)
def dashboard():
    return render_template('driver/dashboard.html')