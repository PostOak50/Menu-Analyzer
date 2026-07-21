import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

st.set_page_config(page_title="Menu Volume & Revenue Engine", layout="wide")

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
    
    # Required columns verification
    required_cols = {'date', 'item_name', 'qty_sold', 'selling_price'}
    if not required_cols.issubset(set(raw_df.columns)):
        st.error(f"CSV files must contain the following columns: {required_cols}")
        st.stop()

    # Data Cleaning: Ignore items without a valid price
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

    # Identify Double Performers
    top_25_freq_names = set(df_grouped[df_grouped['qty_sold'] >= top_freq_cutoff]['item_name'])
    top_25_rev_names = set(df_grouped[df_grouped['total_revenue'] >= top_rev_cutoff]['item_name'])
    double_top_names = top_25_freq_names.intersection(top_25_rev_names)

    # Subsets
    top_25_freq = df_grouped[df_grouped['qty_sold'] >= top_freq_cutoff].sort_values(by='qty_sold', ascending=False)
    top_25_rev = df_grouped[df_grouped['total_revenue'] >= top_rev_cutoff].sort_values(by='total_revenue', ascending=False)

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

    with tab2:
        st.subheader("Monthly & Quarterly Trend Analysis")
        group_dim = 'quarter' if time_view == "By Quarter" else 'month' if time_view == "By Month" else 'quarter'
        
        st.markdown(f"#### Units Sold by Item per {group_dim.title()}")
        pivot_units = raw_df.pivot_table(index='item_name', columns=group_dim, values='qty_sold', aggfunc='sum', fill_value=0)
        st.dataframe(pivot_units, use_container_width=True)

        st.markdown(f"#### Total Revenue ($) by Item per {group_dim.title()}")
        pivot_rev = raw_df.pivot_table(index='item_name', columns=group_dim, values='total_revenue', aggfunc='sum', fill_value=0)
        st.dataframe(pivot_rev.style.format("${:,.2f}"), use_container_width=True)

    with tab3:
        st.subheader("📄 Export Executive PDF Report")
        st.write("Generate a formatted PDF report fitted dynamically for client presentations.")

        if st.button("Generate Executive PDF"):
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer, 
                pagesize=letter, 
                rightMargin=36, 
                leftMargin=36, 
                topMargin=36, 
                bottomMargin=36
            )
            story = []

            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'ReportTitle', parent=styles['Heading1'], fontSize=16, textColor=colors.HexColor("#1A365D"), spaceAfter=2
            )
            sub_style = ParagraphStyle(
                'ReportSub', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor("#718096"), spaceAfter=10
            )
            h2_style = ParagraphStyle(
                'H2Style', parent=styles['Heading2'], fontSize=11, textColor=colors.HexColor("#2C5282"), spaceBefore=6, spaceAfter=4
            )

            # Header
            story.append(Paragraph("Menu Performance Executive Summary", title_style))
            story.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y')} | Filter Mode: {time_view}", sub_style))

            # Executive KPI Table
            kpi_data = [
                ["Total Units Sold", "Total Revenue", "Valid Dishes", "Double Top Performers"],
                [f"{total_units_overall:,.0f}", f"${total_rev_overall:,.2f}", f"{len(df_grouped)}", f"{len(double_top_names)}"]
            ]
            kpi_table = Table(kpi_data, colWidths=[135, 135, 135, 135])
            kpi_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#EDF2F7")),
                ('TEXTCOLOR', (0,0), (-1,0), colors.HexColor("#2D3748")),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,0), 8),
                ('FONTSIZE', (0,1), (-1,1), 10),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E0")),
                ('BACKGROUND', (0,1), (-1,1), colors.white),
                ('PADDING', (0,0), (-1,-1), 5),
            ]))
            story.append(kpi_table)
            story.append(Spacer(1, 8))

            # Helper for Font Auto-Scaling
            def get_font_size(row_count):
                if row_count > 30:
                    return 6, 4
                elif row_count > 20:
                    return 7, 5
                else:
                    return 8, 6

            # TOP 25% TABLE SECTION
            top_row_count = len(top_25_freq)
            f_size, p_size = get_font_size(top_row_count)

            top_table_data = [["Item Name", "Units Sold", "% Volume", "Revenue ($)", "% Revenue Share"]]
            top_styles = [
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2C5282")),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), f_size),
                ('PADDING', (0,0), (-1,-1), p_size),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
                ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
            ]

            for idx, (_, r) in enumerate(top_25_freq.iterrows(), start=1):
                is_dbl = r['item_name'] in double_top_names
                label = f"{r['item_name']} (Top Vol & Rev)" if is_dbl else r['item_name']
                top_table_data.append([
                    label[:32],
                    f"{r['qty_sold']:,.0f}",
                    f"{r['pct_frequency']:.2f}%",
                    f"${r['total_revenue']:,.2f}",
                    f"{r['pct_revenue']:.2f}%"
                ])
                if is_dbl:
                    top_styles.append(('BACKGROUND', (0, idx), (-1, idx), colors.HexColor("#D4EDDA")))
                    top_styles.append(('TEXTCOLOR', (0, idx), (-1, idx), colors.HexColor("#155724")))

            top_table = Table(top_table_data, colWidths=[200, 85, 85, 85, 85])
            top_table.setStyle(TableStyle(top_styles))
            
            top_block = [
                Paragraph("Top 25% Performers (🔥 High Volume / Revenue)", h2_style),
                top_table
            ]
            story.append(KeepTogether(top_block))
            story.append(Spacer(1, 10))

            # BOTTOM 25% TABLE SECTION
            bot_row_count = len(bot_25_freq)
            f_size_b, p_size_b = get_font_size(bot_row_count)

            bot_table_data = [["Item Name", "Units Sold", "Monthly Avg", "Revenue ($)", "% Revenue Share"]]
            bot_table_data.extend([
                r['item_name'][:32],
                f"{r['qty_sold']:,.0f}",
                f"{r['avg_monthly_qty']:.1f}",
                f"${r['total_revenue']:,.2f}",
                f"{r['pct_revenue']:.2f}%"
            ] for _, r in bot_25_freq.iterrows())

            bot_table = Table(bot_table_data, colWidths=[200, 85, 85, 85, 85])
            bot_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#9B2C2C")),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), f_size_b),
                ('PADDING', (0,0), (-1,-1), p_size_b),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
                ('ALIGN', (1,0), (-1,-1), 'RIGHT'),
            ]))

            bot_block = [
                Paragraph("Bottom Performers (📉 Bottom 25% or < 50 units/month)", h2_style),
                bot_table
            ]
            story.append(KeepTogether(bot_block))

            # Build Document
            doc.build(story)
            pdf_bytes = buffer.getvalue()
            buffer.close()

            st.download_button(
                label="📥 Download Executive PDF Report",
                data=pdf_bytes,
                file_name=f"Menu_Executive_Report_{datetime.now().strftime('%Y_%m_%d')}.pdf",
                mime="application/pdf"
            )

else:
    st.info("Upload one or more CSV files from the sidebar to generate the analysis.")