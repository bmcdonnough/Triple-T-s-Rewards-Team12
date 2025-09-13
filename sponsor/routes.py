from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models import Role
from driver.decorators import role_required

sponsor_bp = Blueprint('sponsor', __name__, template_folder="../templates")

@sponsor_bp.get('/dashboard')
@login_required
@role_required(Role.SPONSOR)
def dashboard():
    return render_template('sponsor/dashboard.html')