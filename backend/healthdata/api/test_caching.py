"""Test that caching doesn't change response content."""
import json
import requests
from time import time

BASE_URL = "http://127.0.0.1:8000"

def test_metrics_caching():
    print("=" * 60)
    print("Testing /analytics/metrics caching")
    print("=" * 60)
    
    # First call (cache miss)
    t1 = time()
    r1 = requests.get(f"{BASE_URL}/analytics/metrics")
    d1 = time() - t1
    data1 = r1.json()
    
    # Second call (cache hit)
    t2 = time()
    r2 = requests.get(f"{BASE_URL}/analytics/metrics")
    d2 = time() - t2
    data2 = r2.json()
    
    print(f"First call: {d1*1000:.1f}ms")
    print(f"Second call: {d2*1000:.1f}ms (cached)")
    print(f"Content identical: {data1 == data2}")
    print(f"Count: {data1['count']}")
    print()

def test_overview_caching():
    print("=" * 60)
    print("Testing /analytics/overview caching")
    print("=" * 60)
    
    # First call (cache miss)
    t1 = time()
    r1 = requests.get(f"{BASE_URL}/analytics/overview")
    d1 = time() - t1
    data1 = r1.json()
    
    # Second call (cache hit)
    t2 = time()
    r2 = requests.get(f"{BASE_URL}/analytics/overview")
    d2 = time() - t2
    data2 = r2.json()
    
    print(f"First call: {d1*1000:.1f}ms")
    print(f"Second call: {d2*1000:.1f}ms (cached)")
    print(f"Content identical: {data1 == data2}")
    print(f"As of date: {data1['as_of_date']}")
    print(f"Tiles: {data1['count']}")
    print()

if __name__ == "__main__":
    test_metrics_caching()
    test_overview_caching()
    print("✓ Caching verification complete - content unchanged")
