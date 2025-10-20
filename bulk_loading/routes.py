from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, send_from_directory
from flask_login import login_required, current_user
from common.decorators import role_required
from models import Role, db, AuditLog
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from bulk_loading.processor import BulkLoadProcessor

bulk_loading_bp = Blueprint('bulk_loading_bp', __name__, template_folder="../templates")

@bulk_loading_bp.route('/admin/bulk-loading', methods=['GET', 'POST'])
@role_required(Role.ADMINISTRATOR, redirect_to='auth.login')
def admin_bulk_loading():
    """
    Admin bulk loading page
    """
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
            
        file = request.files['file']
        
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)
            
        if file and _allowed_file(file.filename):
            # Create uploads directory if it doesn't exist
            uploads_dir = os.path.join(current_app.root_path, 'uploads')
            if not os.path.exists(uploads_dir):
                os.makedirs(uploads_dir)
                
            # Save the file with timestamp to prevent overwriting
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{timestamp}_{secure_filename(file.filename)}"
            file_path = os.path.join(uploads_dir, filename)
            file.save(file_path)
            
            try:
                # Process the file
                processor = BulkLoadProcessor(file_path, mode='admin')
                results = processor.process_file()
                
                # Log the event
                _log_audit_event('bulk_load_processed', f"Processed bulk load file: {file.filename}, "
                                f"Total: {results['total']}, Success: {results['success']}, "
                                f"Failed: {results['failed']}, Sponsors: {results['sponsors_created']}, "
                                f"Drivers: {results['drivers_created']}")
                
                # Flash message with results
                flash(f"File processed. Total: {results['total']}, Success: {results['success']}, "
                      f"Failed: {results['failed']}, Sponsors created: {results['sponsors_created']}, "
                      f"Drivers created: {results['drivers_created']}", 'success')
                
                # Save log file path for download
                log_file_path = processor.log_file_path
                log_filename = os.path.basename(log_file_path)
                
                return render_template('administrator/bulk_loading.html', 
                                     results=results, 
                                     log_filename=log_filename)
            except Exception as e:
                flash(f"Error processing file: {str(e)}", 'danger')
                return redirect(request.url)
        else:
            flash('File type not allowed. Please upload a .txt file.', 'danger')
            return redirect(request.url)
            
    return render_template('administrator/bulk_loading.html')

@bulk_loading_bp.route('/download-log/<filename>')
@role_required(Role.ADMINISTRATOR, redirect_to='auth.login')
def download_log(filename):
    """
    Download log file
    """
    logs_dir = os.path.join(current_app.root_path, 'logs')
    return send_from_directory(logs_dir, filename, as_attachment=True)

@bulk_loading_bp.route('/download-template')
@role_required(Role.ADMINISTRATOR, Role.SPONSOR, redirect_to='auth.login')
def download_template():
    """
    Download template file
    """
    if current_user.USER_TYPE == Role.ADMINISTRATOR:
        template_name = 'admin_bulk_template.txt'
    else:
        template_name = 'sponsor_bulk_template.txt'
        
    templates_dir = os.path.join(current_app.root_path, 'bulk_loading', 'templates')
    return send_from_directory(templates_dir, template_name, as_attachment=True)

def _allowed_file(filename):
    """
    Check if file extension is allowed
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'txt'

def _log_audit_event(event_type, details):
    """
    Log an audit event
    """
    log_entry = AuditLog(
        EVENT_TYPE=event_type,
        DETAILS=details,
        CREATED_AT=datetime.utcnow()
    )
    db.session.add(log_entry)
    db.session.commit()