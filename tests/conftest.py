from datetime import datetime, timezone
import shutil
import pytest
from retention.paths import ROOT
from retention.data import load_csv

@pytest.fixture
def scoring():
    return load_csv(ROOT/"data/scoring/active_customers.csv",scoring=True)[0]

@pytest.fixture
def isolated(tmp_path):
    for directory in ["config","artifacts","data/scoring","reports"]:
        shutil.copytree(ROOT/directory,tmp_path/directory)
    return tmp_path

@pytest.fixture
def now():
    return datetime(2026,9,14,10,0,tzinfo=timezone.utc)
