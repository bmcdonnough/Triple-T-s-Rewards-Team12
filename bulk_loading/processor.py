import os
import csv
from datetime import datetime
from flask import current_app
from models import db, User, Sponsor, Driver, Role, AuditLog

class BulkLoadProcessor:
    """
    Processes bulk loading files for the Triple-T's Rewards system
    """
    
    def __init__(self, file_path, mode='admin'):
        """
        Initialize the bulk loading processor
        
        Args:
            file_path (str): Path to the bulk loading file
            mode (str): 'admin' or 'sponsor' mode
        """
        self.file_path = file_path
        self.mode = mode
        self.log_file = None
        self.results = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'sponsors_created': 0,
            'drivers_created': 0
        }
        
        # Create log directory if it doesn't exist
        logs_dir = os.path.join(current_app.root_path, 'logs')
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
            
        # Create log file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_file_path = os.path.join(logs_dir, f'bulk_load_{timestamp}.csv')
        self.log_file = open(self.log_file_path, 'w', newline='')
        self.csv_writer = csv.writer(self.log_file)
        self.csv_writer.writerow(['Line Number', 'Record Type', 'Status', 'Details', 'Error'])
    
    def process_file(self):
        """
        Process the bulk loading file
        
        Returns:
            dict: Results of the processing
        """
        try:
            with open(self.file_path, 'r') as file:
                lines = file.readlines()
                
            for line_num, line in enumerate(lines, 1):
                if not line.strip():
                    continue
                    
                data = line.strip().split('|')
                if not data:
                    continue
                    
                record_type = data[0].upper()
                self.results['total'] += 1
                
                try:
                    if self.mode == 'admin':
                        self._process_admin_record(record_type, data, line_num)
                    else:
                        self._process_sponsor_record(record_type, data, line_num)
                except Exception as e:
                    self.results['failed'] += 1
                    self._log_result(line_num, record_type, 'Failed', str(data), str(e))
                    db.session.rollback()
                    
            # Close the log file
            if self.log_file:
                self.log_file.close()
                
            return self.results
        except Exception as e:
            if self.log_file:
                self.log_file.close()
            raise e
    
    def _process_admin_record(self, record_type, data, line_num):
        """
        Process a record in admin mode
        
        Args:
            record_type (str): Type of record ('O', 'D', 'S')
            data (list): Record data
            line_num (int): Line number in the file
        """
        if record_type == 'S':
            # Create sponsor
            if len(data) >= 5:
                org_name, first_name, last_name, email = data[1], data[2], data[3], data[4]
                self._create_sponsor(org_name, first_name, last_name, email, line_num)
            else:
                self.results['failed'] += 1
                self._log_result(line_num, record_type, 'Failed', str(data), 'Insufficient data for sponsor record')
                
        elif record_type == 'D':
            # Create driver
            if len(data) >= 6:  # Need one more field for license number
                org_name, first_name, last_name, email, license_number = data[1], data[2], data[3], data[4], data[5]
                self._create_driver(org_name, first_name, last_name, email, license_number, line_num)
            else:
                self.results['failed'] += 1
                self._log_result(line_num, record_type, 'Failed', str(data), 'Insufficient data for driver record')
                
        else:
            self.results['failed'] += 1
            self._log_result(line_num, record_type, 'Failed', str(data), f'Unknown record type: {record_type}')
    
    def _process_sponsor_record(self, record_type, data, line_num):
        """
        Process a record in sponsor mode
        
        Args:
            record_type (str): Type of record ('D')
            data (list): Record data
            line_num (int): Line number in the file
        """
        # This will be implemented later for sponsor mode
        pass
    
    def _create_sponsor(self, org_name, first_name, last_name, email, line_num):
        """
        Create a new sponsor user and organization
        
        Args:
            org_name (str): Organization name
            first_name (str): First name
            last_name (str): Last name
            email (str): Email address
            line_num (int): Line number in the file
        """
        # Check if email already exists
        existing_user = User.query.filter_by(EMAIL=email).first()
        if existing_user:
            self.results['failed'] += 1
            self._log_result(line_num, 'S', 'Failed', f'{first_name} {last_name} ({email})', f'Email already exists: {email}')
            return
        
        # Check if organization already exists
        existing_sponsor = Sponsor.query.filter_by(ORG_NAME=org_name).first()
        if existing_sponsor:
            self.results['failed'] += 1
            self._log_result(line_num, 'S', 'Failed', f'{first_name} {last_name} ({email})', f'Organization already exists: {org_name}')
            return
        
        try:
            # Generate a unique username
            username = self._generate_unique_username(first_name, last_name)
            
            # Create the user
            new_user = User(
                USERNAME=username,
                USER_TYPE=Role.SPONSOR,
                FNAME=first_name,
                LNAME=last_name,
                EMAIL=email,
                CREATED_AT=datetime.now(),
                IS_ACTIVE=1,
                FAILED_ATTEMPTS=0,
                IS_LOCKED_OUT=0
            )
            
            # Generate a random password
            password = new_user.admin_set_new_pass()
            
            db.session.add(new_user)
            db.session.flush()  # Get the user ID
            
            # Create the sponsor
            new_sponsor = Sponsor(
                SPONSOR_ID=new_user.USER_CODE,
                ORG_NAME=org_name,
                STATUS="Pending"
            )
            
            db.session.add(new_sponsor)
            db.session.commit()
            
            # Log the event
            self._log_audit_event(new_user.USER_CODE, 'sponsor_created_via_bulk_load', f'Created sponsor: {first_name} {last_name}, Org: {org_name}')
            
            self.results['success'] += 1
            self.results['sponsors_created'] += 1
            self._log_result(line_num, 'S', 'Success', f'{first_name} {last_name} ({email})', f'Username: {username}, Password: {password}')
        except Exception as e:
            db.session.rollback()
            self.results['failed'] += 1
            self._log_result(line_num, 'S', 'Failed', f'{first_name} {last_name} ({email})', f'Database error: {str(e)}')
            raise e
    
    def _create_driver(self, org_name, first_name, last_name, email, license_number, line_num):
        """
        Create a new driver user
        
        Args:
            org_name (str): Organization name (sponsor org)
            first_name (str): First name
            last_name (str): Last name
            email (str): Email address
            license_number (str): Driver license number
            line_num (int): Line number in the file
        """
        # Check if email already exists
        existing_user = User.query.filter_by(EMAIL=email).first()
        if existing_user:
            self.results['failed'] += 1
            self._log_result(line_num, 'D', 'Failed', f'{first_name} {last_name} ({email})', f'Email already exists: {email}')
            return
            
        # Check if the sponsor organization exists
        sponsor = Sponsor.query.filter_by(ORG_NAME=org_name).first()
        if not sponsor:
            self.results['failed'] += 1
            self._log_result(line_num, 'D', 'Failed', f'{first_name} {last_name} ({email})', f'Sponsor organization not found: {org_name}')
            return
            
        try:
            # Generate a unique username
            username = self._generate_unique_username(first_name, last_name)
            
            # Create the user
            new_user = User(
                USERNAME=username,
                USER_TYPE=Role.DRIVER,
                FNAME=first_name,
                LNAME=last_name,
                EMAIL=email,
                CREATED_AT=datetime.now(),
                IS_ACTIVE=1,
                FAILED_ATTEMPTS=0,
                IS_LOCKED_OUT=0
            )
            
            # Generate a random password
            password = new_user.admin_set_new_pass()
            
            db.session.add(new_user)
            db.session.flush()  # Get the user ID
            
            # Create the driver
            new_driver = Driver(
                DRIVER_ID=new_user.USER_CODE,
                LICENSE_NUMBER=license_number
            )
            
            db.session.add(new_driver)
            
            # Create a driver application to the sponsor
            from models import DriverApplication
            application = DriverApplication(
                DRIVER_ID=new_user.USER_CODE,
                SPONSOR_ID=sponsor.SPONSOR_ID,
                STATUS="Pending"
            )
            db.session.add(application)
            
            db.session.commit()
            
            # Log the event
            self._log_audit_event(new_user.USER_CODE, 'driver_created_via_bulk_load', 
                                 f'Created driver: {first_name} {last_name}, Applied to sponsor: {org_name}')
            
            self.results['success'] += 1
            self.results['drivers_created'] += 1
            self._log_result(line_num, 'D', 'Success', f'{first_name} {last_name} ({email})', f'Username: {username}, Password: {password}')
        except Exception as e:
            db.session.rollback()
            self.results['failed'] += 1
            self._log_result(line_num, 'D', 'Failed', f'{first_name} {last_name} ({email})', f'Database error: {str(e)}')
            raise e
    
    def _generate_unique_username(self, first_name, last_name):
        """
        Generate a unique username based on first and last name
        
        Args:
            first_name (str): First name
            last_name (str): Last name
            
        Returns:
            str: Unique username
        """
        import random
        
        # Create base username (first initial + last name, all lowercase)
        base_username = (first_name[0] + last_name).lower()
        
        # Remove non-alphanumeric characters
        base_username = ''.join(c for c in base_username if c.isalnum())
        
        # Check if username exists
        username = base_username
        counter = 1
        
        while User.query.filter_by(USERNAME=username).first():
            # If username exists, add a number to the end
            username = f"{base_username}{counter}"
            counter += 1
            
            # If we've tried too many times, add some randomness
            if counter > 100:
                username = f"{base_username}{random.randint(1000, 9999)}"
                if not User.query.filter_by(USERNAME=username).first():
                    break
        
        return username
    
    def _log_result(self, line_num, record_type, status, details, message):
        """
        Log a result to the CSV file
        
        Args:
            line_num (int): Line number in the file
            record_type (str): Type of record
            status (str): 'Success' or 'Failed'
            details (str): Record details
            message (str): Additional message
        """
        if self.csv_writer:
            self.csv_writer.writerow([line_num, record_type, status, details, message])
    
    def _log_audit_event(self, user_id, event_type, details):
        """
        Log an audit event to the database
        
        Args:
            user_id (int): User ID
            event_type (str): Type of event
            details (str): Event details
        """
        log_entry = AuditLog(
            EVENT_TYPE=event_type,
            DETAILS=details,
            CREATED_AT=datetime.now()
        )
        db.session.add(log_entry)
        # No commit needed here as it's part of a larger transaction