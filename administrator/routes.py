from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models import Role
from driver.decorators import role_required

administrator_bp = Blueprint("administrator", __name__, template_folder="../templates")

@administrator_bp.get("/dashboard")
@login_required 
@role_required(Role.ADMINISTRATOR)
def dashboard():
    return render_template("administrator/dashboard.html")
