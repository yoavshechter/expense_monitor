import pandas as pd
import io
import os
from abc import ABC, abstractmethod
from google import genai
import json
import streamlit as st
import warnings
import time
import math
import db

# --- Strategy Pattern for File Parsing ---

class FileParser(ABC):
    @abstractmethod
    def parse(self, file) -> pd.DataFrame:
        """
        Parses the file and returns a standardized DataFrame with columns:
        ['date', 'description', 'amount']
        """
        pass

class GenericParser(FileParser):
    def parse(self, file) -> pd.DataFrame:
        # Determine file type and read accordingly
        if file.name.endswith('.csv'):
            df = pd.read_csv(file)
        elif file.name.endswith(('.xls', '.xlsx')):
            # Suppress openpyxl warning about default style
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
                # Read Excel file, skipping initial rows if necessary to find the header
                # We'll try to read the first few rows and see if we can find the headers
                df = pd.read_excel(file, header=None)
                
                # Find the header row
                header_row_idx = None
                for i in range(min(10, len(df))):
                    row_values = df.iloc[i].astype(str).str.lower().tolist()
                    # Check if this row contains potential headers
                    matches = 0
                    potential_headers = ['date', 'taarich', 'time', 'תאריך', 'description', 'desc', 'details', 'shem', 'name', 'תיאור', 'פרטים', 'בית עסק', 'amount', 'schum', 'price', 'cost', 'סכום', 'חיוב']
                    for val in row_values:
                        if any(h in val for h in potential_headers):
                            matches += 1
                    
                    if matches >= 2: # If at least 2 headers match, assume this is the header row
                        header_row_idx = i
                        break
                
                if header_row_idx is not None:
                    df = pd.read_excel(file, header=header_row_idx)
                else:
                    # Fallback to default read if no header found
                    df = pd.read_excel(file)

        else:
            raise ValueError("Unsupported file format. Please upload CSV or Excel file.")
        
        # Normalize column names to lower case and strip whitespace
        df.columns = df.columns.astype(str).str.lower().str.strip()
        
        # Basic mapping attempt
        col_map = {
            'date': ['date', 'taarich', 'time', 'תאריך'],
            'description': ['description', 'desc', 'details', 'shem', 'name', 'תיאור', 'פרטים', 'בית עסק'],
            'amount': ['amount', 'schum', 'price', 'cost', 'סכום', 'חיוב']
        }
        
        final_cols = {}
        for target, candidates in col_map.items():
            for candidate in candidates:
                # Exact match or partial match
                matches = [c for c in df.columns if candidate in c]
                if matches:
                    final_cols[target] = matches[0]
                    break
        
        if len(final_cols) < 3:
            # Debug info
            found = list(final_cols.keys())
            missing = [k for k in col_map.keys() if k not in found]
            raise ValueError(f"Could not automatically identify columns: {', '.join(missing)}. Found: {', '.join(found)}. Available columns: {', '.join(df.columns)}")
            
        df = df.rename(columns={v: k for k, v in final_cols.items()})
        return df[['date', 'description', 'amount']]

# --- LLM Categorization ---

def categorize_expenses(expenses_df, user_id):
    """
    Categorizes expenses based on cached descriptions for a specific user.
    """
    # Check Cache
    expenses_df['category'] = expenses_df['description'].apply(lambda x: db.get_cached_category(user_id, x))
    
    # Fill missing with "Uncategorized"
    expenses_df['category'] = expenses_df['category'].fillna("Uncategorized")
    
    return expenses_df