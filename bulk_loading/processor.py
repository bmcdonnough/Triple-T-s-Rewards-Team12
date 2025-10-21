import os
import csv
from datetime import datetime
from flask import current_app
from models import db, User, Sponsor, Driver, Role, AuditLog, Organization

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
            'organizations_created': 0,
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
        if record_type == 'O':
            # Create organization
            if len(data) >= 2:
                org_name = data[1]
                self._create_organization(org_name, line_num)
            else:
                self.results['failed'] += 1
                self._log_result(line_num, record_type, 'Failed', str(data), 'Insufficient data for organization record')
        
        elif record_type == 'S':
            # Create sponsor
            if len(data) >= 5:
                org_name, first_name, last_name, email = data[1], data[2], data[3], data[4]
                self._create_sponsor(org_name, first_name, last_name, email, line_num)
            else:
                self.results['failed'] += 1
                self._log_result(line_num, record_type, 'Failed', str(data), 'Insufficient data for sponsor record. Format: S|Organization|FirstName|LastName|Email')
                
        elif record_type == 'D':
            # Create driver
            if len(data) >= 5:  # Need 5 fields: D|org|first|last|email
                org_name, first_name, last_name, email = data[1], data[2], data[3], data[4]
                self._create_driver(org_name, first_name, last_name, email, line_num)
            else:
                self.results['failed'] += 1
                self._log_result(line_num, record_type, 'Failed', str(data), 'Insufficient data for driver record. Format: D|Organization|FirstName|LastName|Email')
                
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
        
        # Check if organization exists in Organizations table
        existing_org = Organization.query.filter_by(ORG_NAME=org_name).first()
        if not existing_org:
            self.results['failed'] += 1
            self._log_result(line_num, 'S', 'Failed', f'{first_name} {last_name} ({email})', f'Organization not found: {org_name}. Please create the organization first using an O record.')
            return
            
        # Check if there's already a sponsor for this organization
        existing_sponsor = Sponsor.query.filter_by(ORG_NAME=org_name).first()
        if existing_sponsor:
            self.results['failed'] += 1
            self._log_result(line_num, 'S', 'Failed', f'{first_name} {last_name} ({email})', f'Sponsor already exists for organization: {org_name}')
            return
        
        try:
            # Generate a unique username
            username = self._generate_unique_username(first_name, last_name)
            
            # Create the user (let USER_CODE auto-increment)
            new_user = User(
                USERNAME=username,
                USER_TYPE=Role.SPONSOR,
                FNAME=first_name,
                LNAME=last_name,
                EMAIL=email,
                CREATED_AT=datetime.now(),
                POINTS=0,
                wants_point_notifications=True,
                wants_order_notifications=True,
                IS_ACTIVE=1,
                FAILED_ATTEMPTS=0,
                IS_LOCKED_OUT=0
            )
            
            # Generate a random password
            password = new_user.admin_set_new_pass()
            
            db.session.add(new_user)
            db.session.commit()  # Commit the user first to get the auto-generated USER_CODE
            
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
    
    def _create_driver(self, org_name, first_name, last_name, email, line_num):
        """
        Create a new driver user
        
        Args:
            org_name (str): Organization name (sponsor org)
            first_name (str): First name
            last_name (str): Last name
            email (str): Email address
            line_num (int): Line number in the file
        """
        # Check if email already exists
        existing_user = User.query.filter_by(EMAIL=email).first()
        if existing_user:
            self.results['failed'] += 1
            self._log_result(line_num, 'D', 'Failed', f'{first_name} {last_name} ({email})', f'Email already exists: {email}')
            return
            
        # Check if the organization exists
        existing_org = Organization.query.filter_by(ORG_NAME=org_name).first()
        if not existing_org:
            self.results['failed'] += 1
            self._log_result(line_num, 'D', 'Failed', f'{first_name} {last_name} ({email})', f'Organization not found: {org_name}. Please create the organization first using an O record.')
            return
        try:
            # Generate a unique username
            username = self._generate_unique_username(first_name, last_name)
            
            # Create the user (let USER_CODE auto-increment)
            new_user = User(
                USERNAME=username,
                USER_TYPE=Role.DRIVER,
                FNAME=first_name,
                LNAME=last_name,
                EMAIL=email,
                CREATED_AT=datetime.now(),
                POINTS=0,
                wants_point_notifications=True,
                wants_order_notifications=True,
                IS_ACTIVE=1,
                FAILED_ATTEMPTS=0,
                IS_LOCKED_OUT=0
            )
            
            # Generate a random password
            password = new_user.admin_set_new_pass()
            
            db.session.add(new_user)
            db.session.commit()  # Commit the user first to get the auto-generated USER_CODE
            
            # Create the driver (license number will be added separately later)
            new_driver = Driver(
                DRIVER_ID=new_user.USER_CODE,
                LICENSE_NUMBER="PENDING"  # Placeholder - to be updated later
            )
            
            db.session.add(new_driver)
            db.session.commit()
            
            # Log the event
            self._log_audit_event(new_user.USER_CODE, 'driver_created_via_bulk_load', 
                                 f'Created driver: {first_name} {last_name} for organization: {org_name}')
            
            self.results['success'] += 1
            self.results['drivers_created'] += 1
            self._log_result(line_num, 'D', 'Success', f'{first_name} {last_name} ({email})', f'Username: {username}, Password: {password}')
        except Exception as e:
            db.session.rollback()
            self.results['failed'] += 1
            self._log_result(line_num, 'D', 'Failed', f'{first_name} {last_name} ({email})', f'Database error: {str(e)}')
            raise e
    
    def _create_organization(self, org_name, line_num):
        """
        Create an organization record in the database
        
        Args:
            org_name (str): Organization name
            line_num (int): Line number in the file
        """
        # Check if organization already exists
        existing_org = Organization.query.filter_by(ORG_NAME=org_name).first()
        if existing_org:
            self.results['failed'] += 1
            self._log_result(line_num, 'O', 'Failed', org_name, f'Organization already exists: {org_name}')
            return
        
        try:
            # Create new organization
            new_org = Organization(
                ORG_NAME=org_name,
                CREATED_AT=datetime.now()
            )
            
            db.session.add(new_org)
            db.session.commit()
            
            self.results['success'] += 1
            self.results['organizations_created'] += 1
            self._log_result(line_num, 'O', 'Success', org_name, f'Organization "{org_name}" created successfully (ID: {new_org.ORG_ID})')
            
            # Log the event
            self._log_audit_event(0, 'organization_created_via_bulk_load', f'Created organization: {org_name} (ID: {new_org.ORG_ID})')
            
        except Exception as e:
            db.session.rollback()
            self.results['failed'] += 1
            self._log_result(line_num, 'O', 'Failed', org_name, f'Database error creating organization: {str(e)}')
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