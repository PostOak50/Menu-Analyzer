import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Menu Popularity & Revenue Share Engine", layout="wide")

st.title("Restaurant Menu Volume & Revenue Share Engine")
st.markdown("Analyze dish popularity by **Monthly** and **Quarterly** breakdown, highlighting Top 25% and Bottom 25% performers by sales count and revenue contribution.")

# Sidebar File Upload
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
    
    # Required columns for frequency + revenue calculations
    required_cols = {'date', 'item_name', 'qty_sold', 'selling_price'}
    if not required_cols.issubset(set(raw_df.columns)):
        st.error(f"CSV files must contain the following columns: {required_cols}")
        st.stop()

    # Process Dates, Months, Quarters
    raw_df['date'] = pd.to_datetime(raw_df['date'])
    raw_df['year'] = raw_df['date'].dt.year
    raw_df['month'] = raw_df['date'].dt.strftime('%Y-%m (%B)')
    raw_df['quarter'] = raw_df['date'].dt.to_period('Q').astype(str)
    raw_df['total_revenue'] = raw_df['qty_sold'] * raw_df['selling_price']

    # Sidebar Time Filters
    st.sidebar.header("Time Filter Options")
    time_view = st.sidebar.radio("View Breakdown By:", ["All Time", "By Quarter", "By Month"])

    filtered_df = raw_df.copy()

    if time_view == "By Quarter":
        selected_quarters = st.sidebar.multiselect(
            "Select Quarter(s)", 
            options=sorted(raw_df['quarter'].unique()),
            default=sorted(raw_df['quarter'].unique())
        )
        filtered_df = filtered_df[filtered_df['quarter'].isin(selected_quarters)]

    elif time_view == "By Month":
        selected_months = st.sidebar.multiselect(
            "Select Month(s)", 
            options=sorted(raw_df['month'].unique()),
            default=sorted(raw_df['month'].unique())
        )
        filtered_df = filtered_df[filtered_df['month'].isin(selected_months)]

    if filtered_df.empty:
        st.warning("No sales data available for the selected time filter.")
        st.stop()

    # Aggregations
    df_grouped = filtered_df.groupby('item_name').agg({
        'qty_sold': 'sum',
        'total_revenue': 'sum'
    }).reset_index()

    total_units_overall = df_grouped['qty_sold'].sum()
    total_rev_overall = df_grouped['total_revenue'].sum()

    # Percentage Share Calculations
    df_grouped['pct_frequency'] = (df_grouped['qty_sold'] / total_units_overall) * 100
    df_grouped['pct_revenue'] = (df_grouped['total_revenue'] / total_rev_overall) * 100

    # KPI Summary Cards
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Total Volume Sold", f"{total_units_overall:,.0f} units")
    kpi2.metric("Total Revenue", f"${total_rev_overall:,.2f}")
    kpi3.metric("Menu Item Count", f"{len(df_grouped)} items")

    st.markdown("---")

    tab1, tab2 = st.tabs(["Top 25% vs Bottom 25% Split", "Time Trend Breakdowns (Monthly/Quarterly)"])

    with tab1:
        st.subheader("Performance Quadrant: Frequency vs. Revenue Share")

        # Frequency Quartiles
        top_freq_cutoff = df_grouped['qty_sold'].quantile(0.75)
        bot_freq_cutoff = df_grouped['qty_sold'].quantile(0.25)

        top_25_freq = df_grouped[df_grouped['qty_sold'] >= top_freq_cutoff].sort_values(by='qty_sold', ascending=False)
        bot_25_freq = df_grouped[df_grouped['qty_sold'] <= bot_freq_cutoff].sort_values(by='qty_sold', ascending=True)

        # Revenue Quartiles
        top_rev_cutoff = df_grouped['total_revenue'].quantile(0.75)
        bot_rev_cutoff = df_grouped['total_revenue'].quantile(0.25)

        top_25_rev = df_grouped[df_grouped['total_revenue'] >= top_rev_cutoff].sort_values(by='total_revenue', ascending=False)
        bot_25_rev = df_grouped[df_grouped['total_revenue'] <= bot_rev_cutoff].sort_values(by='total_revenue', ascending=True)

        col_freq, col_rev = st.columns(2)

        # FREQUENCY COLUMN
        with col_freq:
            st.markdown("### 📊 BY ORDER FREQUENCY (UNITS)")
            
            st.success("🔥 **Top 25% Most Popular Items (High Volume Drivers)**")
            st.dataframe(
                top_25_freq[['item_name', 'qty_sold', 'pct_frequency']]
                .rename(columns={'item_name': 'Item', 'qty_sold': 'Units Sold', 'pct_frequency': '% of Total Volume'})
                .style.format({'% of Total Volume': '{:.2f}%'}),
                use_container_width=True
            )

            st.error("📉 **Bottom 25% Least Popular Items (Drop Candidates)**")
            st.dataframe(
                bot_25_freq[['item_name', 'qty_sold', 'pct_frequency']]
                .rename(columns={'item_name': 'Item', 'qty_sold': 'Units Sold', 'pct_frequency': '% of Total Volume'})
                .style.format({'% of Total Volume': '{:.2f}%'}),
                use_container_width=True
            )

        # REVENUE COLUMN
        with col_rev:
            st.markdown("### 💰 BY REVENUE SHARE ($)")

            st.success("💵 **Top 25% Highest Revenue Drivers**")
            st.dataframe(
                top_25_rev[['item_name', 'total_revenue', 'pct_revenue']]
                .rename(columns={'item_name': 'Item', 'total_revenue': 'Total Revenue ($)', 'pct_revenue': '% of Total Revenue'})
                .style.format({'Total Revenue ($)': '${:,.2f}', '% of Total Revenue': '{:.2f}%'}),
                use_container_width=True
            )

            st.error("🛑 **Bottom 25% Lowest Revenue Contributors**")
            st.dataframe(
                bot_25_rev[['item_name', 'total_revenue', 'pct_revenue']]
                .rename(columns={'item_name': 'Item', 'total_revenue': 'Total Revenue ($)', 'pct_revenue': '% of Total Revenue'})
                .style.format({'Total Revenue ($)': '${:,.2f}', '% of Total Revenue': '{:.2f}%'}),
                use_container_width=True
            )

        st.caption("Note: Middle 50% performers are hidden automatically.")

    with tab2:
        st.subheader("Monthly & Quarterly Trend Analysis")
        group_dim = 'quarter' if time_view == "By Quarter" else 'month' if time_view == "By Month" else 'quarter'
        
        # Pivot Table: Units Sold
        st.markdown(f"#### Units Sold by Item per {group_dim.title()}")
        pivot_units = raw_df.pivot_table(
            index='item_name', columns=group_dim, values='qty_sold', aggfunc='sum', fill_value=0
        )
        st.dataframe(pivot_units, use_container_width=True)

        # Pivot Table: Revenue Share
        st.markdown(f"#### Total Revenue ($) by Item per {group_dim.title()}")
        pivot_rev = raw_df.pivot_table(
            index='item_name', columns=group_dim, values='total_revenue', aggfunc='sum', fill_value=0
        )
        st.dataframe(pivot_rev.style.format("${:,.2f}"), use_container_width=True)

else:
    st.info("Upload one or more CSV files from the sidebar to generate the analysis.")