import sqlite3
import pandas as pd
from datetime import datetime
import bcrypt

DB_NAME = "expenses.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Create users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')

    # Create categories table with yearly projection and user_id
    c.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            year_projection INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(user_id, name)
        )
    ''')
    
    # Create expenses table with user_id
    c.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (category_id) REFERENCES categories (id)
        )
    ''')

    # Create income table with user_id
    c.execute('''
        CREATE TABLE IF NOT EXISTS income (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            source TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create cache table for expense classification with user_id
    c.execute('''
        CREATE TABLE IF NOT EXISTS expense_classification_cache (
            user_id INTEGER NOT NULL,
            description TEXT NOT NULL,
            category_name TEXT NOT NULL,
            PRIMARY KEY (user_id, description),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

# --- Authentication ---

def create_user(username, password):
    conn = get_connection()
    c = conn.cursor()
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    try:
        c.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, password_hash))
        conn.commit()
        return c.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def verify_user(username, password):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT id, password_hash FROM users WHERE username = ?', (username,))
    result = c.fetchone()
    conn.close()
    
    if result:
        user_id, stored_hash = result
        if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
            return user_id
    return None

# --- Data Operations ---

def add_category(user_id, name, year_projection):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('INSERT INTO categories (user_id, name, year_projection) VALUES (?, ?, ?)', (user_id, name, year_projection))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def update_category_projection(user_id, category_id, year_projection):
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE categories SET year_projection = ? WHERE id = ? AND user_id = ?', (year_projection, category_id, user_id))
    conn.commit()
    conn.close()

def delete_category(user_id, name):
    conn = get_connection()
    c = conn.cursor()
    try:
        # First get the category ID
        c.execute('SELECT id FROM categories WHERE name = ? AND user_id = ?', (name, user_id))
        result = c.fetchone()
        if result:
            category_id = result[0]
            # Delete associated expenses first
            c.execute('DELETE FROM expenses WHERE category_id = ? AND user_id = ?', (category_id, user_id))
            # Then delete the category
            c.execute('DELETE FROM categories WHERE id = ? AND user_id = ?', (category_id, user_id))
            conn.commit()
            return True
        return False
    except Exception as e:
        print(f"Error deleting category: {e}")
        return False
    finally:
        conn.close()

def add_expense(user_id, category_id, amount, date, description):
    conn = get_connection()
    c = conn.cursor()
    c.execute('INSERT INTO expenses (user_id, category_id, amount, date, description) VALUES (?, ?, ?, ?, ?)', 
              (user_id, category_id, amount, date, description))
    conn.commit()
    conn.close()

def add_income(user_id, amount, date, description, source):
    conn = get_connection()
    c = conn.cursor()
    c.execute('INSERT INTO income (user_id, amount, date, description, source) VALUES (?, ?, ?, ?, ?)',
              (user_id, amount, date, description, source))
    conn.commit()
    conn.close()

def delete_income(user_id, income_id):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('DELETE FROM income WHERE id = ? AND user_id = ?', (income_id, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting income: {e}")
        return False
    finally:
        conn.close()

def get_categories(user_id):
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM categories WHERE user_id = ?", conn, params=(user_id,))
    conn.close()
    return df

def get_expenses(user_id):
    conn = get_connection()
    query = '''
        SELECT e.id, c.name as category, e.amount, e.date, e.description 
        FROM expenses e
        JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = ?
        ORDER BY e.date DESC
    '''
    df = pd.read_sql_query(query, conn, params=(user_id,))
    conn.close()
    return df

def get_monthly_expenses(user_id, year, month):
    conn = get_connection()
    # Format month as 'YYYY-MM'
    month_str = f"{year}-{month:02d}"
    query = '''
        SELECT c.name as category, SUM(e.amount) as total_spent
        FROM expenses e
        JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = ? AND strftime('%Y-%m', e.date) = ?
        GROUP BY c.name
    '''
    df = pd.read_sql_query(query, conn, params=(user_id, month_str))
    conn.close()
    return df

def get_yearly_expenses(user_id, year):
    conn = get_connection()
    year_str = str(year)
    query = '''
        SELECT c.name as category, SUM(e.amount) as total_spent
        FROM expenses e
        JOIN categories c ON e.category_id = c.id
        WHERE e.user_id = ? AND strftime('%Y', e.date) = ?
        GROUP BY c.name
    '''
    df = pd.read_sql_query(query, conn, params=(user_id, year_str))
    conn.close()
    return df

def get_monthly_income(user_id, year, month):
    conn = get_connection()
    month_str = f"{year}-{month:02d}"
    query = '''
        SELECT SUM(amount) as total_income
        FROM income
        WHERE user_id = ? AND strftime('%Y-%m', date) = ?
    '''
    df = pd.read_sql_query(query, conn, params=(user_id, month_str))
    conn.close()
    return df.iloc[0]['total_income'] if not df.empty and df.iloc[0]['total_income'] is not None else 0.0

def get_yearly_income(user_id, year):
    conn = get_connection()
    year_str = str(year)
    query = '''
        SELECT SUM(amount) as total_income
        FROM income
        WHERE user_id = ? AND strftime('%Y', date) = ?
    '''
    df = pd.read_sql_query(query, conn, params=(user_id, year_str))
    conn.close()
    return df.iloc[0]['total_income'] if not df.empty and df.iloc[0]['total_income'] is not None else 0.0

def get_income_records(user_id, year, month):
    conn = get_connection()
    month_str = f"{year}-{month:02d}"
    query = '''
        SELECT * FROM income
        WHERE user_id = ? AND strftime('%Y-%m', date) = ?
        ORDER BY date DESC
    '''
    df = pd.read_sql_query(query, conn, params=(user_id, month_str))
    conn.close()
    return df

def get_yearly_income_records(user_id, year):
    conn = get_connection()
    year_str = str(year)
    query = '''
        SELECT * FROM income
        WHERE user_id = ? AND strftime('%Y', date) = ?
        ORDER BY date DESC
    '''
    df = pd.read_sql_query(query, conn, params=(user_id, year_str))
    conn.close()
    return df

def get_cached_category(user_id, description):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT category_name FROM expense_classification_cache WHERE user_id = ? AND description = ?', (user_id, description))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def cache_category(user_id, description, category_name):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('INSERT OR REPLACE INTO expense_classification_cache (user_id, description, category_name) VALUES (?, ?, ?)', 
                  (user_id, description, category_name))
        conn.commit()
    except Exception as e:
        print(f"Error caching category: {e}")
    finally:
        conn.close()

def export_user_data(user_id):
    """Exports all user data to a dictionary of DataFrames."""
    conn = get_connection()
    
    categories = pd.read_sql_query("SELECT * FROM categories WHERE user_id = ?", conn, params=(user_id,))
    expenses = pd.read_sql_query("SELECT * FROM expenses WHERE user_id = ?", conn, params=(user_id,))
    income = pd.read_sql_query("SELECT * FROM income WHERE user_id = ?", conn, params=(user_id,))
    
    conn.close()
    
    return {
        "categories": categories,
        "expenses": expenses,
        "income": income
    }

def import_user_data(user_id, data):
    """Imports user data from a dictionary of DataFrames."""
    conn = get_connection()
    c = conn.cursor()
    
    try:
        # 1. Import Categories
        if 'categories' in data and not data['categories'].empty:
            for _, row in data['categories'].iterrows():
                try:
                    c.execute('INSERT INTO categories (user_id, name, year_projection) VALUES (?, ?, ?)',
                              (user_id, row['name'], row['year_projection']))
                except sqlite3.IntegrityError:
                    # Category might already exist, update projection
                    c.execute('UPDATE categories SET year_projection = ? WHERE user_id = ? AND name = ?',
                              (row['year_projection'], user_id, row['name']))
        
        # Get updated category map (name -> id)
        c.execute('SELECT name, id FROM categories WHERE user_id = ?', (user_id,))
        cat_map = dict(c.fetchall())
        
        # 2. Import Expenses
        if 'expenses' in data and not data['expenses'].empty:
            for _, row in data['expenses'].iterrows():
                # We need to map the category name to the new category ID
                # The export might contain category_id which is invalid in the new context
                # So we need to join with categories on export or rely on name if available.
                # Since our export is raw table dump, expenses has category_id.
                # We need to look up the category name from the exported categories df first.
                
                # Find category name from exported data
                cat_name = None
                if 'categories' in data:
                    cat_row = data['categories'][data['categories']['id'] == row['category_id']]
                    if not cat_row.empty:
                        cat_name = cat_row.iloc[0]['name']
                
                if cat_name and cat_name in cat_map:
                    new_cat_id = cat_map[cat_name]
                    c.execute('INSERT INTO expenses (user_id, category_id, amount, date, description) VALUES (?, ?, ?, ?, ?)',
                              (user_id, new_cat_id, row['amount'], row['date'], row['description']))
        
        # 3. Import Income
        if 'income' in data and not data['income'].empty:
            for _, row in data['income'].iterrows():
                c.execute('INSERT INTO income (user_id, amount, date, description, source) VALUES (?, ?, ?, ?, ?)',
                          (user_id, row['amount'], row['date'], row['description'], row['source']))
                          
        conn.commit()
        return True, "Data imported successfully!"
    except Exception as e:
        return False, f"Error importing data: {e}"
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()