import os
from flask import Flask
from dotenv import load_dotenv
from extensions import db, migrate, login_manager, csrf
from config import Config
from models import User

def create_app():
    # Load environment variables from .env file
    load_dotenv()

    # Initialize Flask app
    app = Flask(__name__)
    app.config.from_object(Config)
    
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'info'
    csrf.init_app(app)
    
    from auth.routes import auth_bp
    from administrator.routes import administrator_bp
    from driver.routes import driver_bp
    from sponsor.routes import sponsor_bp
    from common.routes import common_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(administrator_bp, url_prefix='/admin')
    app.register_blueprint(driver_bp, url_prefix='/driver')
    app.register_blueprint(sponsor_bp, url_prefix='/sponsor')
    app.register_blueprint(common_bp)
    return app

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)