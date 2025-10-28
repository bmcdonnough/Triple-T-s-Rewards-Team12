# triple-ts-rewards/triple-t-s-rewards/Triple-T-s-Rewards-72ca7a46f1915a7f669f3692e9b77d23b248eaee/sponsor/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from common.decorators import role_required
from common.logging import log_audit_event, DRIVER_POINTS
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from models import User, Role, StoreSettings, db, DriverApplication, Sponsor, Notification
from extensions import db
import secrets
import string
import bcrypt

# Blueprint for sponsor-related routes
sponsor_bp = Blueprint('sponsor_bp', __name__, template_folder="../templates")

def driver_query_for_sponsor(sponsor_id):
    return db.session.query(User).filter(User.USER_TYPE == Role.DRIVER, User.SPONSOR_ID == sponsor_id).all()

def next_user_code():
    last_user = User.query.order_by(User.USER_CODE.desc()).first()
    return (last_user.USER_CODE + 1) if last_user else 1

def generate_temp_password(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))

@sponsor_bp.route("/users/new", methods=["GET", "POST"])
@role_required(Role.SPONSOR, allow_admin=True)
def _next_user_code():
    last = User.query.order_by(User.USER_CODE.desc()).first()
    return (last.USER_CODE + 1) if last else 1

@sponsor_bp.route("/sponsor/users/new", methods=["GET", "POST"])
@role_required(Role.SPONSOR, allow_admin=True)
def create_sponsor_user():
    if request.method == "GET":
        return render_template("sponsor/create_user.html")

    # POST
    username = (request.form.get("username") or "").strip()

    if not username:
        flash("Username is required.", "danger")
        return redirect(url_for("sponsor_bp.create_sponsor_user"))

    # 1) Explicit duplicate check first
    if User.query.filter_by(USERNAME=username).first():
        flash("That username is already taken. Please pick another.", "danger")
        return redirect(url_for("sponsor_bp.create_sponsor_user"))

    # 2) Build the user with ALL required fields filled
    new_user = User(
        USER_CODE=_next_user_code(),
        USERNAME=username,
        USER_TYPE=Role.SPONSOR,
        FNAME="Sponsor",
        LNAME="User",
        EMAIL=f"{username}@example.com",   # or collect a real email in the form
        CREATED_AT=datetime.utcnow(),
        POINTS=0,
        IS_ACTIVE=1,
        FAILED_ATTEMPTS=0,
        LOCKOUT_TIME=None,
        RESET_TOKEN=None,
        RESET_TOKEN_CREATED_AT=None,
        IS_LOCKED_OUT=0,
    )

    # Set a temporary password the sponsor can share with the new user
    # (Or generate one elsewhere and display it.)
    temp_password = "P@ssw0rd123"  # replace with your generator
    new_user.set_password(temp_password)

    try:
        db.session.add(new_user)
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        # Surface the REAL reason to your logs; keep message friendly to user
        print("IntegrityError creating sponsor user:", repr(e))
        flash("Could not create user (constraint error). Check required fields or username.", "danger")
        return redirect(url_for("sponsor_bp.create_sponsor_user"))
    except Exception as e:
        db.session.rollback()
        print("Error creating sponsor user:", repr(e))
        flash("Unexpected error creating user.", "danger")
        return redirect(url_for("sponsor_bp.create_sponsor_user"))

    log_audit_event("SPONSOR_CREATE_USER", f"by={current_user.USERNAME} new_user={username} role=sponsor")
    flash(f"Sponsor account created for '{username}'. Temporary password: {temp_password}", "success")
    return redirect(url_for("sponsor_bp.list_sponsor_users"))


@sponsor_bp.route("/users", methods=["GET"])
@role_required(Role.SPONSOR, allow_admin=True)
def list_sponsor_users():
    sponsors = User.query.filter_by(USER_TYPE=Role.SPONSOR).order_by(User.USERNAME.asc()).all()
    return render_template("sponsor/list_users.html", users=sponsors)


# Dashboard
@sponsor_bp.route('/dashboard')
@role_required(Role.SPONSOR, allow_admin=True)
def dashboard():
    return render_template('sponsor/dashboard.html')

# Update Store Settings
@sponsor_bp.route('/settings', methods=['GET', 'POST'])
@role_required(Role.SPONSOR, allow_admin=True)
def update_settings():
    settings = StoreSettings.query.first()
    if not settings:
        settings = StoreSettings()
        db.session.add(settings)
        db.session.commit()

    if request.method == 'POST':
        settings.ebay_category_id = request.form.get('ebay_category_id')
        settings.point_ratio = int(request.form.get('point_ratio'))
        db.session.commit()
        flash("Store settings updated successfully!", "success")
        return redirect(url_for('sponsor_bp.update_settings'))

    return render_template("sponsor/settings.html", settings=settings)


@sponsor_bp.route('/points', methods=['GET'])
@role_required(Role.SPONSOR, allow_admin=True)
def manage_points_page():
    """Display all drivers for awarding or removing points, with search and active/inactive filtering."""
    search_query = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()  # "active" or "inactive"

    query = User.query.filter_by(USER_TYPE=Role.DRIVER)

    # Apply exact username search (case-insensitive)
    if search_query:
        query = query.filter(db.func.lower(User.USERNAME) == search_query.lower())

    # Apply active/inactive filter
    if status_filter == "active":
        query = query.filter(User.IS_ACTIVE == 1)
    elif status_filter == "inactive":
        query = query.filter(User.IS_ACTIVE == 0)

    drivers = query.all()
    return render_template('sponsor/points.html', drivers=drivers)


@sponsor_bp.route('/points/<int:driver_id>', methods=['POST'])
@role_required(Role.SPONSOR, allow_admin=True)
def manage_points(driver_id):
    """
    Allows sponsors to award or remove points from a driver.
    The form must include:
      - 'action' = 'award' or 'remove'
      - 'points' = integer value
      - optional 'reason' (for removals)
    """
    driver = User.query.get_or_404(driver_id)
    action = request.form.get('action')
    points = request.form.get('points', type=int)
    reason = request.form.get('reason', '').strip() or "No reason provided."

    # Validate
    if not action or action not in ("award", "remove") or points is None or points <= 0:
        flash("Invalid request. Please provide an action (award/remove) and valid point amount.", "danger")
        return redirect(url_for('sponsor_bp.manage_points_page'))

    if action == "award":
        driver.POINTS += points
        db.session.commit()

        log_audit_event(
            DRIVER_POINTS,
            f"Sponsor {current_user.USERNAME} awarded {points} points to {driver.USERNAME}."
        )

        if getattr(driver, "wants_point_notifications", False):
            Notification.create_notification(
                recipient_code=driver.USER_CODE,
                sender_code=current_user.USER_CODE,
                message=f"You have been awarded {points} points by {current_user.USERNAME}."
            )

        flash(f"✅ Successfully awarded {points} points to {driver.USERNAME}.", "success")

    elif action == "remove":
        driver.POINTS -= points
        db.session.commit()

        log_audit_event(
            DRIVER_POINTS,
            f"Sponsor {current_user.USERNAME} removed {points} points from {driver.USERNAME}. Reason: {reason}"
        )

        if getattr(driver, "wants_point_notifications", False):
            Notification.create_notification(
                recipient_code=driver.USER_CODE,
                sender_code=current_user.USER_CODE,
                message=f"{points} points were removed from your account by {current_user.USERNAME}. Reason: {reason}"
            )

        flash(f"⚠️ Removed {points} points from {driver.USERNAME}.", "info")

    return redirect(url_for('sponsor_bp.manage_points_page'))


# Add a New Driver
@sponsor_bp.route('/add_user', methods=['GET', 'POST'])
@role_required(Role.SPONSOR, allow_admin=True)
def add_user():
    if request.method == 'POST':
        name = request.form.get('name')
        username = request.form.get('username')
        email = request.form.get('email')

        existing_user = User.query.filter(
            (User.USERNAME == username) | (User.EMAIL == email)
        ).first()
        if existing_user:
            flash(f"Username or email already exists.", "danger")
            return redirect(url_for('sponsor_bp.add_user'))
        
        # Find the highest existing USER_CODE and increment it
        last_user = User.query.order_by(User.USER_CODE.desc()).first()
        if last_user:
            new_user_code = last_user.USER_CODE + 1
        else:
            # Starting code for the first user if the table is empty
            new_user_code = 1

        last_user = User.query.order_by(User.USER_CODE.desc()).first()
        if last_user:
            new_user_code = last_user.USER_CODE + 1
        else:
            new_user_code = 1

        new_driver = User(
            USER_CODE=new_user_code, 
            USERNAME=username,
            EMAIL=email,
            USER_TYPE=Role.DRIVER,
            FNAME="New",
            LNAME="Driver",
            CREATED_AT=datetime.utcnow(),
            IS_ACTIVE=1,
            IS_LOCKED_OUT=0
        )
        new_pass = new_driver.set_password()

        db.session.add(new_driver)
        db.session.commit()

        flash(f"Driver '{username}' has been created! Temporary Password: {new_pass}", "success")
        return redirect(url_for('sponsor_bp.dashboard'))
        
    # Show the form to add a new driver
    return render_template('sponsor/add_user.html')

def get_accepted_drivers_for_sponsor(sponsor_user_code):
    """
    Retrieves all drivers who have an 'Accepted' application status 
    with the given sponsor_user_code using a two-step query for stability.
    """
    # Step 1: Filter the DriverApplication table for accepted apps for this sponsor
    accepted_apps = DriverApplication.query.filter(
        DriverApplication.SPONSOR_ID == sponsor_user_code,
        DriverApplication.STATUS == "Accepted" 
    ).all()

    # If no accepted applications, return an empty list immediately
    if not accepted_apps:
        return []

    # Step 2: Get the list of DRIVER_ID codes from the accepted applications
    driver_codes = [app.DRIVER_ID for app in accepted_apps]

    # Step 3: Filter the User table to get the full driver objects
    drivers = User.query.filter(User.USER_CODE.in_(driver_codes)).all()

    return drivers

@sponsor_bp.route('/drivers', methods=['GET'])
@role_required(Role.SPONSOR, allow_admin=True)
def driver_management():
    drivers = get_accepted_drivers_for_sponsor(current_user.USER_CODE)
    return render_template('sponsor/my_organization_drivers.html', drivers=drivers)

# Sponsor Application
@sponsor_bp.route("/applications")
@login_required
def review_driver_applications():
    apps = DriverApplication.query.filter_by(SPONSOR_ID=current_user.USER_CODE, STATUS="Pending").all()
    return render_template("sponsor/review_driver_applications.html", applications=apps)

@sponsor_bp.route("/applications/<int:app_id>/<decision>")
@login_required
def driver_decision(app_id, decision):
    app = DriverApplication.query.get_or_404(app_id)
    if decision == "accept":
        app.STATUS = "Accepted"
    else:
        app.STATUS = "Rejected"
    db.session.commit()
    flash(f"Driver application {decision}ed!", "info")
    return redirect(url_for("sponsor_bp.review_driver_applications"))

# Update Contact Information
@sponsor_bp.route('/update_info', methods=['GET', 'POST'])
@role_required(Role.DRIVER, Role.SPONSOR, allow_admin=True, redirect_to='auth.login')
def update_info():
    from extensions import db
    
    sponsor = None
    if current_user.USER_TYPE == "sponsor":
        sponsor = Sponsor.query.get(current_user.USER_CODE)
    
    if request.method == 'POST':
        email = request.form.get('email').strip()
        phone = request.form.get('phone').strip()

        # Basic email validation
        if not email or '@' not in email:
            flash('Please enter a valid email address.', 'danger')
            return redirect(url_for('sponsor_bp.update_info'))
            
        # Check if email already exists for another user
        if User.query.filter(User.EMAIL == email, User.USER_CODE != current_user.USER_CODE).first():
            flash('Email already in use.', 'danger')
            return redirect(url_for('sponsor_bp.update_info'))
        
        # Basic phone validation (optional)
        if phone and (not phone.isdigit() or len(phone) < 10):
            flash('Please enter a valid phone number.', 'danger')
            return redirect(url_for('sponsor_bp.update_contact'))
        
        # Check if phone already exists for another user
        if phone and User.query.filter(User.PHONE == phone, User.USER_CODE != current_user.USER_CODE).first():
            flash('Phone number already in use.', 'danger')
            return redirect(url_for('sponsor_bp.update_contact'))
        
        try:
            current_user.EMAIL = email
            current_user.PHONE = phone

            db.session.commit()
            flash('Contact information updated successfully!', 'success')
            return redirect(url_for('sponsor_bp.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while updating your information', 'danger')
            return redirect(url_for('sponsor_bp.update_info'))

    return render_template('sponsor/update_info.html', user=current_user, sponsor=sponsor)

# Update Password
@sponsor_bp.route('/change_password', methods=['GET', 'POST'])
@role_required(Role.DRIVER, Role.SPONSOR, allow_admin=True, redirect_to='auth.login')
def change_password():
    from extensions import db

    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        # Verify current password
        if not bcrypt.check_password_hash(current_user.PASS, current_password):
            flash('Current password is incorrect.', 'danger')
            return redirect(url_for('sponsor_bp.change_password'))

        # Validate new password
        if new_password != confirm_password:
            flash('New passwords do not match.', 'danger')
            return redirect(url_for('sponsor_bp.change_password'))
        
        if len(new_password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return redirect(url_for('sponsor_bp.change_password'))
        
        # Update password and email
        try:
            hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
            current_user.PASS = hashed_password
            db.session.commit()
            flash('Information updated successfully!', 'success')
            return redirect(url_for('sponsor_bp.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while updating your information', 'danger')
            return redirect(url_for('sponsor_bp.change_password'))

    return render_template('sponsor/update_info.html', user=current_user)