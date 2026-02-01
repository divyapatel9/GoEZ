"""
Apple Health Export Type Inventory Scanner

Streams through export.xml using iterparse to count:
- Unique Record types with sample counts
- Unique units per type
- Top sources per type

Outputs:
- data/inventory/health_type_inventory.json
- data/inventory/health_type_inventory.csv

Usage:
    python -m backend.healthdata.ingest.scan_types
"""

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree.ElementTree import iterparse

# Add parent to path for imports when running as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from backend.healthdata.config import (
    EXPORT_XML_PATH,
    INVENTORY_DIR,
    ensure_data_dirs,
    validate_export_exists,
)


def scan_health_types(export_path: Path, progress_interval: int = 100000) -> dict:
    """
    Stream parse export.xml and collect type inventory.
    
    Args:
        export_path: Path to export.xml
        progress_interval: Print progress every N records
        
    Returns:
        Dictionary with type statistics
    """
    # Accumulators
    type_counts: Counter = Counter()
    type_units: dict[str, set] = defaultdict(set)
    type_sources: dict[str, Counter] = defaultdict(Counter)
    
    # Also track workouts separately
    workout_counts: Counter = Counter()
    workout_sources: Counter = Counter()
    
    total_records = 0
    total_workouts = 0
    
    print(f"Scanning: {export_path}")
    print(f"File size: {export_path.stat().st_size / (1024*1024):.1f} MB")
    print()
    
    # Stream parse with iterparse
    context = iterparse(str(export_path), events=("end",))
    
    for event, elem in context:
        tag = elem.tag
        
        if tag == "Record":
            total_records += 1
            
            # Extract attributes
            record_type = elem.get("type", "Unknown")
            unit = elem.get("unit")
            source_name = elem.get("sourceName", "Unknown")
            
            # Accumulate
            type_counts[record_type] += 1
            if unit:
                type_units[record_type].add(unit)
            type_sources[record_type][source_name] += 1
            
            # Progress indicator
            if total_records % progress_interval == 0:
                print(f"  Processed {total_records:,} records...")
            
            # Clear element to free memory
            elem.clear()
            
        elif tag == "Workout":
            total_workouts += 1
            
            workout_type = elem.get("workoutActivityType", "Unknown")
            source_name = elem.get("sourceName", "Unknown")
            
            workout_counts[workout_type] += 1
            workout_sources[source_name] += 1
            
            elem.clear()
            
        elif tag in ("HealthData", "ExportDate", "Me"):
            # Keep these for reference but clear
            elem.clear()
        else:
            # Clear any other elements
            elem.clear()
    
    print()
    print(f"Scan complete: {total_records:,} records, {total_workouts:,} workouts")
    print(f"Unique record types: {len(type_counts)}")
    print(f"Unique workout types: {len(workout_counts)}")
    
    # Build result structure
    result = {
        "summary": {
            "total_records": total_records,
            "total_workouts": total_workouts,
            "unique_record_types": len(type_counts),
            "unique_workout_types": len(workout_counts),
        },
        "record_types": {},
        "workout_types": {},
    }
    
    # Record types with details
    for record_type, count in type_counts.most_common():
        units_list = sorted(type_units[record_type])
        top_sources = type_sources[record_type].most_common(5)
        
        result["record_types"][record_type] = {
            "sample_count": count,
            "units": units_list,
            "top_sources": [{"name": name, "count": cnt} for name, cnt in top_sources],
        }
    
    # Workout types
    for workout_type, count in workout_counts.most_common():
        result["workout_types"][workout_type] = {
            "sample_count": count,
        }
    
    # Top workout sources
    result["workout_sources"] = [
        {"name": name, "count": cnt} 
        for name, cnt in workout_sources.most_common(10)
    ]
    
    return result


def save_inventory_json(inventory: dict, output_path: Path) -> None:
    """Save inventory as JSON."""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(inventory, f, indent=2, ensure_ascii=False)
    print(f"Saved JSON: {output_path}")


def save_inventory_csv(inventory: dict, output_path: Path) -> None:
    """Save inventory as CSV (one row per record type)."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "type",
            "sample_count",
            "units",
            "top_source_1",
            "top_source_1_count",
            "top_source_2",
            "top_source_2_count",
        ])
        
        for record_type, data in inventory["record_types"].items():
            units_str = "|".join(data["units"]) if data["units"] else ""
            
            # Get top 2 sources
            sources = data["top_sources"]
            src1_name = sources[0]["name"] if len(sources) > 0 else ""
            src1_count = sources[0]["count"] if len(sources) > 0 else 0
            src2_name = sources[1]["name"] if len(sources) > 1 else ""
            src2_count = sources[1]["count"] if len(sources) > 1 else 0
            
            writer.writerow([
                record_type,
                data["sample_count"],
                units_str,
                src1_name,
                src1_count,
                src2_name,
                src2_count,
            ])
    
    print(f"Saved CSV: {output_path}")


def main():
    """Main entry point for the scanner."""
    print("=" * 60)
    print("Apple Health Export Type Inventory Scanner")
    print("=" * 60)
    print()
    
    # Ensure output directories exist
    ensure_data_dirs()
    
    # Validate export exists
    if not validate_export_exists():
        print(f"ERROR: export.xml not found at {EXPORT_XML_PATH}")
        print("Please set HEALTH_EXPORT_DIR environment variable or check path.")
        sys.exit(1)
    
    # Run scan
    inventory = scan_health_types(EXPORT_XML_PATH)
    
    # Save outputs
    json_path = INVENTORY_DIR / "health_type_inventory.json"
    csv_path = INVENTORY_DIR / "health_type_inventory.csv"
    
    save_inventory_json(inventory, json_path)
    save_inventory_csv(inventory, csv_path)
    
    # Print summary
    print()
    print("=" * 60)
    print("Top 10 Record Types by Sample Count")
    print("=" * 60)
    for i, (record_type, data) in enumerate(
        list(inventory["record_types"].items())[:10], 1
    ):
        short_type = record_type.replace("HKQuantityTypeIdentifier", "").replace(
            "HKCategoryTypeIdentifier", "Cat:"
        )
        print(f"  {i:2}. {short_type}: {data['sample_count']:,}")
    
    print()
    print("Done! Inventory files saved to:")
    print(f"  - {json_path}")
    print(f"  - {csv_path}")


if __name__ == "__main__":
    main()
