#!/usr/bin/env python3
"""
Fetch numeric region codes from IP2Location API for ALL countries that might use numeric codes.
"""

import requests
import json
import time
from pathlib import Path
import csv

IP2LOCATION_KEY = "2A7EF69522DEDB7664CD69A4FA11D5A0"
API_URL = "https://api.ip2location.io/"

# Countries known to use numeric codes in ISO 3166-2 (from documentation)
NUMERIC_CODE_COUNTRIES = [
    'TR', 'TH', 'TN', 'AT', 'BG', 'AL', 'EE', 'KE', 'KH', 'CY', 'JP', 
    'MM', 'ME', 'HR', 'AD', 'MA', 'IR', 'DO', 'BD', 'SL', 'CY',
    # Already converted:
    'KR', 'CZ', 'PL', 'UG', 'GT', 'ML', 'MR', 'MY', 'PA', 'VN'
]

def query_ip2location(ip):
    """Query IP2Location API for a single IP."""
    params = {'key': IP2LOCATION_KEY, 'ip': ip}
    try:
        resp = requests.get(API_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if 'region' in data and isinstance(data['region'], dict):
            data['region_code'] = data['region'].get('code', '')
            data['region_name'] = data['region'].get('name', '')
        return data
    except Exception as e:
        print(f"Error querying {ip}: {e}")
        return None

def load_sample_ips_for_country(cc):
    """Load sample IPs from ip2loc_lookup test data."""
    csv_file = Path(__file__).parent.parent / f'tests/data/ip2loc_lookup/{cc}.csv'
    if csv_file.exists():
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            return [row['ip'] for row in reader]
    return []

def main():
    all_codes = {}  # {cc: {region_name: region_code}}
    
    for cc in NUMERIC_CODE_COUNTRIES:
        print(f"\n=== Processing {cc} ===")
        ips = load_sample_ips_for_country(cc)
        
        if not ips:
            print(f"  No test IPs found for {cc}")
            continue
        
        all_codes[cc] = {}
        
        for ip in ips[:10]:  # Try up to 10 IPs
            data = query_ip2location(ip)
            if data:
                region_code = data.get('region_code', '')
                region_name = data.get('region_name', '')
                
                if region_code and region_name:
                    parts = region_code.split('-', 1)
                    if len(parts) == 2:
                        suffix = parts[1]
                        print(f"  {region_name} -> {suffix}")
                        all_codes[cc][region_name] = suffix
            
            time.sleep(0.3)  # Rate limiting
    
    # Save results
    output_file = Path(__file__).parent / 'data' / 'all_numeric_region_codes.json'
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_codes, f, indent=2, ensure_ascii=False)
    
    print(f"\n=== Summary ===")
    for cc, regions in all_codes.items():
        if regions:
            print(f"{cc}: {len(regions)} regions")
    
    print(f"\nSaved to {output_file}")

if __name__ == '__main__':
    main()
