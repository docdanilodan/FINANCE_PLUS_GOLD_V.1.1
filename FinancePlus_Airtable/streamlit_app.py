# Compatibility entry point for old FinancePlus Airtable deploys.
# All deployments now open the same unified master application.
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from master_app import *  # noqa: F401,F403,E402
