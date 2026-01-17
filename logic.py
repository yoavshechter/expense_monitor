import pandas as pd
from datetime import datetime
import db

def get_projection_status(year):
    """
    Calculates the status of expenses vs projection for each category.
    """
    categories_df = db.get_categories()
    yearly_expenses_df = db.get_yearly_expenses(year)
    
    # Merge categories with actual expenses
    if not yearly_expenses_df.empty:
        merged_df = pd.merge(categories_df, yearly_expenses_df, left_on='name', right_on='category', how='left')
    else:
        merged_df = categories_df.copy()
        merged_df['total_spent'] = 0.0
        
    merged_df['total_spent'] = merged_df['total_spent'].fillna(0.0)
    
    # Calculate remaining budget
    merged_df['remaining_budget'] = merged_df['year_projection'] - merged_df['total_spent']
    
    # Calculate monthly run rate needed to stay on track
    current_month = datetime.now().month
    months_remaining = 12 - current_month + 1 # Including current month
    
    if months_remaining > 0:
        merged_df['monthly_allowance'] = merged_df['remaining_budget'] / months_remaining
    else:
        merged_df['monthly_allowance'] = 0
        
    return merged_df

def get_monthly_summary(year, month):
    """
    Get summary of expenses for a specific month compared to the average monthly allowance.
    """
    monthly_expenses = db.get_monthly_expenses(year, month)
    projection_status = get_projection_status(year)
    
    # Calculate the ideal monthly spend based on yearly projection / 12
    # This is a simple average, not adjusting for seasonality or past overspending
    projection_status['avg_monthly_target'] = projection_status['year_projection'] / 12
    
    if not monthly_expenses.empty:
        summary = pd.merge(projection_status, monthly_expenses, left_on='name', right_on='category', how='left')
        # Rename total_spent from monthly_expenses to monthly_spent
        summary = summary.rename(columns={'total_spent_y': 'monthly_spent', 'total_spent_x': 'yearly_spent'})
    else:
        summary = projection_status.copy()
        summary['monthly_spent'] = 0.0
        summary = summary.rename(columns={'total_spent': 'yearly_spent'})
        
    summary['monthly_spent'] = summary['monthly_spent'].fillna(0.0)
    summary['monthly_variance'] = summary['avg_monthly_target'] - summary['monthly_spent']
    
    return summary