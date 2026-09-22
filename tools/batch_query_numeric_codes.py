#!/usr/bin/env python3
"""
Batch query IP2Location API to get numeric region codes for all countries.
Uses sample IPs from existing test data files.
"""

import requests
import json
import time
from pathlib import Path
import csv
import re

IP2LOCATION_KEY = "2A7EF69522DEDB7664CD69A4FA11D5A0"
API_URL = "https://api.ip2location.io/"

def query_ip2location(ip):
    """Query IP2Location API for a single IP."""
    params = {'key': IP2LOCATION_KEY, 'ip': ip}
    try:
        resp = requests.get(API_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if 'region' in data and isinstance(data['region'], dict):
            return {
                'region_code': data['region'].get('code', ''),
                'region_name': data['region'].get('name', '')
            }
        return None
    except Exception as e:
        return None

def get_all_test_ips():
    """Get all test IPs from ip2loc_lookup and maxmind_samples."""
    test_ips = {}
    
    base_path = Path(__file__).parent.parent
    
    # From ip2loc_lookup
    ip2loc_dir = base_path / 'tests/data/ip2loc_lookup'
    if ip2loc_dir.exists():
        for csv_file in ip2loc_dir.glob('*.csv'):
            cc = csv_file.stem
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                ips = [row['ip'] for row in reader if row.get('ip')]
                if cc not in test_ips:
                    test_ips[cc] = []
                test_ips[cc].extend(ips)
    
    # From maxmind_samples
    maxmind_dir = base_path / 'tests/data/maxmind_samples'
    if maxmind_dir.exists():
        for csv_file in maxmind_dir.glob('*.csv'):
            cc = csv_file.stem
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                ips = [row.get('ip', row.get('network', '')) for row in reader if row.get('ip') or row.get('network')]
                if cc not in test_ips:
                    test_ips[cc] = []
                test_ips[cc].extend(ips)
    
    return test_ips

def build_kebab_to_numeric_mapping():
    """Build mapping from kebab-name to numeric code for each country."""
    
    # Load all test IPs
    test_ips = get_all_test_ips()
    print(f"Loaded test IPs for {len(test_ips)} countries")
    
    # Result: {cc: {kebab_name: numeric_code}}
    all_mappings = {}
    
    # Process each country
    for cc, ips in test_ips.items():
        print(f"\nProcessing {cc} ({len(ips)} IPs)...")
        
        # Query unique region codes
        region_map = {}  # {region_name: region_code}
        
        for ip in ips[:20]:  # Try up to 20 IPs per country
            result = query_ip2location(ip)
            if result and result['region_code'] and result['region_name']:
                region_code = result['region_code']
                region_name = result['region_name']
                
                # Extract suffix
                parts = region_code.split('-', 1)
                if len(parts) == 2:
                    suffix = parts[1]
                    # Check if it's numeric or alphanumeric
                    if suffix.isdigit() or (suffix and suffix[0].isdigit()):
                        region_map[region_name] = suffix
                        print(f"  {region_name} -> {suffix}")
            
            time.sleep(0.2)  # Rate limiting
        
        if region_map:
            # Convert region names to kebab-case
            kebab_map = {}
            for region_name, code in region_map.items():
                kebab = region_name.lower()
                kebab = re.sub(r'[^a-z0-9\s-]', '', kebab)
                kebab = re.sub(r'\s+', '-', kebab)
                kebab_map[kebab] = code
            
            all_mappings[cc] = kebab_map
    
    return all_mappings

def main():
    print("=== Building kebab-to-numeric mapping ===\n")
    mappings = build_kebab_to_numeric_mapping()
    
    print(f"\n=== Summary ===")
    for cc, regions in sorted(mappings.items()):
        print(f"{cc}: {len(regions)} regions")
    
    # Save results
    output_file = Path('tools/data/kebab_to_numeric_mapping.json')
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(mappings, f, indent=2, ensure_ascii=False)
    
    print(f"\nSaved to {output_file}")

if __name__ == '__main__':
    main()
