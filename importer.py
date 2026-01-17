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

def categorize_expenses(expenses_df, categories_list, api_key):
    """
    Uses Gemini to categorize expenses based on description.
    Implements caching, batching, and retry logic.
    """
    if not api_key:
        return expenses_df
        
    client = genai.Client(api_key=api_key)
    
    # 1. Check Cache First
    expenses_df['category'] = expenses_df['description'].apply(db.get_cached_category)
    
    # Identify rows that need categorization (where category is None)
    uncached_mask = expenses_df['category'].isna()
    uncached_df = expenses_df[uncached_mask]
    
    if uncached_df.empty:
        st.info("All expenses categorized from cache!")
        return expenses_df
        
    st.info(f"Categorizing {len(uncached_df)} new expenses via AI...")
    
    # Batch processing configuration
    BATCH_SIZE = 15
    new_categories_map = {} # Map index to category
    
    progress_bar = st.progress(0)
    
    # Process only uncached expenses
    for i in range(0, len(uncached_df), BATCH_SIZE):
        batch = uncached_df.iloc[i:i+BATCH_SIZE]
        batch_expenses_text = batch[['description', 'amount']].to_json(orient='records')
        
        prompt = f"""
        You are an expense categorization assistant.
        
        Categories: {categories_list}
        
        Expenses:
        {batch_expenses_text}
        
        Task: Assign the most appropriate category from the list to each expense based on its description.
        If no category fits well, use "Uncategorized".
        
        Return ONLY a JSON array of strings, where each string is the category name corresponding to the expense at that index.
        Example: ["Food", "Transport", "Uncategorized"]
        """
        
        # Retry logic
        max_retries = 3
        retry_delay = 2
        
        batch_categories = []
        success = False
        
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=prompt
                )
                
                text = response.text.strip()
                if text.startswith('```json'):
                    text = text[7:-3]
                elif text.startswith('```'):
                    text = text[3:-3]
                    
                batch_categories = json.loads(text)
                
                if len(batch_categories) == len(batch):
                    success = True
                    break
                else:
                    print(f"Batch mismatch: Expected {len(batch)}, got {len(batch_categories)}")
                    break
                    
            except Exception as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    if attempt < max_retries - 1:
                        sleep_time = retry_delay * (2 ** attempt)
                        st.warning(f"Rate limit hit. Retrying in {sleep_time}s...")
                        time.sleep(sleep_time)
                    else:
                        st.error(f"Failed to categorize batch due to rate limits.")
                else:
                    st.error(f"Error calling LLM: {e}")
                    break
        
        if success:
            # Update map and cache
            for idx, (orig_idx, row) in enumerate(batch.iterrows()):
                category = batch_categories[idx]
                new_categories_map[orig_idx] = category
                # Cache the result
                db.cache_category(row['description'], category)
        else:
            for orig_idx in batch.index:
                new_categories_map[orig_idx] = "Uncategorized"
            
        progress_bar.progress((i + BATCH_SIZE) / len(uncached_df))
        time.sleep(1)

    progress_bar.empty()
    
    # Apply new categories to original dataframe
    for idx, category in new_categories_map.items():
        expenses_df.at[idx, 'category'] = category
        
    return expenses_df