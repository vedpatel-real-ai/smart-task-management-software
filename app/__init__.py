from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_required
from flask_migrate import Migrate

db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'supersecretkey'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///taskflow.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'
    migrate = Migrate(app, db)

    # Register your existing main blueprint
    from .routes import main
    app.register_blueprint(main)

    # ✅ Register the Daily Planner API blueprint
    from app.routes import planner
    app.register_blueprint(planner)

    # ✅ Route to render the planner HTML page
    @app.route("/daily-planner")
    @login_required
    def daily_planner_page():
        return render_template("daily_planner.html")

    return app