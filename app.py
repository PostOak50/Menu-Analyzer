import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Dish Popularity & Volume Analyzer", layout="wide")

st.title("Restaurant Dish Popularity & Ordering Frequency Engine")
st.markdown("Upload POS CSV files to identify your top-ordered items, slow movers, and seasonal volume shifts.")

# Sidebar File Upload
uploaded_files = st.sidebar.file_uploader(
    "Upload POS CSV Files", type=["csv"], accept_multiple_files=True
)

if uploaded_files:
    df_list = []
    for file in uploaded_files:
        df_temp = pd.read_csv(file)
        df_list.append(df_temp)
    
    # Combine datasets
    raw_df = pd.concat(df_list, ignore_index=True)
    raw_df.columns = raw_df.columns.str.strip().str.lower()
    
    # Check for required columns
    required_cols = {'date', 'item_name', 'qty_sold'}
    if not required_cols.issubset(set(raw_df.columns)):
        st.error(f"CSV files must contain the following columns: {required_cols}")
        st.stop()

    # Process Dates and Seasons
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

    # Sidebar Filters
    st.sidebar.header("Filter Options")
    selected_season = st.sidebar.multiselect(
        "Select Season(s)", 
        options=['Spring', 'Summer', 'Fall', 'Winter'],
        default=['Spring', 'Summer', 'Fall', 'Winter']
    )

    # Filter Data
    filtered_df = raw_df[raw_df['season'].isin(selected_season)]

    if filtered_df.empty:
        st.warning("No sales data available for the selected seasonal filters.")
        st.stop()

    # Aggregate Total Quantity Sold per Item
    df_grouped = filtered_df.groupby('item_name').agg({
        'qty_sold': 'sum'
    }).reset_index().sort_values(by='qty_sold', ascending=False)

    # Core Metrics KPI Cards
    total_items_sold = df_grouped['qty_sold'].sum()
    unique_items = len(df_grouped)
    avg_qty_per_item = df_grouped['qty_sold'].mean()

    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Total Units Sold", f"{total_items_sold:,.0f}")
    kpi2.metric("Total Unique Menu Items", f"{unique_items}")
    kpi3.metric("Avg Volume / Item", f"{avg_qty_per_item:.1f}")

    st.markdown("---")

    # Main Tabs
    tab1, tab2 = st.tabs(["Overall Popularity Rankings", "Seasonal Frequency Breakdown"])

    with tab1:
        st.subheader("Top Ordered Items Frequency Chart")
        
        # Interactive Horizontal Bar Chart
        fig_popularity = px.bar(
            df_grouped,
            x="qty_sold",
            y="item_name",
            orientation="h",
            labels={"qty_sold": "Total Units Ordered", "item_name": "Dish Name"},
            title="Most Frequently Ordered Dishes",
            color="qty_sold",
            color_continuous_scale="Viridis"
        )
        # Order highest to lowest on chart
        fig_popularity.update_layout(yaxis={'categoryorder': 'total ascending'}, height=max(400, len(df_grouped) * 25))
        st.plotly_chart(fig_popularity, use_container_width=True)

        # High/Low Breakdown
        col_top, col_bottom = st.columns(2)
        
        with col_top:
            st.success("🔥 **Top 20% Most Popular Items (Core Volume Drivers)**")
            top_threshold = df_grouped['qty_sold'].quantile(0.80)
            top_items = df_grouped[df_grouped['qty_sold'] >= top_threshold]
            st.dataframe(top_items, use_container_width=True)

        with col_bottom:
            st.error("📉 **Bottom 20% Lowest Volume Items (Low Demand / Drop Candidates)**")
            bottom_threshold = df_grouped['qty_sold'].quantile(0.20)
            bottom_items = df_grouped[df_grouped['qty_sold'] <= bottom_threshold]
            st.dataframe(bottom_items, use_container_width=True)

    with tab2:
        st.subheader("Seasonal Ordering Patterns")
        st.write("Tracks how dish order volume changes across different times of the year.")
        
        # Pivot Table by Season
        seasonal_pivot = raw_df.pivot_table(
            index='item_name', 
            columns='season', 
            values='qty_sold', 
            aggfunc='sum', 
            fill_value=0
        )
        # Sort by total volume across all seasons
        seasonal_pivot['Total'] = seasonal_pivot.sum(axis=1)
        seasonal_pivot = seasonal_pivot.sort_values(by='Total', ascending=False).drop(columns=['Total'])

        st.dataframe(seasonal_pivot, use_container_width=True)

        # Grouped Bar Chart by Season
        seasonal_grouped = raw_df.groupby(['item_name', 'season'])['qty_sold'].sum().reset_index()
        fig_season = px.bar(
            seasonal_grouped,
            x='item_name',
            y='qty_sold',
            color='season',
            barmode='group',
            title="Order Frequency Comparison by Season",
            labels={"qty_sold": "Units Sold", "item_name": "Dish Name"}
        )
        st.plotly_chart(fig_season, use_container_width=True)

else:
    st.info("Upload one or more CSV files from the sidebar to generate the popularity analysis.")