import streamlit as st
import pandas as pd
from datetime import datetime
import db
import logic
import matplotlib.pyplot as plt
import utils
import importer
import advanced_importer

st.set_page_config(page_title="Expense Tracker", layout="wide")

def main():
    st.title("💰 Expense Tracker & Projection")

    # Initialize DB
    db.init_db()

    # Authentication
    if 'user_id' not in st.session_state:
        st.session_state['user_id'] = None

    if st.session_state['user_id'] is None:
        show_login_page()
    else:
        show_main_app()

def show_login_page():
    st.subheader("Login / Register")
    
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
            
            if submitted:
                user_id = db.verify_user(username, password)
                if user_id:
                    st.session_state['user_id'] = user_id
                    st.success("Logged in successfully!")
                    st.rerun()
                else:
                    st.error("Invalid username or password")

    with tab2:
        with st.form("register_form"):
            new_username = st.text_input("New Username")
            new_password = st.text_input("New Password", type="password")
            submitted = st.form_submit_button("Register")
            
            if submitted:
                if new_username and new_password:
                    if db.create_user(new_username, new_password):
                        st.success("User created successfully! Please login.")
                    else:
                        st.error("Username already exists")
                else:
                    st.error("Please fill in all fields")

def show_main_app():
    user_id = st.session_state['user_id']
    
    # Sidebar for navigation
    st.sidebar.write(f"Logged in as user ID: {user_id}")
    if st.sidebar.button("Logout"):
        st.session_state['user_id'] = None
        st.rerun()
        
    page = st.sidebar.selectbox("Navigate", ["Dashboard", "Add Expense", "Add Income", "Import Expenses", "Manage Categories"])

    if page == "Dashboard":
        show_dashboard(user_id)
    elif page == "Add Expense":
        show_add_expense(user_id)
    elif page == "Add Income":
        show_add_income(user_id)
    elif page == "Import Expenses":
        show_import_expenses(user_id)
    elif page == "Manage Categories":
        show_manage_categories(user_id)

def show_dashboard(user_id):
    st.header("Dashboard")
    
    current_year = datetime.now().year
    current_month = datetime.now().month
    
    # Year Selection
    selected_year = st.sidebar.number_input("Year", min_value=2020, max_value=2030, value=current_year)
    
    # Month Selection
    month_names = ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]
    selected_month_name = st.sidebar.selectbox("Month", month_names, index=current_month-1)
    selected_month = month_names.index(selected_month_name) + 1

    # Monthly Overview
    st.subheader(f"Monthly Overview ({selected_month_name} {selected_year})")
    
    # Income Section
    monthly_income = db.get_monthly_income(user_id, selected_year, selected_month)
    monthly_summary = logic.get_monthly_summary(user_id, selected_year, selected_month)
    total_monthly_spent = monthly_summary['monthly_spent'].sum() if not monthly_summary.empty else 0.0
    
    # Calculate percentages
    savings_rate = (monthly_income - total_monthly_spent) / monthly_income * 100 if monthly_income > 0 else 0
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Monthly Income", f"₪{monthly_income:,.2f}")
    col2.metric("Monthly Spent", f"₪{total_monthly_spent:,.2f}")
    net_savings = monthly_income - total_monthly_spent
    col3.metric("Net Savings", f"₪{net_savings:,.2f}", f"{savings_rate:.1f}%", delta_color="normal" if net_savings > 0 else "inverse")

    if not monthly_summary.empty:
        # Top Spending Category
        top_category = monthly_summary.loc[monthly_summary['monthly_spent'].idxmax()]
        if top_category['monthly_spent'] > 0:
            st.info(f"🔥 Top Spending Category: **{top_category['name']}** (₪{top_category['monthly_spent']:,.2f})")

        # Charts Row
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.subheader("Target vs Spent")
            # Bar Chart
            fig, ax = plt.subplots()
            # Fix Hebrew text for matplotlib
            categories = monthly_summary['name'].apply(utils.fix_hebrew_text)
            
            x = range(len(categories))
            width = 0.35
            
            ax.bar([i - width/2 for i in x], monthly_summary['avg_monthly_target'], width, label='Target')
            ax.bar([i + width/2 for i in x], monthly_summary['monthly_spent'], width, label='Spent')
            
            ax.set_ylabel('Amount (NIS)')
            ax.set_xticks(x)
            ax.set_xticklabels(categories, rotation=45, ha='right')
            ax.legend()
            plt.tight_layout()
            st.pyplot(fig)

        with col_chart2:
            st.subheader("Expenses Distribution")
            # Pie Chart
            # Filter out zero expenses for cleaner pie chart
            spent_summary = monthly_summary[monthly_summary['monthly_spent'] > 0].copy()
            
            if not spent_summary.empty:
                # Fix Hebrew text for pie chart labels
                spent_summary['display_name'] = spent_summary['name'].apply(utils.fix_hebrew_text)
                
                fig_pie, ax_pie = plt.subplots()
                ax_pie.pie(spent_summary['monthly_spent'], labels=spent_summary['display_name'], autopct='%1.1f%%', startangle=90)
                ax_pie.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
                st.pyplot(fig_pie)
            else:
                st.info("No expenses recorded for this month yet.")

        # Detailed Table
        with st.expander("View Detailed Monthly Breakdown"):
            monthly_summary['utilization'] = (monthly_summary['monthly_spent'] / monthly_summary['avg_monthly_target'] * 100).fillna(0)
            st.dataframe(monthly_summary[['name', 'avg_monthly_target', 'monthly_spent', 'monthly_variance', 'utilization']].style.format({
                'avg_monthly_target': '₪{:,.2f}',
                'monthly_spent': '₪{:,.2f}',
                'monthly_variance': '₪{:,.2f}',
                'utilization': '{:.1f}%'
            }))

    # Yearly Overview (Collapsed)
    with st.expander(f"View Yearly Overview ({selected_year})"):
        projection_status = logic.get_projection_status(user_id, selected_year)
        
        if not projection_status.empty:
            # Display metrics
            total_projected = projection_status['year_projection'].sum()
            total_spent = projection_status['total_spent'].sum()
            remaining = total_projected - total_spent
            yearly_utilization = (total_spent / total_projected * 100) if total_projected > 0 else 0
            
            yearly_income = db.get_yearly_income(user_id, selected_year)
            net_savings = yearly_income - total_spent
            savings_rate = (net_savings / yearly_income * 100) if yearly_income > 0 else 0
            
            st.subheader("Financial Summary")
            col_fin1, col_fin2, col_fin3 = st.columns(3)
            col_fin1.metric("Yearly Income", f"₪{yearly_income:,.2f}")
            col_fin2.metric("Yearly Spent", f"₪{total_spent:,.2f}")
            col_fin3.metric("Net Savings", f"₪{net_savings:,.2f}", f"{savings_rate:.1f}%", delta_color="normal" if net_savings > 0 else "inverse")
            
            st.subheader("Budget Status")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Projected", f"₪{int(total_projected):,}")
            col2.metric("Total Spent", f"₪{total_spent:,.2f}")
            col3.metric("Remaining Budget", f"₪{remaining:,.2f}", delta_color="normal" if remaining > 0 else "inverse")
            col4.metric("Budget Utilization", f"{yearly_utilization:.1f}%")
            
            # Dataframe
            st.dataframe(projection_status[['name', 'year_projection', 'total_spent', 'remaining_budget', 'monthly_allowance']].style.format({
                'year_projection': '₪{:.0f}',
                'total_spent': '₪{:,.2f}',
                'remaining_budget': '₪{:,.2f}',
                'monthly_allowance': '₪{:,.2f}'
            }))
            
            # Chart
            # Fix Hebrew text for chart
            projection_status['display_name'] = projection_status['name'].apply(utils.fix_hebrew_text)
            st.bar_chart(projection_status.set_index('display_name')[['year_projection', 'total_spent']])
            
        else:
            st.info("No categories found. Please add categories first.")

def show_add_expense(user_id):
    st.header("Add New Expense")
    
    categories_df = db.get_categories(user_id)
    
    if categories_df.empty:
        st.warning("Please add categories first!")
        return

    with st.form("expense_form"):
        category = st.selectbox("Category", categories_df['name'])
        amount = st.number_input("Amount", min_value=0.01, step=0.01)
        
        col_date1, col_date2 = st.columns(2)
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        with col_date1:
            year = st.number_input("Year", min_value=2020, max_value=2030, value=current_year)
        with col_date2:
            month_names = ["January", "February", "March", "April", "May", "June",
                           "July", "August", "September", "October", "November", "December"]
            month_name = st.selectbox("Month", month_names, index=current_month-1)
            month = month_names.index(month_name) + 1
            
        description = st.text_input("Description")
        
        submitted = st.form_submit_button("Add Expense")
        
        if submitted:
            # Convert numpy int64 to native python int
            category_id = int(categories_df[categories_df['name'] == category]['id'].values[0])
            # Default to 1st of the month
            date_str = f"{year}-{month:02d}-01"
            db.add_expense(user_id, category_id, amount, date_str, description)
            st.success("Expense added successfully!")

    st.subheader("Recent Expenses")
    expenses = db.get_expenses(user_id)
    if not expenses.empty:
        st.dataframe(expenses)

def show_add_income(user_id):
    st.header("Add Income")
    
    with st.form("income_form"):
        amount = st.number_input("Amount", min_value=0.01, step=0.01)
        
        col_date1, col_date2 = st.columns(2)
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        with col_date1:
            year = st.number_input("Year", min_value=2020, max_value=2030, value=current_year)
        with col_date2:
            month_names = ["January", "February", "March", "April", "May", "June",
                           "July", "August", "September", "October", "November", "December"]
            month_name = st.selectbox("Month", month_names, index=current_month-1)
            month = month_names.index(month_name) + 1
            
        source = st.text_input("Source (e.g., Salary, Bonus)")
        description = st.text_input("Description")
        
        submitted = st.form_submit_button("Add Income")
        
        if submitted:
            # Default to 1st of the month
            date_str = f"{year}-{month:02d}-01"
            db.add_income(user_id, amount, date_str, description, source)
            st.success("Income added successfully!")

    st.subheader("Recent Income")
    current_year = datetime.now().year
    current_month = datetime.now().month
    income_records = db.get_income_records(user_id, current_year, current_month)
    if not income_records.empty:
        st.dataframe(income_records)

def show_import_expenses(user_id):
    st.header("Import Expenses from File")
    
    uploaded_file = st.file_uploader("Choose a CSV or Excel file", type=["csv", "xlsx", "xls"])
    
    if uploaded_file is not None:
        try:
            # Parse File
            # Try Advanced Parser first for Excel files, fallback to Generic
            if uploaded_file.name.endswith(('.xls', '.xlsx')):
                try:
                    parser = advanced_importer.AdvancedExcelParser()
                    df = parser.parse(uploaded_file)
                except Exception as e:
                    st.warning(f"Advanced parsing failed ({e}), falling back to generic parser.")
                    parser = importer.GenericParser()
                    df = parser.parse(uploaded_file)
            else:
                parser = importer.GenericParser()
                df = parser.parse(uploaded_file)
            
            st.subheader("Preview")
            st.dataframe(df.head())
            
            if st.button("Process and Categorize"):
                with st.spinner("Categorizing expenses..."):
                    # Categorize using cache
                    categorized_df = importer.categorize_expenses(df, user_id)
                    
                    # Store in session state for review
                    st.session_state['imported_expenses'] = categorized_df
                    st.success("Processing complete! Please review below.")
                    
        except Exception as e:
            st.error(f"Error parsing file: {e}")
            
    # Review and Save Section
    if 'imported_expenses' in st.session_state:
        st.subheader("Review and Save")
        
        edited_df = st.data_editor(
            st.session_state['imported_expenses'],
            column_config={
                "category": st.column_config.SelectboxColumn(
                    "Category",
                    options=db.get_categories(user_id)['name'].tolist() + ["Uncategorized"],
                    required=True
                )
            },
            num_rows="dynamic"
        )
        
        if st.button("Save to Database"):
            count = 0
            categories_df = db.get_categories(user_id)
            
            for index, row in edited_df.iterrows():
                # Skip uncategorized or invalid categories
                if row['category'] == "Uncategorized" or row['category'] not in categories_df['name'].values:
                    continue
                    
                category_id = int(categories_df[categories_df['name'] == row['category']]['id'].values[0])
                
                # Parse date (assuming generic parser returns standard format or trying best effort)
                # For now, we'll try to parse common formats
                try:
                    date_obj = pd.to_datetime(row['date'])
                    date_str = date_obj.strftime('%Y-%m-%d')
                except:
                    date_str = datetime.now().strftime('%Y-%m-%d') # Fallback
                
                db.add_expense(user_id, category_id, float(row['amount']), date_str, row['description'])
                
                # Update cache with manual selection
                db.cache_category(user_id, row['description'], row['category'])
                
                count += 1
                
            st.success(f"Successfully saved {count} expenses and updated cache!")
            del st.session_state['imported_expenses']

def show_manage_categories(user_id):
    st.header("Manage Categories")
    
    with st.form("category_form"):
        name = st.text_input("Category Name")
        
        col1, col2 = st.columns(2)
        with col1:
            projection_type = st.radio("Projection Type", ["Yearly", "Monthly"])
        with col2:
            amount = st.number_input("Amount", min_value=0, step=1)
            
        submitted = st.form_submit_button("Add/Update Category")
        
        if submitted:
            if name:
                # Convert monthly to yearly if needed
                yearly_projection = int(amount * 12) if projection_type == "Monthly" else int(amount)
                
                if db.add_category(user_id, name, yearly_projection):
                    st.success(f"Category '{name}' added with yearly projection of ₪{yearly_projection:,}!")
                else:
                    # If add fails, try to update
                    cats = db.get_categories(user_id)
                    if name in cats['name'].values:
                        cat_id = cats[cats['name'] == name]['id'].values[0]
                        db.update_category_projection(user_id, cat_id, yearly_projection)
                        st.success(f"Category '{name}' updated with yearly projection of ₪{yearly_projection:,}!")
                    else:
                        st.error("Error adding category.")
            else:
                st.error("Please enter a name.")

    st.subheader("Existing Categories")
    categories = db.get_categories(user_id)
    if not categories.empty:
        st.dataframe(categories)
        
        st.markdown("---")
        st.subheader("Delete Category")
        with st.form("delete_category_form"):
            category_to_delete = st.selectbox("Select Category to Delete", categories['name'])
            delete_submitted = st.form_submit_button("Delete Category")
            
            if delete_submitted:
                if db.delete_category(user_id, category_to_delete):
                    st.success(f"Category '{category_to_delete}' and its expenses deleted successfully!")
                    st.rerun()
                else:
                    st.error("Error deleting category.")

if __name__ == "__main__":
    main()