import streamlit as st
import pandas as pd
import plotly.express as px
import weasyprint
from datetime import datetime

st.set_page_config(page_title="Menu Popularity & Revenue Share Engine", layout="wide")

st.title("Restaurant Menu Volume & Revenue Share Engine")
st.markdown("Analyze dish popularity by **Monthly** and **Quarterly** breakdown, highlighting Top 25% and Bottom 25% performers, items sold under 50 units/month, and PDF exports.")

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
    
    # Required columns
    required_cols = {'date', 'item_name', 'qty_sold', 'selling_price'}
    if not required_cols.issubset(set(raw_df.columns)):
        st.error(f"CSV files must contain the following columns: {required_cols}")
        st.stop()

    # Data Cleaning: Ignore items without a valid price (null, zero, or missing)
    raw_df['selling_price'] = pd.to_numeric(raw_df['selling_price'], errors='coerce')
    raw_df = raw_df.dropna(subset=['selling_price'])
    raw_df = raw_df[raw_df['selling_price'] > 0]

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

    # Distinct month count for < 50 units/month check
    num_months = max(1, filtered_df['month'].nunique())

    # Aggregations
    df_grouped = filtered_df.groupby('item_name').agg({
        'qty_sold': 'sum',
        'total_revenue': 'sum',
        'selling_price': 'mean'
    }).reset_index()

    df_grouped['avg_monthly_qty'] = df_grouped['qty_sold'] / num_months

    total_units_overall = df_grouped['qty_sold'].sum()
    total_rev_overall = df_grouped['total_revenue'].sum()

    # Percentage Share Calculations
    df_grouped['pct_frequency'] = (df_grouped['qty_sold'] / total_units_overall) * 100
    df_grouped['pct_revenue'] = (df_grouped['total_revenue'] / total_rev_overall) * 100

    # Quartile Thresholds
    top_freq_cutoff = df_grouped['qty_sold'].quantile(0.75)
    bot_freq_cutoff = df_grouped['qty_sold'].quantile(0.25)
    top_rev_cutoff = df_grouped['total_revenue'].quantile(0.75)
    bot_rev_cutoff = df_grouped['total_revenue'].quantile(0.25)

    # Identify Double Performers (Top 25% Volume AND Top 25% Revenue)
    top_25_freq_names = set(df_grouped[df_grouped['qty_sold'] >= top_freq_cutoff]['item_name'])
    top_25_rev_names = set(df_grouped[df_grouped['total_revenue'] >= top_rev_cutoff]['item_name'])
    double_top_names = top_25_freq_names.intersection(top_25_rev_names)

    # Dataframe Subsets
    top_25_freq = df_grouped[df_grouped['qty_sold'] >= top_freq_cutoff].sort_values(by='qty_sold', ascending=False)
    top_25_rev = df_grouped[df_grouped['total_revenue'] >= top_rev_cutoff].sort_values(by='total_revenue', ascending=False)

    # Bottom 25% OR < 50 units/month
    bot_25_freq = df_grouped[(df_grouped['qty_sold'] <= bot_freq_cutoff) | (df_grouped['avg_monthly_qty'] < 50)].sort_values(by='qty_sold', ascending=True)
    bot_25_rev = df_grouped[(df_grouped['total_revenue'] <= bot_rev_cutoff) | (df_grouped['avg_monthly_qty'] < 50)].sort_values(by='total_revenue', ascending=True)

    # KPI Summary Cards
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Total Volume Sold", f"{total_units_overall:,.0f} units")
    kpi2.metric("Total Revenue", f"${total_rev_overall:,.2f}")
    kpi3.metric("Valid Menu Items", f"{len(df_grouped)} items")
    kpi4.metric("Double Top Performers 🟢", f"{len(double_top_names)} items")

    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["Top 25% vs Bottom 25% Split", "Time Trend Breakdowns", "Export PDF Report"])

    with tab1:
        st.subheader("Performance Quadrant: Frequency vs. Revenue Share")
        st.info("🟢 **Highlight Note:** Items highlighted in green are **Double Performers** (belonging to BOTH Top 25% Volume AND Top 25% Revenue).")

        col_freq, col_rev = st.columns(2)

        def highlight_double_top(row):
            if row['Item'] in double_top_names:
                return ['background-color: #d4edda; font-weight: bold; color: #155724;'] * len(row)
            return [''] * len(row)

        # FREQUENCY COLUMN
        with col_freq:
            st.markdown("### 📊 BY ORDER FREQUENCY (UNITS)")
            
            st.success("🔥 **Top 25% Most Popular Items**")
            top_freq_disp = top_25_freq[['item_name', 'qty_sold', 'pct_frequency']].rename(
                columns={'item_name': 'Item', 'qty_sold': 'Units Sold', 'pct_frequency': '% Volume'}
            )
            st.dataframe(
                top_freq_disp.style.apply(highlight_double_top, axis=1).format({'% Volume': '{:.2f}%'}),
                use_container_width=True
            )

            st.error("📉 **Bottom 25% / Low Volume (< 50/mo)**")
            bot_freq_disp = bot_25_freq[['item_name', 'qty_sold', 'avg_monthly_qty', 'pct_frequency']].rename(
                columns={'item_name': 'Item', 'qty_sold': 'Units Sold', 'avg_monthly_qty': 'Monthly Avg', 'pct_frequency': '% Volume'}
            )
            st.dataframe(
                bot_freq_disp.style.format({'Monthly Avg': '{:.1f}', '% Volume': '{:.2f}%'}),
                use_container_width=True
            )

        # REVENUE COLUMN
        with col_rev:
            st.markdown("### 💰 BY REVENUE SHARE ($)")

            st.success("💵 **Top 25% Highest Revenue Drivers**")
            top_rev_disp = top_25_rev[['item_name', 'total_revenue', 'pct_revenue']].rename(
                columns={'item_name': 'Item', 'total_revenue': 'Total Revenue ($)', 'pct_revenue': '% Revenue'}
            )
            st.dataframe(
                top_rev_disp.style.apply(highlight_double_top, axis=1).format({'Total Revenue ($)': '${:,.2f}', '% Revenue': '{:.2f}%'}),
                use_container_width=True
            )

            st.error("🛑 **Bottom 25% / Low Volume (< 50/mo)**")
            bot_rev_disp = bot_25_rev[['item_name', 'total_revenue', 'avg_monthly_qty', 'pct_revenue']].rename(
                columns={'item_name': 'Item', 'total_revenue': 'Total Revenue ($)', 'avg_monthly_qty': 'Monthly Avg', 'pct_revenue': '% Revenue'}
            )
            st.dataframe(
                bot_rev_disp.style.format({'Total Revenue ($)': '${:,.2f}', 'Monthly Avg': '{:.1f}', '% Revenue': '{:.2f}%'}),
                use_container_width=True
            )

        st.caption("Note: Items without prices are ignored. Middle 50% performers are hidden automatically.")

    with tab2:
        st.subheader("Monthly & Quarterly Trend Analysis")
        group_dim = 'quarter' if time_view == "By Quarter" else 'month' if time_view == "By Month" else 'quarter'
        
        st.markdown(f"#### Units Sold by Item per {group_dim.title()}")
        pivot_units = raw_df.pivot_table(
            index='item_name', columns=group_dim, values='qty_sold', aggfunc='sum', fill_value=0
        )
        st.dataframe(pivot_units, use_container_width=True)

        st.markdown(f"#### Total Revenue ($) by Item per {group_dim.title()}")
        pivot_rev = raw_df.pivot_table(
            index='item_name', columns=group_dim, values='total_revenue', aggfunc='sum', fill_value=0
        )
        st.dataframe(pivot_rev.style.format("${:,.2f}"), use_container_width=True)

    with tab3:
        st.subheader("📄 Generate & Export Executive PDF Report")
        st.write("Click below to compile this month's menu analysis into a styled PDF report ready for email attachment.")

        if st.button("Generate PDF Executive Report"):
            now_str = datetime.now().strftime("%B %d, %Y")
            
            top_freq_rows = ""
            for _, r in top_25_freq.iterrows():
                is_dbl = r['item_name'] in double_top_names
                bg = "background-color: #d4edda; font-weight: bold; color: #155724;" if is_dbl else ""
                badge = " 🟢 (Top Vol & Rev)" if is_dbl else ""
                top_freq_rows += f"<tr style='{bg}'><td>{r['item_name']}{badge}</td><td>{r['qty_sold']:,.0f}</td><td>{r['pct_frequency']:.2f}%</td></tr>"

            top_rev_rows = ""
            for _, r in top_25_rev.iterrows():
                is_dbl = r['item_name'] in double_top_names
                bg = "background-color: #d4edda; font-weight: bold; color: #155724;" if is_dbl else ""
                badge = " 🟢 (Top Vol & Rev)" if is_dbl else ""
                top_rev_rows += f"<tr style='{bg}'><td>{r['item_name']}{badge}</td><td>${r['total_revenue']:,.2f}</td><td>{r['pct_revenue']:.2f}%</td></tr>"

            bot_freq_rows = ""
            for _, r in bot_25_freq.iterrows():
                bot_freq_rows += f"<tr><td>{r['item_name']}</td><td>{r['qty_sold']:,.0f}</td><td>{r['avg_monthly_qty']:.1f}</td><td>{r['pct_frequency']:.2f}%</td></tr>"

            bot_rev_rows = ""
            for _, r in bot_25_rev.iterrows():
                bot_rev_rows += f"<tr><td>{r['item_name']}</td><td>${r['total_revenue']:,.2f}</td><td>{r['avg_monthly_qty']:.1f}</td><td>{r['pct_revenue']:.2f}%</td></tr>"

            html_doc = f"""
            <!DOCTYPE html>
            <html>
            <head>
            <style>
                @page {{ size: A4; margin: 15mm 12mm; }}
                body {{ font-family: 'Helvetica', 'Arial', sans-serif; color: #333; margin: 0; padding: 0; font-size: 10pt; }}
                h1 {{ color: #1a365d; margin-bottom: 5px; font-size: 18pt; }}
                .subtitle {{ color: #718096; font-size: 10pt; margin-bottom: 20px; }}
                .kpi-container {{ display: table; width: 100%; margin-bottom: 20px; background: #f7fafc; border: 1px solid #e2e8f0; border-radius: 5px; }}
                .kpi-box {{ display: table-cell; text-align: center; padding: 12px; width: 25%; }}
                .kpi-val {{ font-size: 14pt; font-weight: bold; color: #2b6cb0; }}
                .kpi-lbl {{ font-size: 8pt; color: #4a5568; text-transform: uppercase; }}
                h2 {{ color: #2c5282; font-size: 13pt; border-bottom: 2px solid #e2e8f0; padding-bottom: 4px; margin-top: 15px; page-break-after: avoid; }}
                table {{ width: 100%; border-collapse: collapse; margin-bottom: 15px; font-size: 9pt; }}
                th {{ background-color: #edf2f7; color: #2d3748; text-align: left; padding: 6px; border: 1px solid #cbd5e0; font-size: 8pt; }}
                td {{ padding: 6px; border: 1px solid #e2e8f0; }}
                .section-grid {{ display: table; width: 100%; }}
                .section-col {{ display: table-cell; width: 48%; vertical-align: top; padding-right: 2%; }}
                .section-col:last-child {{ padding-right: 0; padding-left: 2%; }}
                .legend-box {{ background-color: #d4edda; color: #155724; padding: 8px 12px; border-radius: 4px; font-size: 9pt; margin-bottom: 15px; border: 1px solid #c3e6cb; }}
            </style>
            </head>
            <body>
                <h1>Menu Performance Executive Report</h1>
                <div class="subtitle">Generated on {now_str} | Filter Mode: {time_view}</div>

                <div class="kpi-container">
                    <div class="kpi-box"><div class="kpi-val">{total_units_overall:,.0f}</div><div class="kpi-lbl">Total Units</div></div>
                    <div class="kpi-box"><div class="kpi-val">${total_rev_overall:,.2f}</div><div class="kpi-lbl">Total Revenue</div></div>
                    <div class="kpi-box"><div class="kpi-val">{len(df_grouped)}</div><div class="kpi-lbl">Valid Dishes</div></div>
                    <div class="kpi-box"><div class="kpi-val">{len(double_top_names)}</div><div class="kpi-lbl">Double Top 🟢</div></div>
                </div>

                <div class="legend-box">
                    <strong>🟢 Green Highlight:</strong> Items qualifying as BOTH Top 25% by Order Volume AND Top 25% by Revenue Contribution.
                </div>

                <h2>Top 25% Performers</h2>
                <div class="section-grid">
                    <div class="section-col">
                        <h3>By Volume (Order Frequency)</h3>
                        <table>
                            <thead><tr><th>Item Name</th><th>Units</th><th>% Share</th></tr></thead>
                            <tbody>{top_freq_rows}</tbody>
                        </table>
                    </div>
                    <div class="section-col">
                        <h3>By Revenue Share</h3>
                        <table>
                            <thead><tr><th>Item Name</th><th>Revenue ($)</th><th>% Share</th></tr></thead>
                            <tbody>{top_rev_rows}</tbody>
                        </table>
                    </div>
                </div>

                <h2>Bottom Performers (Bottom 25% or < 50 units/month)</h2>
                <div class="section-grid">
                    <div class="section-col">
                        <h3>Lowest Volume Items</h3>
                        <table>
                            <thead><tr><th>Item Name</th><th>Units</th><th>Mo. Avg</th><th>% Share</th></tr></thead>
                            <tbody>{bot_freq_rows}</tbody>
                        </table>
                    </div>
                    <div class="section-col">
                        <h3>Lowest Revenue Contributors</h3>
                        <table>
                            <thead><tr><th>Item Name</th><th>Revenue ($)</th><th>Mo. Avg</th><th>% Share</th></tr></thead>
                            <tbody>{bot_rev_rows}</tbody>
                        </table>
                    </div>
                </div>
            </body>
            </html>
            """

            weasyprint.HTML(string=html_doc).write_pdf("menu_executive_report.pdf")
            
            with open("menu_executive_report.pdf", "rb") as pdf_file:
                PDFbyte = pdf_file.read()

            st.download_button(
                label="📥 Download PDF Executive Report",
                data=PDFbyte,
                file_name=f"Menu_Report_{datetime.now().strftime('%Y_%m_%d')}.pdf",
                mime="application/pdf"
            )

else:
    st.info("Upload one or more CSV files from the sidebar to generate the analysis.")