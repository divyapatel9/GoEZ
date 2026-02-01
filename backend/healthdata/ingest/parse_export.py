"""
Apple Health Export Parser - Records and Workouts to Parquet

Streams through export.xml using iterparse and writes normalized records
to partitioned Parquet files.

Output structure:
- data/parquet/records/type=<type>/year=YYYY/month=MM/part-0.parquet
- data/parquet/workouts/year=YYYY/month=MM/part-0.parquet

Records schema:
- user_id, type, value, unit, start_ts, end_ts, creation_ts,
  source_name, device, metadata_json

Workouts schema:
- workout_type, start_ts, end_ts, duration_sec, distance_m,
  energy_kcal, source_name, device, metadata_json

Usage:
    python -m backend.healthdata.ingest.parse_export
"""

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from xml.etree.ElementTree import iterparse

import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from backend.healthdata.config import (
    EXPORT_XML_PATH,
    PARQUET_DIR,
    ensure_data_dirs,
    validate_export_exists,
)

BATCH_SIZE = 50000

RECORD_SCHEMA = pa.schema([
    ("user_id", pa.string()),
    ("type", pa.string()),
    ("value", pa.float64()),
    ("unit", pa.string()),
    ("start_ts", pa.timestamp("us", tz="UTC")),
    ("end_ts", pa.timestamp("us", tz="UTC")),
    ("creation_ts", pa.timestamp("us", tz="UTC")),
    ("source_name", pa.string()),
    ("device", pa.string()),
    ("metadata_json", pa.string()),
])

WORKOUT_SCHEMA = pa.schema([
    ("workout_type", pa.string()),
    ("start_ts", pa.timestamp("us", tz="UTC")),
    ("end_ts", pa.timestamp("us", tz="UTC")),
    ("duration_sec", pa.float64()),
    ("distance_m", pa.float64()),
    ("energy_kcal", pa.float64()),
    ("source_name", pa.string()),
    ("device", pa.string()),
    ("metadata_json", pa.string()),
])


def parse_apple_timestamp(ts_str: str | None) -> datetime | None:
    """Parse Apple Health timestamp to datetime (UTC)."""
    if not ts_str:
        return None
    try:
        return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S %z")
    except ValueError:
        try:
            return datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None


def parse_float(val_str: str | None) -> float | None:
    """Parse string to float, return None on failure."""
    if not val_str:
        return None
    try:
        return float(val_str)
    except ValueError:
        return None


def extract_metadata(elem) -> str | None:
    """Extract metadata entries from element as JSON string."""
    metadata = {}
    for meta_entry in elem.findall("MetadataEntry"):
        key = meta_entry.get("key")
        value = meta_entry.get("value")
        if key and value:
            metadata[key] = value
    return json.dumps(metadata) if metadata else None


def get_partition_key(dt: datetime | None, record_type: str) -> tuple:
    """Get partition key (type_short, year, month) from datetime."""
    if dt is None:
        return (record_type, "unknown", "unknown")
    type_short = record_type.replace("HKQuantityTypeIdentifier", "").replace(
        "HKCategoryTypeIdentifier", "cat_"
    )
    return (type_short, str(dt.year), f"{dt.month:02d}")


def get_workout_partition_key(dt: datetime | None) -> tuple:
    """Get partition key (year, month) for workouts."""
    if dt is None:
        return ("unknown", "unknown")
    return (str(dt.year), f"{dt.month:02d}")


class PartitionedParquetWriter:
    """Manages batched writes to partitioned Parquet files."""

    def __init__(self, base_dir: Path, schema: pa.Schema, partition_type: str):
        self.base_dir = base_dir
        self.schema = schema
        self.partition_type = partition_type
        self.buffers: dict[tuple, list[dict]] = defaultdict(list)
        self.written_counts: dict[tuple, int] = defaultdict(int)
        self.part_numbers: dict[tuple, int] = defaultdict(int)

    def add_record(self, partition_key: tuple, record: dict):
        """Add a record to the buffer for a partition."""
        self.buffers[partition_key].append(record)
        if len(self.buffers[partition_key]) >= BATCH_SIZE:
            self._flush_partition(partition_key)

    def _flush_partition(self, partition_key: tuple):
        """Flush a partition buffer to Parquet."""
        records = self.buffers[partition_key]
        if not records:
            return

        if self.partition_type == "records":
            type_short, year, month = partition_key
            partition_dir = self.base_dir / f"type={type_short}" / f"year={year}" / f"month={month}"
        else:
            year, month = partition_key
            partition_dir = self.base_dir / f"year={year}" / f"month={month}"

        partition_dir.mkdir(parents=True, exist_ok=True)
        
        part_num = self.part_numbers[partition_key]
        output_path = partition_dir / f"part-{part_num}.parquet"
        self.part_numbers[partition_key] += 1

        table = pa.Table.from_pylist(records, schema=self.schema)
        pq.write_table(table, output_path, compression="snappy")

        self.written_counts[partition_key] += len(records)
        self.buffers[partition_key] = []

    def flush_all(self):
        """Flush all remaining buffers."""
        for partition_key in list(self.buffers.keys()):
            self._flush_partition(partition_key)

    def get_total_written(self) -> int:
        """Get total records written across all partitions."""
        return sum(self.written_counts.values())


def parse_export(export_path: Path, progress_interval: int = 100000):
    """
    Stream parse export.xml and write to partitioned Parquet files.
    """
    records_dir = PARQUET_DIR / "records"
    workouts_dir = PARQUET_DIR / "workouts"

    records_dir.mkdir(parents=True, exist_ok=True)
    workouts_dir.mkdir(parents=True, exist_ok=True)

    record_writer = PartitionedParquetWriter(records_dir, RECORD_SCHEMA, "records")
    workout_writer = PartitionedParquetWriter(workouts_dir, WORKOUT_SCHEMA, "workouts")

    total_records = 0
    total_workouts = 0
    parse_errors = 0

    print(f"Parsing: {export_path}")
    print(f"File size: {export_path.stat().st_size / (1024*1024):.1f} MB")
    print(f"Output: {PARQUET_DIR}")
    print()

    context = iterparse(str(export_path), events=("end",))

    for event, elem in context:
        tag = elem.tag

        if tag == "Record":
            total_records += 1

            try:
                record_type = elem.get("type", "Unknown")
                start_ts = parse_apple_timestamp(elem.get("startDate"))
                end_ts = parse_apple_timestamp(elem.get("endDate"))
                creation_ts = parse_apple_timestamp(elem.get("creationDate"))

                record = {
                    "user_id": "default",
                    "type": record_type,
                    "value": parse_float(elem.get("value")),
                    "unit": elem.get("unit"),
                    "start_ts": start_ts,
                    "end_ts": end_ts,
                    "creation_ts": creation_ts,
                    "source_name": elem.get("sourceName"),
                    "device": elem.get("device"),
                    "metadata_json": extract_metadata(elem),
                }

                partition_key = get_partition_key(start_ts, record_type)
                record_writer.add_record(partition_key, record)

            except Exception as e:
                parse_errors += 1
                if parse_errors <= 5:
                    print(f"  Warning: Parse error on record {total_records}: {e}")

            if total_records % progress_interval == 0:
                print(f"  Processed {total_records:,} records...")

            elem.clear()

        elif tag == "Workout":
            total_workouts += 1

            try:
                start_ts = parse_apple_timestamp(elem.get("startDate"))
                end_ts = parse_apple_timestamp(elem.get("endDate"))

                workout = {
                    "workout_type": elem.get("workoutActivityType", "Unknown"),
                    "start_ts": start_ts,
                    "end_ts": end_ts,
                    "duration_sec": parse_float(elem.get("duration")),
                    "distance_m": None,
                    "energy_kcal": None,
                    "source_name": elem.get("sourceName"),
                    "device": elem.get("device"),
                    "metadata_json": extract_metadata(elem),
                }

                for stat in elem.findall("WorkoutStatistics"):
                    stat_type = stat.get("type", "")
                    if "DistanceWalkingRunning" in stat_type:
                        workout["distance_m"] = parse_float(stat.get("sum"))
                    elif "ActiveEnergyBurned" in stat_type:
                        workout["energy_kcal"] = parse_float(stat.get("sum"))

                partition_key = get_workout_partition_key(start_ts)
                workout_writer.add_record(partition_key, workout)

            except Exception as e:
                parse_errors += 1
                if parse_errors <= 5:
                    print(f"  Warning: Parse error on workout {total_workouts}: {e}")

            elem.clear()

        else:
            elem.clear()

    print()
    print("Flushing remaining buffers...")
    record_writer.flush_all()
    workout_writer.flush_all()

    print()
    print("=" * 60)
    print("Parse Complete")
    print("=" * 60)
    print(f"Total records parsed: {total_records:,}")
    print(f"Total workouts parsed: {total_workouts:,}")
    print(f"Records written to Parquet: {record_writer.get_total_written():,}")
    print(f"Workouts written to Parquet: {workout_writer.get_total_written():,}")
    print(f"Parse errors: {parse_errors}")
    print(f"Record partitions: {len(record_writer.written_counts)}")
    print(f"Workout partitions: {len(workout_writer.written_counts)}")

    return {
        "total_records": total_records,
        "total_workouts": total_workouts,
        "records_written": record_writer.get_total_written(),
        "workouts_written": workout_writer.get_total_written(),
        "parse_errors": parse_errors,
    }


def main():
    """Main entry point for the parser."""
    print("=" * 60)
    print("Apple Health Export Parser - Records to Parquet")
    print("=" * 60)
    print()

    ensure_data_dirs()

    if not validate_export_exists():
        print(f"ERROR: export.xml not found at {EXPORT_XML_PATH}")
        print("Please set HEALTH_EXPORT_DIR environment variable or check path.")
        sys.exit(1)

    result = parse_export(EXPORT_XML_PATH)

    print()
    print("Done! Parquet files saved to:")
    print(f"  - {PARQUET_DIR / 'records'}")
    print(f"  - {PARQUET_DIR / 'workouts'}")


if __name__ == "__main__":
    main()
