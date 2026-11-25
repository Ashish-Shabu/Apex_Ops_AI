import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Force SQLite in-memory or temporary database for tests
os.environ["DATABASE_URL"] = "sqlite:///./test_ai_ops.db"
os.environ["DEBUG"] = "False"
os.environ["LLM_PROVIDER"] = "demo"
os.environ["GEMINI_API_KEY"] = ""

from backend.app.core.database import Base, get_db
from backend.app.main import app
from backend.app.seed_data import seed_database

test_engine = create_engine(
    "sqlite:///./test_ai_ops.db",
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    db = TestingSessionLocal()
    seed_database(db)
    db.close()
    yield
    Base.metadata.drop_all(bind=test_engine)
    if os.path.exists("./test_ai_ops.db"):
        try:
            os.remove("./test_ai_ops.db")
        except Exception:
            pass


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
