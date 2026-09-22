#!/usr/bin/env python3
"""
Convert English-name region IDs to numeric codes for countries where IP2Location returns numeric codes.
This is a change in naming convention: numeric codes directly used instead of English names.
"""

import json
import re
from pathlib import Path
from collections import defaultdict

# Load the numeric region codes mapping
MAPPING_FILE = Path(__file__).parent / 'data' / 'numeric_region_codes.json'

def load_mapping():
    """Load the region name to numeric code mapping."""
    with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def build_conversion_map():
    """Load the direct ID-to-ID mapping."""
    return load_mapping()

def analyze_svg(svg_file, conversion):
    """Analyze which IDs in the SVG need to be converted."""
    with open(svg_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    stats = defaultdict(lambda: {'total': 0, 'to_convert': 0, 'examples': []})
    
    for cc, id_map in conversion.items():
        # Find all IDs for this country
        pattern = rf'id="{cc}-([a-z-]+)"'
        matches = re.findall(pattern, content)
        
        stats[cc]['total'] = len(matches)
        
        # Check which ones need conversion
        for match in matches:
            old_id = f"{cc}-{match}"
            if old_id in id_map:
                stats[cc]['to_convert'] += 1
                if len(stats[cc]['examples']) < 5:
                    new_id = id_map[old_id]
                    stats[cc]['examples'].append(f"{old_id} → {new_id}")
    
    return stats

def convert_svg(svg_file, conversion, output_file=None):
    """Convert English-name IDs to numeric codes in the SVG file."""
    with open(svg_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    total_converted = 0
    conversions = []
    
    for cc, id_map in conversion.items():
        for old_id, new_id in id_map.items():
            # Check if old_id exists in the file
            if f'id="{old_id}"' in content:
                content = content.replace(f'id="{old_id}"', f'id="{new_id}"')
                total_converted += 1
                conversions.append(f"{old_id} → {new_id}")
                print(f"  {old_id} → {new_id}")
    
    # Write output
    if output_file is None:
        output_file = svg_file
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return total_converted, conversions

def main():
    print("=== Building conversion map ===")
    conversion = build_conversion_map()
    
    for cc in sorted(conversion.keys()):
        print(f"{cc}: {len(conversion[cc])} regions to convert")
    
    print("\n=== Analyzing world-states-provinces.svg ===")
    svg_path = Path(__file__).parent.parent / 'src/world-states-provinces.svg'
    stats = analyze_svg(svg_path, conversion)
    
    for cc in sorted(stats.keys()):
        s = stats[cc]
        print(f"{cc}: {s['to_convert']}/{s['total']} IDs to convert")
        for ex in s['examples']:
            print(f"  {ex}")
    
    print("\n=== Converting IDs ===")
    total, conversions = convert_svg(
        svg_path,
        conversion
    )
    
    print(f"\n=== Summary ===")
    print(f"Total IDs converted: {total}")
    
    # Save conversion log
    log_file = Path('tools/data/conversion_log.txt')
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(f"Total conversions: {total}\n\n")
        for conv in conversions:
            f.write(f"{conv}\n")
    print(f"Conversion log saved to {log_file}")

if __name__ == '__main__':
    main()
