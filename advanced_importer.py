import pandas as pd
import warnings
import io
from importer import FileParser, categorize_expenses
import db

class AdvancedExcelParser(FileParser):
    def parse(self, file) -> pd.DataFrame:
        """
        Parses complex Excel files with Hebrew headers and disconnected tables.
        """
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
            # Read the entire sheet without header to analyze structure
            # Handle both file path (str) and file-like object
            if isinstance(file, str):
                df_raw = pd.read_excel(file, header=None)
            else:
                df_raw = pd.read_excel(file, header=None)

        # 1. Dynamic Table Detection - Find ALL tables
        tables = []
        
        # We scan the entire file for potential header rows
        # The file structure shows multiple tables (e.g., "עסקאות שטרם נקלטו" and "עסקאות למועד חיוב")
        # Each table has its own header row.
        
        keywords = ['תאריך', 'שם בית עסק', 'סכום', 'חיוב', 'פרטים', 'תיאור', 'date', 'amount', 'description']
        
        current_header_idx = None
        
        for i in range(len(df_raw)):
            row_values = df_raw.iloc[i].astype(str).str.strip().tolist()
            match_count = sum(1 for val in row_values if any(k in val for k in keywords))
            
            if match_count >= 2:
                # Found a header row
                if current_header_idx is not None:
                    # Process the previous table
                    table_df = self._extract_table(df_raw, current_header_idx, i)
                    if not table_df.empty:
                        tables.append(table_df)
                
                current_header_idx = i
        
        # Process the last table
        if current_header_idx is not None:
            table_df = self._extract_table(df_raw, current_header_idx, len(df_raw))
            if not table_df.empty:
                tables.append(table_df)
                
        if not tables:
            raise ValueError("Could not find any valid transaction tables in the Excel file.")
            
        # Concatenate all found tables
        full_df = pd.concat(tables, ignore_index=True)
        
        return full_df[['date', 'description', 'amount']]

    def _extract_table(self, df_raw, header_idx, end_idx):
        """
        Extracts a single table given start (header) and end indices.
        """
        # Extract the slice
        df_slice = df_raw.iloc[header_idx:end_idx].copy()
        
        # Set first row as header
        df_slice.columns = df_slice.iloc[0]
        df_slice = df_slice[1:]
        
        # Map columns
        df_mapped = self._map_columns(df_slice)
        
        # Clean data
        # Filter out rows that don't look like transactions
        df_clean = df_mapped.dropna(subset=['date', 'amount'])
        
        # Ensure amount is numeric
        # Remove currency symbols and commas
        if 'amount' in df_clean.columns:
            df_clean['amount'] = df_clean['amount'].astype(str).str.replace('₪', '').str.replace(',', '').str.strip()
            df_clean['amount'] = pd.to_numeric(df_clean['amount'], errors='coerce')
            df_clean = df_clean.dropna(subset=['amount'])
        
        # Ensure date is datetime
        if 'date' in df_clean.columns:
            # Handle DD.MM.YY format seen in the file (e.g., 01.01.26)
            df_clean['date'] = pd.to_datetime(df_clean['date'], format='%d.%m.%y', errors='coerce')
            df_clean = df_clean.dropna(subset=['date'])
            
        return df_clean

    def _map_columns(self, df):
        """
        Maps Hebrew/English columns to standard internal names.
        """
        col_map = {
            'date': ['תאריך', 'date', 'taarich'],
            'description': ['שם בית עסק', 'תיאור', 'פרטים', 'description', 'details', 'business'],
            'amount': ['סכום', 'סכום חיוב', 'amount', 'price', 'debit']
        }
        
        final_cols = {}
        df.columns = df.columns.astype(str).str.strip()
        
        for target, candidates in col_map.items():
            for col in df.columns:
                if col in candidates:
                    final_cols[target] = col
                    break
            # If exact match not found, try partial match
            if target not in final_cols:
                for col in df.columns:
                    if any(c in col for c in candidates):
                        final_cols[target] = col
                        break
        
        if len(final_cols) < 3:
             # Fallback: if we have date and amount, we can maybe infer description or use a default
             pass

        # Rename columns
        df_renamed = df.rename(columns={v: k for k, v in final_cols.items()})
        
        # Return only mapped columns if they exist
        available_cols = [c for c in ['date', 'description', 'amount'] if c in df_renamed.columns]
        return df_renamed[available_cols]

def process_file(file_path, api_key=None):
    """
    Main function to process a file: parse -> categorize -> return DataFrame
    """
    parser = AdvancedExcelParser()
    df = parser.parse(file_path)
    
    # Get categories for AI
    categories_df = db.get_categories()
    categories_list = categories_df['name'].tolist()
    
    # Categorize
    if api_key:
        df = categorize_expenses(df, categories_list, api_key)
    else:
        df['category'] = 'Uncategorized'
        
    return df