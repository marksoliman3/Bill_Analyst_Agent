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
MAX_RETRY_ATTEMPTS = 3

# Logging settings
import logging
import os
import datetime

# Ensure log directory exists
log_dir = os.path.join("data", "output", "logs")
os.makedirs(log_dir, exist_ok=True)

# Create timestamped log filename
current_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_filename = os.path.join(log_dir, f"bill_analysis_{current_time}.log")

# Set up logging to both console and file
handlers = [
    # Console handler
    logging.StreamHandler(),
    # File handler
    logging.FileHandler(log_filename)
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=handlers
)

# Log the start of the application and log file location
logger = logging.getLogger(__name__)
logger.info(f"Starting application, logging to: {log_filename}")
