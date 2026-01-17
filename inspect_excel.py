import pandas as pd
import warnings

file_path = "/Users/yshechter/Downloads/1322_01_2026.xlsx"

print(f"Inspecting file: {file_path}")

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
    df = pd.read_excel(file_path, header=None)
    
    print("\n--- First 30 Rows ---")
    print(df.head(30))
    
    print("\n--- Row Values (as list) ---")
    for i in range(min(30, len(df))):
        print(f"Row {i}: {df.iloc[i].astype(str).tolist()}")