"""
Configuration for Health Data module.
Uses environment variables with sensible defaults.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Path to Apple Health export folder (contains export.xml)
# This should point to the user's exported Apple Health data
HEALTH_EXPORT_DIR = Path(os.getenv(
    "HEALTH_EXPORT_DIR",
    BASE_DIR / "ShreyiPhoneHealth data" / "apple_health_export"
))

# Path where processed data (parquet, duckdb) will be stored
HEALTH_DATA_DIR = Path(os.getenv(
    "HEALTH_DATA_DIR",
    BASE_DIR / "data"
))

# Derived paths
PARQUET_DIR = HEALTH_DATA_DIR / "parquet"
DUCKDB_PATH = HEALTH_DATA_DIR / "health.duckdb"
INVENTORY_DIR = HEALTH_DATA_DIR / "inventory"

# Export file paths (read-only, never stored in data folder)
EXPORT_XML_PATH = HEALTH_EXPORT_DIR / "export.xml"
EXPORT_CDA_XML_PATH = HEALTH_EXPORT_DIR / "export_cda.xml"


def ensure_data_dirs():
    """Create data directories if they don't exist."""
    HEALTH_DATA_DIR.mkdir(parents=True, exist_ok=True)
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)
    INVENTORY_DIR.mkdir(parents=True, exist_ok=True)


def validate_export_exists() -> bool:
    """Check if the export.xml file exists."""
    return EXPORT_XML_PATH.exists()


def get_config_summary() -> dict:
    """Return a summary of current configuration."""
    return {
        "HEALTH_EXPORT_DIR": str(HEALTH_EXPORT_DIR),
        "HEALTH_DATA_DIR": str(HEALTH_DATA_DIR),
        "PARQUET_DIR": str(PARQUET_DIR),
        "DUCKDB_PATH": str(DUCKDB_PATH),
        "export_xml_exists": EXPORT_XML_PATH.exists(),
        "export_cda_xml_exists": EXPORT_CDA_XML_PATH.exists(),
    }
