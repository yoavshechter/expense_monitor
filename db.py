import sqlite3
import pandas as pd
from datetime import datetime

DB_NAME = "expenses.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Create categories table with yearly projection
    c.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            year_projection INTEGER NOT NULL DEFAULT 0
        )
    ''')
    
    # Create expenses table
    c.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            FOREIGN KEY (category_id) REFERENCES categories (id)
        )
    ''')

    # Create income table
    c.execute('''
        CREATE TABLE IF NOT EXISTS income (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            source TEXT
        )
    ''')

    # Create cache table for expense classification
    c.execute('''
        CREATE TABLE IF NOT EXISTS expense_classification_cache (
            description TEXT PRIMARY KEY,
            category_name TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

def add_category(name, year_projection):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('INSERT INTO categories (name, year_projection) VALUES (?, ?)', (name, year_projection))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def update_category_projection(category_id, year_projection):
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE categories SET year_projection = ? WHERE id = ?', (year_projection, category_id))
    conn.commit()
    conn.close()

def delete_category(name):
    conn = get_connection()
    c = conn.cursor()
    try:
        # First get the category ID
        c.execute('SELECT id FROM categories WHERE name = ?', (name,))
        result = c.fetchone()
        if result:
            category_id = result[0]
            # Delete associated expenses first
            c.execute('DELETE FROM expenses WHERE category_id = ?', (category_id,))
            # Then delete the category
            c.execute('DELETE FROM categories WHERE id = ?', (category_id,))
            conn.commit()
            return True
        return False
    except Exception as e:
        print(f"Error deleting category: {e}")
        return False
    finally:
        conn.close()

def add_expense(category_id, amount, date, description):
    conn = get_connection()
    c = conn.cursor()
    c.execute('INSERT INTO expenses (category_id, amount, date, description) VALUES (?, ?, ?, ?)', 
              (category_id, amount, date, description))
    conn.commit()
    conn.close()

def add_income(amount, date, description, source):
    conn = get_connection()
    c = conn.cursor()
    c.execute('INSERT INTO income (amount, date, description, source) VALUES (?, ?, ?, ?)',
              (amount, date, description, source))
    conn.commit()
    conn.close()

def get_categories():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM categories", conn)
    conn.close()
    return df

def get_expenses():
    conn = get_connection()
    query = '''
        SELECT e.id, c.name as category, e.amount, e.date, e.description 
        FROM expenses e
        JOIN categories c ON e.category_id = c.id
        ORDER BY e.date DESC
    '''
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def get_monthly_expenses(year, month):
    conn = get_connection()
    # Format month as 'YYYY-MM'
    month_str = f"{year}-{month:02d}"
    query = '''
        SELECT c.name as category, SUM(e.amount) as total_spent
        FROM expenses e
        JOIN categories c ON e.category_id = c.id
        WHERE strftime('%Y-%m', e.date) = ?
        GROUP BY c.name
    '''
    df = pd.read_sql_query(query, conn, params=(month_str,))
    conn.close()
    return df

def get_yearly_expenses(year):
    conn = get_connection()
    year_str = str(year)
    query = '''
        SELECT c.name as category, SUM(e.amount) as total_spent
        FROM expenses e
        JOIN categories c ON e.category_id = c.id
        WHERE strftime('%Y', e.date) = ?
        GROUP BY c.name
    '''
    df = pd.read_sql_query(query, conn, params=(year_str,))
    conn.close()
    return df

def get_monthly_income(year, month):
    conn = get_connection()
    month_str = f"{year}-{month:02d}"
    query = '''
        SELECT SUM(amount) as total_income
        FROM income
        WHERE strftime('%Y-%m', date) = ?
    '''
    df = pd.read_sql_query(query, conn, params=(month_str,))
    conn.close()
    return df.iloc[0]['total_income'] if not df.empty and df.iloc[0]['total_income'] is not None else 0.0

def get_yearly_income(year):
    conn = get_connection()
    year_str = str(year)
    query = '''
        SELECT SUM(amount) as total_income
        FROM income
        WHERE strftime('%Y', date) = ?
    '''
    df = pd.read_sql_query(query, conn, params=(year_str,))
    conn.close()
    return df.iloc[0]['total_income'] if not df.empty and df.iloc[0]['total_income'] is not None else 0.0

def get_income_records(year, month):
    conn = get_connection()
    month_str = f"{year}-{month:02d}"
    query = '''
        SELECT * FROM income
        WHERE strftime('%Y-%m', date) = ?
        ORDER BY date DESC
    '''
    df = pd.read_sql_query(query, conn, params=(month_str,))
    conn.close()
    return df

def get_cached_category(description):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT category_name FROM expense_classification_cache WHERE description = ?', (description,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def cache_category(description, category_name):
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('INSERT OR REPLACE INTO expense_classification_cache (description, category_name) VALUES (?, ?)',
                  (description, category_name))
        conn.commit()
    except Exception as e:
        print(f"Error caching category: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()