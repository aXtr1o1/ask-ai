import pytest
from unittest.mock import MagicMock, patch


# Fake DB cursor — used by test_assets, test_bdm, test_ppm
@pytest.fixture
def mock_cursor():
    cursor = MagicMock()
    cursor.fetchone.return_value = ['{"p_list": [], "p_count": 0}']
    return cursor


# Fake DB connection — used by test_assets, test_bdm, test_ppm
@pytest.fixture
def mock_conn(mock_cursor):
    conn = MagicMock()
    conn.cursor.return_value = mock_cursor
    return conn


