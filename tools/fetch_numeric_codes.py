#!/usr/bin/env python3
"""
Fetch numeric region codes from IP2Location API for countries that need conversion.
"""

import requests
import json
import time
from pathlib import Path

IP2LOCATION_KEY = "2A7EF69522DEDB7664CD69A4FA11D5A0"
API_URL = "https://api.ip2location.io/"

# Sample IPs from tests/data/ip2loc_lookup for countries with numeric codes
COUNTRIES_TO_QUERY = {
    'CZ': [],  # Will load from test data
    'KR': [],
    'ML': [],
    'MR': [],
    'MY': [],
    'PA': [],
    'PL': [],
    'UG': [],
    'GT': [],
}

def load_sample_ips():
    """Load sample IPs from test data files."""
    import csv
    sample_ips = {}
    
    print(f"COUNTRIES_TO_QUERY: {list(COUNTRIES_TO_QUERY.keys())}")
    
    for cc in COUNTRIES_TO_QUERY.keys():
        csv_file = Path(__file__).parent.parent / 'tests/data/ip2loc_lookup' / f'{cc}.csv'
        print(f"Checking {csv_file}...")
        if csv_file.exists():
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                ips = [row['ip'] for row in reader]
                sample_ips[cc] = ips
                print(f"Loaded {len(ips)} sample IPs for {cc}")
        else:
            print(f"File not found: {csv_file}")
    
    return sample_ips

def query_ip2location(ip):
    """Query IP2Location API for a single IP."""
    params = {'key': IP2LOCATION_KEY, 'ip': ip}
    try:
        resp = requests.get(API_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # The API returns region.code, not region_code
        if 'region' in data and isinstance(data['region'], dict):
            data['region_code'] = data['region'].get('code', '')
            data['region_name'] = data['region'].get('name', '')
        return data
    except Exception as e:
        print(f"Error querying {ip}: {e}")
        return None

def fetch_all_numeric_codes():
    """Fetch region codes for all countries with numeric codes."""
    sample_ips = load_sample_ips()
    print(f"Sample IPs loaded: {list(sample_ips.keys())}")
    
    all_codes = {}  # {cc: {region_name: region_code}}
    
    for cc, ips in sample_ips.items():
        print(f"\n=== Processing {cc} ===")
        print(f"  Sample IPs: {ips[:3]}")
        all_codes[cc] = {}
        
        for ip in ips[:5]:  # Limit to 5 IPs per country to avoid rate limiting
            data = query_ip2location(ip)
            if data:
                region_code = data.get('region_code', '')
                region_name = data.get('region_name', '')
                print(f"  IP {ip}: region_code={region_code}, region_name={region_name}")
                if region_code and region_name:
                    # Extract numeric suffix
                    parts = region_code.split('-', 1)
                    if len(parts) == 2:
                        suffix = parts[1]
                        all_codes[cc][region_name] = suffix
                        print(f"    -> {region_name} = {suffix}")
            
            time.sleep(0.5)  # Rate limiting
    
    return all_codes

if __name__ == '__main__':
    codes = fetch_all_numeric_codes()
    print("\n=== Summary ===")
    print(json.dumps(codes, indent=2, ensure_ascii=False))
    
    # Save to file
    output_file = Path('tools/data/numeric_region_codes.json')
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(codes, f, indent=2, ensure_ascii=False)
    print(f"\nSaved to {output_file}")
