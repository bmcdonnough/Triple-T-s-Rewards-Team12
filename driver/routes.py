# triple-ts-rewards/triple-t-s-rewards/Triple-T-s-Rewards-72ca7a46f1915a7f669f3692e9b77d23b248eaee/driver/routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from common.decorators import role_required
from common.logging import DRIVER_POINTS
from models import Role, AuditLog, User, db, Sponsor, DriverApplication, Address, StoreSettings, Driver
from extensions import bcrypt

# Blueprint for driver-related routes
driver_bp = Blueprint('driver_bp', __name__, template_folder="../templates")

# Login
@driver_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Look up user by USERNAME
        user = User.query.filter_by(USERNAME=username).first()

        # Check password with bcrypt
        if user and user.check_password(password):
            login_user(user)
            flash("Login successful!", "success")
            return redirect(url_for('driver_bp.dashboard'))
        else:
            flash("Invalid username or password", "danger")

    # Looks inside templates/driver/login.html
    return render_template('driver/login.html')

# Dashboard
@driver_bp.route('/dashboard')
@role_required(Role.DRIVER, Role.SPONSOR, allow_admin=True, redirect_to='auth.login')
def dashboard():
    settings = StoreSettings.query.first()
    point_ratio = settings.point_ratio if settings else 10 # Default to 10 if not set
    return render_template('driver/dashboard.html', user=current_user, point_ratio=point_ratio)

# Point History
@driver_bp.route('/point_history')
@role_required(Role.DRIVER, allow_admin=True)
def point_history():
    events = AuditLog.query.filter(
        AuditLog.EVENT_TYPE == DRIVER_POINTS,
        AuditLog.DETAILS.like(f"%{current_user.USERNAME}%")
    ).order_by(AuditLog.CREATED_AT.desc()).all()
    return render_template("driver/point_history.html", events=events)

# Logout
@driver_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('auth.login'))

# Settings Page
@driver_bp.route('/settings', methods=['GET', 'POST'])
@role_required(Role.DRIVER, allow_admin=True)
def settings():
    if request.method == 'POST':
        wants_points = request.form.get('wants_point_notifications') == 'on'
        wants_orders = request.form.get('wants_order_notifications') == 'on'
        
        current_user.wants_point_notifications = wants_points
        current_user.wants_order_notifications = wants_orders
        db.session.commit()
        
        flash('Your settings have been updated!', 'success')
        return redirect(url_for('driver_bp.dashboard'))
        
    return render_template('driver/settings.html')

# Update Contact Information
@driver_bp.route('/update_info', methods=['GET', 'POST'])
@role_required(Role.DRIVER, Role.SPONSOR, allow_admin=True, redirect_to='auth.login')
def update_contact():
    from extensions import db
    
    driver = None
    if current_user.USER_TYPE == "driver":
        driver = Driver.query.get(current_user.USER_CODE)

    if request.method == 'POST':
        email = request.form.get('email')
        phone = request.form.get('phone')
        license_number = request.form.get('license_number') if driver else None

        # Basic email validation
        if not email or '@' not in email:
            flash('Please enter a valid email address.', 'danger')
            return redirect(url_for('driver_bp.update_contact'))
            
        # Check if email already exists for another user
        if User.query.filter(User.EMAIL == email, User.USER_CODE != current_user.USER_CODE).first():
            flash('Email already in use.', 'danger')
            return redirect(url_for('driver_bp.update_contact'))
        
        # Basic phone validation (optional)
        if phone and (not phone.isdigit() or len(phone) < 10):
            flash('Please enter a valid phone number.', 'danger')
            return redirect(url_for('driver_bp.update_contact'))
        
        # Check if phone already exists for another user
        if phone and User.query.filter(User.PHONE == phone, User.USER_CODE != current_user.USER_CODE).first():
            flash('Phone number already in use.', 'danger')
            return redirect(url_for('driver_bp.update_contact'))
        
        try:
            current_user.EMAIL = email
            current_user.PHONE = phone

            # Only drivers update license number
            if driver is not None and license_number is not None:
                driver.LICENSE_NUMBER = license_number

            db.session.commit()
            flash('Contact information updated successfully!', 'success')
            return redirect(url_for('driver_bp.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while updating your information', 'danger')
            return redirect(url_for('driver_bp.update_info'))
        
    return render_template('driver/update_info.html', user=current_user, driver=driver)

# Update Password
@driver_bp.route('/change_password', methods=['GET', 'POST'])
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
            return redirect(url_for('driver_bp.change_password'))

        # Validate new password
        if new_password != confirm_password:
            flash('New passwords do not match.', 'danger')
            return redirect(url_for('driver_bp.change_password'))
        
        if len(new_password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return redirect(url_for('driver_bp.change_password'))
        
        # Update password and email
        try:
            hashed_password = bcrypt.generate_password_hash(new_password).decode('utf-8')
            current_user.PASS = hashed_password
            db.session.commit()
            flash('Information updated successfully!', 'success')
            return redirect(url_for('driver_bp.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while updating your information', 'danger')
            return redirect(url_for('driver_bp.change_password'))
        
    return render_template('driver/update_info.html', user=current_user)

# Driver Application
@driver_bp.route("/driver_app", methods=["GET", "POST"])
@login_required
def apply_driver():
    sponsors = Sponsor.query.filter_by(STATUS="Approved").all()

    if request.method == "POST":
        sponsor_id = request.form["sponsor_id"]
        reason = request.form.get("reason", "")

        existing = DriverApplication.query.filter_by(
            DRIVER_ID=current_user.USER_CODE,
            SPONSOR_ID=sponsor_id
        ).first()

        if existing:
            flash("You already applied to this sponsor.", "warning")
        else:
            application = DriverApplication(
                DRIVER_ID=current_user.USER_CODE,
                SPONSOR_ID=sponsor_id,
                REASON=reason,
                STATUS="Pending",
                LICENSE_NUMBER=current_user.LICENSE_NUMBER if current_user else None
            )
            db.session.add(application)
            db.session.commit()
            flash("Application submitted successfully! Await sponsor review.", "success")

        return redirect(url_for("driver_bp.dashboard"))

    return render_template("driver/driver_app.html", sponsors=sponsors)

# Address Management
@driver_bp.route('/addresses')
@role_required(Role.DRIVER, allow_admin=True)
def addresses():
    return render_template('driver/addresses.html')

@driver_bp.route('/addresses/add', methods=['GET', 'POST'])
@role_required(Role.DRIVER, allow_admin=True)
def add_address():
    if request.method == 'POST':
        new_address = Address(
            user_id=current_user.USER_CODE,
            street=request.form['street'],
            city=request.form['city'],
            state=request.form['state'],
            zip_code=request.form['zip_code'],
            is_default=request.form.get('is_default') == 'on'
        )
        db.session.add(new_address)
        db.session.commit()
        flash('Address added successfully!', 'success')
        return redirect(url_for('driver_bp.addresses'))
    return render_template('driver/address_form.html')

@driver_bp.route('/addresses/edit/<int:address_id>', methods=['GET', 'POST'])
@role_required(Role.DRIVER, allow_admin=True)
def edit_address(address_id):
    address = Address.query.get_or_404(address_id)
    if request.method == 'POST':
        address.street = request.form['street']
        address.city = request.form['city']
        address.state = request.form['state']
        address.zip_code = request.form['zip_code']
        address.is_default = request.form.get('is_default') == 'on'
        db.session.commit()
        flash('Address updated successfully!', 'success')
        return redirect(url_for('driver_bp.addresses'))
    return render_template('driver/address_form.html', address=address)

@driver_bp.route('/addresses/delete/<int:address_id>', methods=['POST'])
@role_required(Role.DRIVER, allow_admin=True)
def delete_address(address_id):
    address = Address.query.get_or_404(address_id)
    db.session.delete(address)
    db.session.commit()
    flash('Address deleted successfully!', 'success')
    return redirect(url_for('driver_bp.addresses'))

@driver_bp.route('/addresses/set_default/<int:address_id>', methods=['POST'])
@role_required(Role.DRIVER, allow_admin=True)
def set_default_address(address_id):
    # First, unset any other default addresses
    Address.query.filter_by(user_id=current_user.USER_CODE, is_default=True).update({'is_default': False})
    # Then, set the new default address
    address = Address.query.get_or_404(address_id)
    address.is_default = True
    db.session.commit()
    flash('Default address has been updated!', 'success')
    return redirect(url_for('driver_bp.addresses'))
