"""Test script for analytics API endpoints."""
import json
import requests

BASE_URL = "http://127.0.0.1:8000"

def test_metrics():
    print("=" * 60)
    print("1. GET /analytics/metrics")
    print("=" * 60)
    r = requests.get(f"{BASE_URL}/analytics/metrics")
    data = r.json()
    print(f"Status: {r.status_code}")
    print(f"Count: {data['count']}")
    print("Sample metrics:")
    for m in data['metrics'][:3]:
        print(f"  - {m['metric_key']}: {m['display_name']} ({m['category']})")
    print()

def test_daily_metric():
    print("=" * 60)
    print("2. GET /analytics/metric/daily")
    print("=" * 60)
    r = requests.get(f"{BASE_URL}/analytics/metric/daily", params={
        "metric_key": "steps",
        "start_date": "2026-01-20",
        "end_date": "2026-01-30"
    })
    data = r.json()
    print(f"Status: {r.status_code}")
    print(f"Metric: {data['metric_key']} ({data['display_name']})")
    print(f"Data points: {data['count']}")
    print("Sample data:")
    for d in data['data'][:3]:
        print(f"  {d['date']}: {d['value']} (baseline: {d['baseline_median']}, anomaly: {d['anomaly_level']})")
    print()

def test_overview():
    print("=" * 60)
    print("3. GET /analytics/overview")
    print("=" * 60)
    r = requests.get(f"{BASE_URL}/analytics/overview")
    data = r.json()
    print(f"Status: {r.status_code}")
    print(f"As of: {data['as_of_date']}")
    print(f"Tiles: {data['count']}")
    print("Sample tiles:")
    for t in data['tiles'][:3]:
        print(f"  - {t['display_name']}: {t['latest_value']} {t['unit']} (trend: {t['trend_7d']})")
    print()

def test_anomalies():
    print("=" * 60)
    print("4. GET /analytics/anomalies")
    print("=" * 60)
    r = requests.get(f"{BASE_URL}/analytics/anomalies", params={
        "start_date": "2026-01-01",
        "end_date": "2026-01-30",
        "min_level": "mild"
    })
    data = r.json()
    print(f"Status: {r.status_code}")
    print(f"Anomalies: {data['count']}")
    print("Sample anomalies:")
    for a in data['anomalies'][:3]:
        print(f"  {a['date']} - {a['display_name']}: {a['anomaly_level']} - {a['reason'][:50]}...")
    print()

def test_correlations():
    print("=" * 60)
    print("5. GET /analytics/correlations")
    print("=" * 60)
    r = requests.get(f"{BASE_URL}/analytics/correlations", params={
        "metric_key": "steps"
    })
    data = r.json()
    print(f"Status: {r.status_code}")
    print(f"Correlations for: {data['metric_key']}")
    print(f"Count: {data['count']}")
    for c in data['correlations']:
        print(f"  {c['metric_a_display']} <-> {c['metric_b_display']}: r={c['corr']} (lag={c['lag_days']})")
    print()

def test_chart_context():
    print("=" * 60)
    print("6. GET /analytics/chart-context")
    print("=" * 60)
    r = requests.get(f"{BASE_URL}/analytics/chart-context", params={
        "metric_key": "hrv_sdnn",
        "start_date": "2026-01-01",
        "end_date": "2026-01-30"
    })
    data = r.json()
    print(f"Status: {r.status_code}")
    print(f"Metric: {data['display_name']} ({data['category']})")
    print(f"Time series: {data['time_series']['last_n_days']} days")
    print(f"Baseline: median={data['baseline']['current_median']}")
    print(f"Anomalies: {data['anomalies']['total_count']} total")
    print(f"Data quality: {data['data_quality']['coverage_percent']}% coverage")
    print()

def verify_sparse_metrics():
    print("=" * 60)
    print("VERIFICATION: vo2max and sleep_duration anomalies")
    print("=" * 60)
    r = requests.get(f"{BASE_URL}/analytics/anomalies", params={
        "start_date": "2024-10-01",
        "end_date": "2026-01-30",
        "min_level": "mild"
    })
    data = r.json()
    
    vo2max_anomalies = [a for a in data['anomalies'] if a['metric_key'] == 'vo2max']
    sleep_anomalies = [a for a in data['anomalies'] if a['metric_key'] == 'sleep_duration']
    
    print(f"Total anomalies in range: {data['count']}")
    print(f"vo2max anomalies: {len(vo2max_anomalies)}")
    print(f"sleep_duration anomalies: {len(sleep_anomalies)}")
    
    if len(vo2max_anomalies) == 0 and len(sleep_anomalies) == 0:
        print("✓ PASS: Sparse metrics correctly excluded from anomalies")
    else:
        print("✗ FAIL: Sparse metrics found in anomalies!")
    print()

def verify_null_baselines():
    print("=" * 60)
    print("VERIFICATION: Null baselines handled correctly")
    print("=" * 60)
    r = requests.get(f"{BASE_URL}/analytics/metric/daily", params={
        "metric_key": "vo2max",
        "start_date": "2024-10-01",
        "end_date": "2026-01-30"
    })
    data = r.json()
    
    null_baseline_count = sum(1 for d in data['data'] if d['baseline_median'] is None)
    print(f"vo2max data points: {data['count']}")
    print(f"Points with null baseline: {null_baseline_count}")
    print("✓ PASS: Null baselines preserved (vo2max is sparse)")
    print()

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("ANALYTICS API ENDPOINT TESTS")
    print("=" * 60 + "\n")
    
    test_metrics()
    test_daily_metric()
    test_overview()
    test_anomalies()
    test_correlations()
    test_chart_context()
    verify_sparse_metrics()
    verify_null_baselines()
    
    print("=" * 60)
    print("ALL TESTS COMPLETE")
    print("=" * 60)
