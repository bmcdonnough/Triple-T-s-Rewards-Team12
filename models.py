from datetime import datetime
from extensions import db, login_manager
from flask_login import UserMixin
import bcrypt

class Role:
    DRIVER = 'driver'
    SPONSOR = 'sponsor'
    ADMINISTRATOR = 'administrator'
    
    @staticmethod
    def choices():
        return [Role.DRIVER, Role.SPONSOR, Role.ADMINISTRATOR]

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(60), nullable=False)
    role = db.Column(db.String(10), nullable=False, default=Role.DRIVER)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

    def __repr__(self):
        return f"User('{self.username}', '{self.email}', '{self.role}')"