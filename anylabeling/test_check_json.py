import json
import sys

if len(sys.argv) < 2:
    print("Usage: python test_check_json.py <json_file_path>")
    sys.exit(1)

json_file = sys.argv[1]

try:
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"JSON file: {json_file}")
    print(f"Has shapes: {len(data.get('shapes', []))} shapes")
    print(f"Has other_data: {'other_data' in data}")
    
    if 'other_data' in data:
        other_data = data['other_data']
        print(f"other_data keys: {list(other_data.keys())}")
        print(f"Has manually_edited: {'manually_edited' in other_data}")
        if 'manually_edited' in other_data:
            print(f"manually_edited value: {other_data['manually_edited']}")
    
    print("\nFull other_data:")
    print(json.dumps(data.get('other_data', {}), indent=2, ensure_ascii=False))
    
except Exception as e:
    print(f"Error reading JSON: {e}")
