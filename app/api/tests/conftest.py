import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from workboard.database import engine
from workboard.main import app
from workboard.models import Task


@pytest.fixture
def client():
    if not os.environ["POSTGRES_DB"].endswith("_test"):
        raise RuntimeError("テストには _test で終わる専用 DB が必要です")
    with Session(engine) as session:
        session.execute(delete(Task))
        session.commit()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
