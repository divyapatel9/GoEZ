"""Quick verification script for Parquet outputs."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import duckdb

from backend.healthdata.config import PARQUET_DIR

def main():
    records_path = PARQUET_DIR / "records" / "**" / "*.parquet"
    workouts_path = PARQUET_DIR / "workouts" / "**" / "*.parquet"
    
    con = duckdb.connect()
    
    print("=" * 60)
    print("Parquet Verification")
    print("=" * 60)
    
    # Count records by type
    print("\nTop 10 Record Types by Count:")
    print("-" * 40)
    query = f"""
        SELECT type, COUNT(*) as cnt 
        FROM read_parquet('{records_path}', hive_partitioning=true)
        GROUP BY type 
        ORDER BY cnt DESC 
        LIMIT 10
    """
    result = con.execute(query).fetchdf()
    for _, row in result.iterrows():
        short_type = row['type'].replace("HKQuantityTypeIdentifier", "").replace("HKCategoryTypeIdentifier", "Cat:")
        print(f"  {short_type}: {row['cnt']:,}")
    
    # Count by year
    print("\nRecords by Year:")
    print("-" * 40)
    query = f"""
        SELECT YEAR(start_ts) as year, COUNT(*) as cnt 
        FROM read_parquet('{records_path}', hive_partitioning=true)
        WHERE start_ts IS NOT NULL
        GROUP BY YEAR(start_ts)
        ORDER BY year
    """
    result = con.execute(query).fetchdf()
    for _, row in result.iterrows():
        print(f"  {int(row['year'])}: {row['cnt']:,}")
    
    # Total counts
    print("\nTotals:")
    print("-" * 40)
    total_records = con.execute(f"SELECT COUNT(*) FROM read_parquet('{records_path}', hive_partitioning=true)").fetchone()[0]
    total_workouts = con.execute(f"SELECT COUNT(*) FROM read_parquet('{workouts_path}', hive_partitioning=true)").fetchone()[0]
    print(f"  Total records: {total_records:,}")
    print(f"  Total workouts: {total_workouts:,}")
    
    # Sample record
    print("\nSample Record:")
    print("-" * 40)
    sample = con.execute(f"""
        SELECT type, value, unit, start_ts, source_name 
        FROM read_parquet('{records_path}', hive_partitioning=true)
        WHERE type LIKE '%StepCount%'
        LIMIT 1
    """).fetchdf()
    print(sample.to_string(index=False))
    
    print("\n" + "=" * 60)
    print("Verification Complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()
