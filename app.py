import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Menu & Seasonal Engine", layout="wide")

st.title("Menu Engineering & Seasonal Analysis Engine")
st.markdown("Analyze overall menu profitability and seasonal performance shifts across uploaded POS data.")

# File Upload
uploaded_files = st.sidebar.file_uploader(
    "Upload POS CSV Files", type=["csv"], accept_multiple_files=True
)

if uploaded_files:
    df_list = []
    for file in uploaded_files:
        df_temp = pd.read_csv(file)
        df_list.append(df_temp)
    
    raw_df = pd.concat(df_list, ignore_index=True)
    raw_df.columns = raw_df.columns.str.strip().str.lower()
    
    required_cols = {'date', 'item_name', 'qty_sold', 'selling_price', 'cost_per_item'}
    if not required_cols.issubset(set(raw_df.columns)):
        st.error(f"CSV files must contain columns: {required_cols}")
        st.stop()

    # Parse Dates & Map Seasons
    raw_df['date'] = pd.to_datetime(raw_df['date'])
    raw_df['month'] = raw_df['date'].dt.month_name()
    
    def get_season(month_num):
        if month_num in [12, 1, 2]:
            return 'Winter'
        elif month_num in [3, 4, 5]:
            return 'Spring'
        elif month_num in [6, 7, 8]:
            return 'Summer'
        else:
            return 'Fall'

    raw_df['season'] = raw_df['date'].dt.month.apply(get_season)

    # Sidebar Filter Controls
    st.sidebar.header("Filter Scheme")
    selected_season = st.sidebar.multiselect(
        "Select Season(s)", 
        options=['Spring', 'Summer', 'Fall', 'Winter'],
        default=['Spring', 'Summer', 'Fall', 'Winter']
    )

    # Filtered Dataset
    filtered_df = raw_df[raw_df['season'].isin(selected_season)]

    if filtered_df.empty:
        st.warning("No data available for the selected seasonal filters.")
        st.stop()

    # Aggregate Data
    df = filtered_df.groupby('item_name').agg({
        'qty_sold': 'sum',
        'selling_price': 'mean',
        'cost_per_item': 'mean'
    }).reset_index()

    # Metrics
    df['margin_per_item'] = df['selling_price'] - df['cost_per_item']
    df['total_revenue'] = df['qty_sold'] * df['selling_price']
    df['total_profit'] = df['qty_sold'] * df['margin_per_item']

    avg_qty = df['qty_sold'].mean()
    avg_margin = df['margin_per_item'].mean()

    def categorize(row):
        if row['qty_sold'] >= avg_qty and row['margin_per_item'] >= avg_margin:
            return 'Star (Keep)'
        elif row['qty_sold'] >= avg_qty and row['margin_per_item'] < avg_margin:
            return 'Plowhorse (Raise Price)'
        elif row['qty_sold'] < avg_qty and row['margin_per_item'] >= avg_margin:
            return 'Puzzle (Promote)'
        else:
            return 'Dog (Remove)'

    df['category'] = df.apply(categorize, axis=1)

    # Tabs for Organization
    tab1, tab2 = st.tabs(["Core Menu Matrix", "Seasonal Shift Analysis"])

    with tab1:
        st.subheader("Menu Matrix")
        fig = px.scatter(
            df, x="margin_per_item", y="qty_sold", size="total_profit",
            color="category", hover_name="item_name", text="item_name",
            labels={"margin_per_item": "Profit Margin ($)", "qty_sold": "Units Sold"}
        )
        fig.add_hline(y=avg_qty, line_dash="dash", line_color="gray")
        fig.add_vline(x=avg_margin, line_dash="dash", line_color="gray")
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Actionable Menu Recommendations")
        col1, col2 = st.columns(2)
        with col1:
            st.error("🚨 **Dogs (Low Vol / Low Margin)** — Candidates for Removal")
            st.dataframe(df[df['category'] == 'Dog (Remove)'][['item_name', 'qty_sold', 'margin_per_item']])
        with col2:
            st.success("⭐ **Stars (High Vol / High Margin)** — Core Menu Staples")
            st.dataframe(df[df['category'] == 'Star (Keep)'][['item_name', 'qty_sold', 'margin_per_item']])

    with tab2:
        st.subheader("Seasonal Volume Shifts")
        st.write("Tracks unit sales fluctuations across seasons to identify limited-time menu candidates.")
        
        # Seasonal Pivot Table
        seasonal_pivot = raw_df.pivot_table(
            index='item_name', 
            columns='season', 
            values='qty_sold', 
            aggfunc='sum', 
            fill_value=0
        ).reset_index()

        st.dataframe(seasonal_pivot, use_container_width=True)

        # Seasonal Bar Chart
        fig_season = px.bar(
            raw_df.groupby(['item_name', 'season'])['qty_sold'].sum().reset_index(),
            x='item_name', y='qty_sold', color='season', barmode='group',
            title="Unit Sales per Dish by Season"
        )
        st.plotly_chart(fig_season, use_container_width=True)
