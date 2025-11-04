import os

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'fdf3b077e67f77d9b75322212cd0d50f8932ed96db890458caaeab3aa27c2f44')
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI', 'mysql+pymysql://Team12:paSsword@cpsc4910-f25.cobd8enwsupz.us-east-1.rds.amazonaws.com/Team12_DB')
    MAIL_SUPPRESS_SEND = os.getenv("MAIL_SUPPRESS_SEND", "False").lower() == "true"
    SQLALCHEMY_TRACK_MODIFICATIONS = False