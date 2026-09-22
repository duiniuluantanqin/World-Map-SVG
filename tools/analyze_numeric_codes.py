#!/usr/bin/env python3
"""
Analyze IP test data to identify countries with numeric region codes.
Reads from tests/data/ip2loc_lookup/*.csv and extracts region_code patterns.
"""

import csv
import glob
import os
import re
from collections import defaultdict

def analyze_ip_data():
    """Analyze all IP test data files to find numeric region codes."""
    numeric_countries = defaultdict(set)
    alpha_countries = defaultdict(set)
    
    for csv_file in glob.glob('tests/data/ip2loc_lookup/*.csv'):
        cc = os.path.basename(csv_file).split('.')[0]
        
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                region_code = row.get('region_code', '')
                if not region_code or region_code == '-':
                    continue
                
                # Extract the suffix after CC-
                parts = region_code.split('-', 1)
                if len(parts) == 2:
                    suffix = parts[1]
                    # Check if suffix is numeric or alphanumeric
                    if suffix.isdigit():
                        numeric_countries[cc].add(int(suffix))
                    elif re.match(r'^[A-Z]+$', suffix):
                        alpha_countries[cc].add(suffix)
                    else:
                        # Mixed code (like 10A, but unlikely in ISO)
                        print(f"Mixed code: {region_code}")
    
    print("=== Countries with NUMERIC region codes ===")
    for cc in sorted(numeric_countries.keys()):
        codes = sorted(numeric_countries[cc])
        print(f"{cc}: {len(codes)} codes: {codes[:10]}{'...' if len(codes) > 10 else ''}")
    
    print("\n=== Countries with ALPHA region codes ===")
    for cc in sorted(alpha_countries.keys()):
        codes = sorted(alpha_countries[cc])
        print(f"{cc}: {len(codes)} codes: {codes[:10]}{'...' if len(codes) > 10 else ''}")
    
    print("\n=== Countries with BOTH numeric and alpha ===")
    both = set(numeric_countries.keys()) & set(alpha_countries.keys())
    for cc in sorted(both):
        num = sorted(numeric_countries[cc])
        alpha = sorted(alpha_countries[cc])
        print(f"{cc}: {len(num)} numeric + {len(alpha)} alpha")

if __name__ == '__main__':
    analyze_ip_data()
