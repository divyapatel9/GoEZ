"""Debug script to check record types in Parquet."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import duckdb
from backend.healthdata.config import PARQUET_DIR

records_path = str(PARQUET_DIR / "records" / "**" / "*.parquet").replace("\\", "/")

con = duckdb.connect()

print("Distinct record types in Parquet:")
print("-" * 60)
types = con.execute(f"""
    SELECT DISTINCT type, COUNT(*) as cnt
    FROM read_parquet('{records_path}', hive_partitioning=true)
    GROUP BY type
    ORDER BY cnt DESC
""").fetchdf()
print(types.to_string())

print("\n\nChecking for StepCount specifically:")
steps = con.execute(f"""
    SELECT COUNT(*) as cnt, MIN(value) as min_val, MAX(value) as max_val
    FROM read_parquet('{records_path}', hive_partitioning=true)
    WHERE type = 'HKQuantityTypeIdentifierStepCount'
""").fetchone()
print(f"  Count: {steps[0]}, Min: {steps[1]}, Max: {steps[2]}")

print("\n\nChecking for HeartRate specifically:")
hr = con.execute(f"""
    SELECT COUNT(*) as cnt, MIN(value) as min_val, MAX(value) as max_val
    FROM read_parquet('{records_path}', hive_partitioning=true)
    WHERE type = 'HKQuantityTypeIdentifierHeartRate'
""").fetchone()
print(f"  Count: {hr[0]}, Min: {hr[1]}, Max: {hr[2]}")

print("\n\nSample StepCount records:")
sample = con.execute(f"""
    SELECT type, value, unit, start_ts, source_name
    FROM read_parquet('{records_path}', hive_partitioning=true)
    WHERE type = 'HKQuantityTypeIdentifierStepCount'
    LIMIT 5
""").fetchdf()
print(sample.to_string())
