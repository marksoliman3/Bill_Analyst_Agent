import os

from pathlib import Path
from dotenv import load_dotenv

# Explicitly load .env from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# LLM API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# File paths
INPUT_CSV_PATH = "data/input/bills.csv"
OUTPUT_CSV_PATH = "data/output/analysis_results.csv"

# Retry settings
MAX_RETRY_ATTEMPTS = 2

# Logging settings
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
