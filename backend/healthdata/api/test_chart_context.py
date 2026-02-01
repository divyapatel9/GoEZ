"""Print chart-context example showing category and data_quality fields."""
import json
import requests

r = requests.get(
    "http://127.0.0.1:8000/analytics/chart-context",
    params={
        "metric_key": "steps",
        "start_date": "2026-01-01",
        "end_date": "2026-01-30"
    }
)
data = r.json()

print("=" * 60)
print("/analytics/chart-context example response")
print("=" * 60)
print()
print("Key fields requested in Phase 4.1:")
print("-" * 40)
print(f"metric_key: {data['metric_key']}")
print(f"category: {data['category']}")
print()
print("data_quality object:")
print(json.dumps(data['data_quality'], indent=2))
print()
print("-" * 40)
print("Full response (truncated):")
print(json.dumps({
    "metric_key": data["metric_key"],
    "display_name": data["display_name"],
    "unit": data["unit"],
    "category": data["category"],
    "start_date": data["start_date"],
    "end_date": data["end_date"],
    "time_series": {
        "last_n_days": data["time_series"]["last_n_days"],
        "min_value": data["time_series"]["min_value"],
        "max_value": data["time_series"]["max_value"],
        "mean_value": data["time_series"]["mean_value"],
    },
    "baseline": data["baseline"],
    "anomalies": {
        "total_count": data["anomalies"]["total_count"],
        "mild_count": data["anomalies"]["mild_count"],
        "strong_count": data["anomalies"]["strong_count"],
    },
    "data_quality": data["data_quality"],
}, indent=2))
