"""
conftest.py — Global test configuration.
Mocks ALL external dependencies so tests run anywhere without real services.
"""
import pytest
import os
import sys
from unittest.mock import MagicMock, patch
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# ✅ Set environment variables BEFORE any imports
os.environ.setdefault('GEMINI_API_KEY', 'fake-test-key')
os.environ.setdefault('GOOGLE_API_KEY', 'fake-test-key')
os.environ.setdefault('DATABASE_URL', 'postgresql://fake:fake@localhost/fake')
os.environ.setdefault('PG_HOST', 'localhost')
os.environ.setdefault('PG_DATABASE', 'testdb')
os.environ.setdefault('PG_NAME', 'testdb')
os.environ.setdefault('PG_USER', 'testuser')
os.environ.setdefault('PG_PASSWORD', 'testpass')
os.environ.setdefault('PG_PORT', '5432')
os.environ.setdefault('GOOGLE_AI_MODEL', 'gemini-1.5-flash')
os.environ.setdefault('MAX_HISTORY', '5')
os.environ.setdefault('DATABASE_API_URL', 'http://localhost:8000')
os.environ.setdefault('L1_TTL_SECONDS', '120')
os.environ.setdefault('L2_TTL_SECONDS', '120')
os.environ.setdefault('L1_SIZE_THRESHOLD', '5')
os.environ.setdefault('WS_SESSION_TIMEOUT', '120')
os.environ.setdefault('WS_PING_INTERVAL', '30')
os.environ.setdefault('SYNC_INTERVAL_MINUTES', '20')
os.environ.setdefault('SYNC_PAGE_SIZE', '1000')


@pytest.fixture(scope="session", autouse=True)
def mock_environment_variables():
    """Mock all environment variables before any imports"""
    fake_env = {
        'GEMINI_API_KEY': 'fake-test-key',
        'GOOGLE_API_KEY': 'fake-test-key',
        'DATABASE_URL': 'postgresql://fake:fake@localhost/fake',
        'PG_HOST': 'localhost',
        'PG_DATABASE': 'testdb',
        'PG_NAME': 'testdb',
        'PG_USER': 'testuser',
        'PG_PASSWORD': 'testpass',
        'PG_PORT': '5432',
        'GOOGLE_AI_MODEL': 'gemini-1.5-flash',
    }
    
    with patch.dict(os.environ, fake_env, clear=False):
        yield


@pytest.fixture(scope="function", autouse=True)
def mock_database():
    """Mock database connections globally"""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = ['{"p_list": [], "p_count": 0}']
    mock_cursor.fetchall.return_value = []
    mock_cursor.description = []
    
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_conn.cursor.return_value = mock_cursor
    
    # ✅ Patch all places where get_pool is imported
    patches = [
        patch("app.api.database.postgres_client.get_pool", return_value=mock_conn),
        patch("app.services.postgres_service.get_pool", return_value=mock_conn),
        patch("app.services.session_service.get_pool", return_value=mock_conn),
        patch("app.api.routes.assets.get_pool", return_value=mock_conn),
        patch("app.api.routes.ppm.get_pool", return_value=mock_conn),
        patch("app.api.routes.bdm.get_pool", return_value=mock_conn),
        patch("app.api.routes.app_endpoints.get_pool", return_value=mock_conn),
    ]
    
    for p in patches:
        p.start()
    
    yield mock_conn
    
    for p in patches:
        p.stop()


@pytest.fixture(scope="function", autouse=True)
def mock_langchain():
    """Mock LangChain/Gemini AI globally"""
    with patch("app.services.langchain_service.ChatGoogleGenerativeAI") as mock_llm:
        mock_instance = MagicMock()
        mock_instance.bind_tools.return_value = mock_instance
        mock_llm.return_value = mock_instance
        yield mock_llm