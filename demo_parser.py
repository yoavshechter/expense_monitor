import os
import pandas as pd
from advanced_importer import process_file
import db

# Initialize DB to ensure we have categories
db.init_db()

# Add some dummy categories if none exist, for the demo
if db.get_categories().empty:
    db.add_category("Food", 12000)
    db.add_category("Transport", 6000)
    db.add_category("Utilities", 5000)

file_path = "/Users/yshechter/Downloads/1322_01_2026.xlsx"

print(f"Processing file: {file_path}")

if os.path.exists(file_path):
    try:
        # Note: We are not passing an API key here, so categorization will be skipped (marked as Uncategorized)
        # In a real scenario, you would pass the API key.
        df = process_file(file_path, api_key=None)
        
        print("\n--- Extracted Data Preview ---")
        print(df.head())
        print("\n--- Data Info ---")
        print(df.info())
        
        print("\n--- Success! ---")
        print(f"Successfully extracted {len(df)} transactions.")
        
    except Exception as e:
        print(f"\nError processing file: {e}")
        import traceback
        traceback.print_exc()
else:
    print("File not found.")