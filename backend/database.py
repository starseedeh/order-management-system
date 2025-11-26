from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


def init_db(app, database_url=None):
    app.config.setdefault("SQLALCHEMY_DATABASE_URI", database_url or "sqlite:///orders.db")
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)
    db.init_app(app)
    with app.app_context():
        db.create_all()
