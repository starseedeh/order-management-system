import pytest

from backend.app import create_app
from backend.database import db


@pytest.fixture()
def app():
    app = create_app(testing=True)
    with app.app_context():
        yield app
        db.session.remove()


@pytest.fixture()
def client(app):
    return app.test_client()
