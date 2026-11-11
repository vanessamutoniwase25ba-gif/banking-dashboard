"""
Banking Customer & Business Analytics - Streamlit Dashboard
Built from the Jupyter notebook "Banking_Analysis.ipynb".
All money values are in RWF (Rwandan Francs).

Run with:   streamlit run app.py
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from scipy import stats

# ------------------------------------------------------------------
# 0. PAGE SETUP & STYLE
# ------------------------------------------------------------------
st.set_page_config(page_title="Banking Analytics Dashboard", page_icon="🏦", layout="wide")

# ---- BK brand colours ----
BK_BLUE    = "#034EA2"
NAVY       = "#011B39"
BK_GOLD    = "#EB9C20"
LIGHT_GRAY = "#F4F5F8"
TEAL, GOLD = BK_BLUE, BK_GOLD          # the rest of the code uses these two names
RED, GREEN = "#C8102E", "#2E8B57"      # kept only for loan risk (Non-Performing / Performing)
PALETTE = [BK_BLUE, BK_GOLD, NAVY, "#5B8FD1", "#F5C77E", "#8A9BB0", "#2E8B57"]
STATUS_COLORS = {"Performing": GREEN, "Watch": GOLD, "Non-Performing": RED}
SEGMENT_ORDER = ["Retail", "SME", "Corporate", "Agribusiness", "Institutional Banking"]
REFERENCE_DATE = pd.Timestamp("2026-11-10")   # "today", used for customer tenure (same as notebook)
DIGITAL_CHANNELS = ["Mobile", "Internet"]
# Folder with the 5 CSV files. Default = a "Data" folder next to app.py.
# You can also write your own path, e.g. Path(r"C:\\Users\\You\\Desktop\\Data")
DATA_FOLDER = Path(__file__).parent
FILES = ["Branches", "Customers", "Accounts", "Transactions", "Loans"]

st.markdown(f"""
<style>
    .stApp {{background: {LIGHT_GRAY};}}
    .block-container {{padding-top: 1.5rem;}}
    .hero {{
        background: linear-gradient(120deg, {NAVY} 0%, {BK_BLUE} 100%);
        padding: 1.6rem 2rem; border-radius: 16px; color: white; margin-bottom: 1.2rem;
        box-shadow: 0 6px 18px rgba(1,27,57,.25); border-bottom: 5px solid {BK_GOLD};
    }}
    .hero h1 {{color: white; margin: 0; font-size: 2rem;}}
    .hero p  {{color: #D6E3F3; margin: .3rem 0 0 0; font-size: 1rem;}}
    .kpi {{
        background: white; border-radius: 14px; padding: 1rem 1.1rem;
        border-left: 6px solid {TEAL}; box-shadow: 0 2px 10px rgba(0,0,0,.07); height: 100%;
    }}
    .kpi .label {{color: #5A6B82; font-size: .80rem; text-transform: uppercase; letter-spacing: .05em;}}
    .kpi .value {{color: {NAVY}; font-size: 1.55rem; font-weight: 700; margin-top: .2rem;}}
    .kpi .note  {{color: #8A97A8; font-size: .78rem; margin-top: .15rem;}}
    .insight {{
        background: white; border-left: 5px solid {BK_BLUE}; border-radius: 10px;
        padding: .8rem 1rem; margin: .4rem 0 1rem 0; color: {NAVY};
    }}
    .warn {{background: #FDF3E1; border-left-color: {GOLD};}}
    .danger {{background: #FBEAEC; border-left-color: {RED};}}
    div[data-baseweb="tab-list"] button {{font-weight: 600;}}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------
# Small helpers
# ------------------------------------------------------------------
_NEW_WIDTH_API = tuple(int(x) for x in st.__version__.split(".")[:2]) >= (1, 50)


def show_chart(fig):
    """Display a plotly chart full width (works on old and new Streamlit versions)."""
    fig.update_traces(textangle=0, selector=dict(type="bar"))
    fig.update_layout(template="plotly_white", font=dict(family="Segoe UI, Arial", size=13),
                      margin=dict(l=10, r=10, t=55, b=10), title_font=dict(size=16, color=NAVY))
    if _NEW_WIDTH_API:
        st.plotly_chart(fig, width="stretch")
    else:
        st.plotly_chart(fig, use_container_width=True)


def show_table(df, **kwargs):
    if _NEW_WIDTH_API:
        st.dataframe(df, width="stretch", **kwargs)
    else:
        st.dataframe(df, use_container_width=True, **kwargs)


def rwf(x):
    """Short money format: 3.71B, 489.9M, 52.3K."""
    for size, unit in [(1e9, "B"), (1e6, "M"), (1e3, "K")]:
        if abs(x) >= size:
            return f"RWF {x / size:,.2f}{unit}"
    return f"RWF {x:,.0f}"


def kpi(col, label, value, note="", color=TEAL):
    col.markdown(f"""<div class="kpi" style="border-left-color:{color}">
        <div class="label">{label}</div><div class="value">{value}</div>
        <div class="note">{note}</div></div>""", unsafe_allow_html=True)


def insight(text, kind=""):
    st.markdown(f'<div class="insight {kind}"> {text}</div>', unsafe_allow_html=True)


# ------------------------------------------------------------------
# 1. LOAD THE DATA  (from the Data/ folder, or uploaded in the sidebar)
# ------------------------------------------------------------------
@st.cache_data(show_spinner="Loading data...")
def read_csvs(folder: str):
    return {name: pd.read_csv(Path(folder) / f"{name}.csv") for name in FILES}


st.sidebar.markdown("## Banking Analytics")

missing = [n for n in FILES if not (DATA_FOLDER / f"{n}.csv").exists()]
if missing:
    st.error(f"Could not find: **{', '.join(n + '.csv' for n in missing)}** in the folder `{DATA_FOLDER}`.\n\n"
             "Put the 5 CSV files (Branches, Customers, Accounts, Transactions, Loans) in that folder, "
             "or change `DATA_FOLDER` at the top of app.py to the folder where your files are.")
    st.stop()

raw = read_csvs(str(DATA_FOLDER))


# ------------------------------------------------------------------
# 2. DATA QUALITY + CLEANING  (same steps as the notebook)
# ------------------------------------------------------------------
@st.cache_data
def clean_data(raw: dict):
    branches = raw["Branches"].copy()
    customers = raw["Customers"].copy()
    accounts = raw["Accounts"].copy()
    transactions = raw["Transactions"].copy()
    loans = raw["Loans"].copy()

    # Fill missing values: median for skewed numbers, "Unknown" for category
    customers["Age"] = customers["Age"].fillna(customers["Age"].median())
    accounts["Balance"] = accounts["Balance"].fillna(accounts["Balance"].median())
    transactions["Channel"] = transactions["Channel"].fillna("Unknown")

    # Text -> real dates
    customers["Customer_Since"] = pd.to_datetime(customers["Customer_Since"])
    transactions["Transaction_Date"] = pd.to_datetime(transactions["Transaction_Date"])
    loans["Disbursement_Date"] = pd.to_datetime(loans["Disbursement_Date"])

    # Join: Region on customers, then Segment/Region/Gender on the other tables
    customers = customers.merge(branches[["Branch_ID", "Region"]], on="Branch_ID", how="left")
    cust_info = customers[["Customer_ID", "Segment", "Region", "Gender"]]
    accounts = accounts.merge(cust_info, on="Customer_ID", how="left")
    transactions = transactions.merge(cust_info, on="Customer_ID", how="left")
    loans = loans.merge(cust_info, on="Customer_ID", how="left")

    # New columns
    customers["Age_Group"] = pd.cut(customers["Age"], bins=[17, 25, 35, 45, 55, 100],
                                    labels=["18-25", "26-35", "36-45", "46-55", "56+"])
    customers["Tenure_Years"] = (REFERENCE_DATE - customers["Customer_Since"]).dt.days / 365
    transactions["Month"] = transactions["Transaction_Date"].dt.strftime("%Y-%m")
    transactions["Digital"] = transactions["Channel"].isin(DIGITAL_CHANNELS)
    loans["Over_Borrowed"] = loans["Outstanding_Balance"] > loans["Loan_Amount"]
    return customers, accounts, transactions, loans


customers_all, accounts_all, transactions_all, loans_all = clean_data(raw)


# ------------------------------------------------------------------
# 3. SIDEBAR FILTERS
# ------------------------------------------------------------------
st.sidebar.markdown("### Filters")
seg_options = [s for s in SEGMENT_ORDER if s in customers_all["Segment"].unique()] + \
              sorted(set(customers_all["Segment"].dropna()) - set(SEGMENT_ORDER))
sel_seg = st.sidebar.multiselect("Segment", seg_options, default=seg_options)
reg_options = sorted(customers_all["Region"].dropna().unique())
sel_reg = st.sidebar.multiselect("Region", reg_options, default=reg_options)
gen_options = sorted(customers_all["Gender"].dropna().unique())
sel_gen = st.sidebar.multiselect("Gender", gen_options, default=gen_options)

if not (sel_seg and sel_reg and sel_gen):
    st.warning("Please select at least one Segment, Region and Gender in the sidebar.")
    st.stop()


def apply_filters(df):
    return df[df["Segment"].isin(sel_seg) & df["Region"].isin(sel_reg) & df["Gender"].isin(sel_gen)]


customers = apply_filters(customers_all)
accounts = apply_filters(accounts_all)
transactions = apply_filters(transactions_all)
loans = apply_filters(loans_all)

st.sidebar.caption(f"Showing **{len(customers):,}** of {len(customers_all):,} customers")
st.sidebar.markdown("---")
st.sidebar.caption("All money values are in RWF (Rwandan Francs).")


# ------------------------------------------------------------------
# KEY NUMBERS used across tabs
# ------------------------------------------------------------------
total_balance = accounts["Balance"].sum()
total_loans = loans["Loan_Amount"].sum()
total_outstanding = loans["Outstanding_Balance"].sum()
npl_out = loans.loc[loans["Loan_Status"] == "Non-Performing", "Outstanding_Balance"].sum()
watch_out = loans.loc[loans["Loan_Status"] == "Watch", "Outstanding_Balance"].sum()
npl_ratio = npl_out / total_outstanding * 100 if total_outstanding else 0
at_risk_ratio = (npl_out + watch_out) / total_outstanding * 100 if total_outstanding else 0
digital_share = transactions["Digital"].mean() * 100 if len(transactions) else 0

# Header
st.markdown(f"""<div class="hero">
    <h1>Banking Customer & Business Analytics</h1>
    <p>Customers · Deposits · Transactions · Loans · Segment performance &nbsp;|&nbsp;
    {len(customers):,} customers · {len(transactions):,} transactions · {len(loans):,} loans</p>
</div>""", unsafe_allow_html=True)

tabs = st.tabs(["Overview", "Data Quality", "Customers",  "Deposits",
                "Transactions", "Loans", "Segments", "Insights"])


# ==================================================================
# TAB 1 - OVERVIEW
# ==================================================================
with tabs[0]:
    c = st.columns(4)
    kpi(c[0], "Customers", f"{len(customers):,}", f"{customers['Segment'].nunique()} segments")
    kpi(c[1], "Total deposits", rwf(total_balance), f"Avg {rwf(accounts['Balance'].mean() if len(accounts) else 0)} / account", NAVY)
    kpi(c[2], "Loan outstanding", rwf(total_outstanding), f"{len(loans):,} loans · disbursed {rwf(total_loans)}", GOLD)
    kpi(c[3], "NPL ratio", f"{npl_ratio:.1f}%", f"Watch + NPL at risk: {at_risk_ratio:.1f}%", RED)
    st.write("")
    c = st.columns(4)
    kpi(c[0], "Transactions", f"{len(transactions):,}", f"Value {rwf(transactions['Amount'].sum())}")
    kpi(c[1], "Digital adoption", f"{digital_share:.1f}%", "Mobile + Internet share", GREEN)
    kpi(c[2], "Dormant accounts", f"{(accounts['Account_Status'] == 'Dormant').sum():,}",
        f"of {len(accounts):,} accounts", GOLD)
    kpi(c[3], "Avg tenure", f"{customers['Tenure_Years'].mean():.1f} yrs",
        f"Avg age {customers['Age'].mean():.1f}", NAVY)
    st.write("")

    left, right = st.columns(2)
    with left:
        comp = pd.DataFrame({
            "Customers %": customers["Segment"].value_counts(normalize=True) * 100,
            "Balance %": accounts.groupby("Segment")["Balance"].sum() / total_balance * 100,
        }).reindex([s for s in seg_options if s in sel_seg]).fillna(0).reset_index(names="Segment")
        fig = px.bar(comp.melt(id_vars="Segment", var_name="Measure", value_name="Share"),
                     x="Segment", y="Share", color="Measure", barmode="group", text_auto=".1f",
                     color_discrete_sequence=[TEAL, NAVY],
                     title="Customer share vs Deposit share by Segment (%)")
        fig.update_layout(yaxis_title="%", xaxis_title="", legend_title="")
        show_chart(fig)
    with right:
        monthly = transactions.groupby("Month")["Amount"].agg(["count", "sum"]).reset_index()
        fig = go.Figure()
        fig.add_bar(x=monthly["Month"], y=monthly["sum"] / 1e6, name="Value (RWF M)",
                    marker_color=TEAL, opacity=.75)
        fig.add_scatter(x=monthly["Month"], y=monthly["count"], name="Number", yaxis="y2",
                        mode="lines+markers", line=dict(color=NAVY, width=3))
        fig.update_layout(title="Monthly Transactions (number & value)",
                          yaxis=dict(title="RWF millions"),
                          yaxis2=dict(title="Transactions", overlaying="y", side="right"),
                          legend=dict(orientation="h", y=-0.15, x=0))
        show_chart(fig)

    left, right = st.columns(2)
    with left:
        st_counts = loans["Loan_Status"].value_counts().reset_index()
        fig = px.pie(st_counts, names="Loan_Status", values="count", hole=.55,
                     color="Loan_Status", color_discrete_map=STATUS_COLORS, title="Loans by Status")
        fig.update_traces(textinfo="percent+label")
        show_chart(fig)
    with right:
        ch = transactions["Channel"].value_counts().reset_index()
        ch["Type"] = ch["Channel"].apply(lambda x: "Digital" if x in DIGITAL_CHANNELS else "Other")
        fig = px.bar(ch, x="count", y="Channel", orientation="h", color="Type", text_auto=",",
                     color_discrete_map={"Digital": TEAL, "Other": "#B8C2D0"},
                     title="Transactions by Channel")
        fig.update_layout(yaxis=dict(categoryorder="total ascending", title=""), xaxis_title="Transactions")
        show_chart(fig)


# ==================================================================
# TAB 2 - DATA QUALITY (uses the raw, un-filtered data)
# ==================================================================
with tabs[1]:
    st.subheader("Data quality checks (raw data, before cleaning)")
    c = st.columns(5)
    for col, name in zip(c, FILES):
        r, k = raw[name].shape
        kpi(col, name, f"{r:,}", f"rows · {k} columns")
    st.write("")

    left, right = st.columns(2)
    with left:
        st.markdown("**Missing values per column**")
        miss = pd.concat([raw[n].isna().sum().rename("Missing").to_frame().assign(Table=n)
                          for n in FILES]).reset_index(names="Column")
        miss = miss[miss["Missing"] > 0][["Table", "Column", "Missing"]]
        if miss.empty:
            st.success("No missing values.")
        else:
            show_table(miss, hide_index=True)
            st.caption("Fixed by: Age & Balance → median (skewed numbers), Channel → 'Unknown'.")
    with right:
        st.markdown("**Duplicate IDs**")
        ids = {"Customers": "Customer_ID", "Accounts": "Account_ID",
               "Transactions": "Transaction_ID", "Loans": "Loan_ID"}
        dup = pd.DataFrame({"Table": list(ids),
                            "Duplicates": [int(raw[t][c].duplicated().sum()) for t, c in ids.items()]})
        show_table(dup, hide_index=True)

    over = loans_all[loans_all["Over_Borrowed"]]
    insight(f"<b>{len(over):,} loans</b> have an outstanding balance bigger than the original loan "
            f"amount. This may be interest/penalties or a data entry error – kept but flagged.", "warn")
    with st.expander("See these loans"):
        show_table(over[["Loan_ID", "Customer_ID", "Loan_Type", "Loan_Amount",
                         "Outstanding_Balance", "Loan_Status"]], hide_index=True)

    st.markdown("**Distribution & normality test (why we used the median)**")
    left, right = st.columns(2)
    for col, (label, series) in zip([left, right], [("Age", raw["Customers"]["Age"]),
                                                     ("Balance", raw["Accounts"]["Balance"])]):
        s = series.dropna()                               # drop NaN first, otherwise p-value = nan
        _, p = stats.normaltest(s)
        with col:
            fig = px.histogram(s, nbins=40, color_discrete_sequence=[TEAL],
                               title=f"{label} distribution")
            fig.update_layout(showlegend=False, xaxis_title=label, yaxis_title="Count")
            show_chart(fig)
            verdict = "normally distributed" if p > 0.05 else "NOT normally distributed → use median"
            st.caption(f"D'Agostino K² test p-value = {p:.4f} → {verdict}")


# ==================================================================
# TAB 3 - CUSTOMERS
# ==================================================================
with tabs[2]:
    c = st.columns(3)
    kpi(c[0], "Customers", f"{len(customers):,}")
    kpi(c[1], "Average age", f"{customers['Age'].mean():.1f}", "years", NAVY)
    kpi(c[2], "Average tenure", f"{customers['Tenure_Years'].mean():.1f} yrs",
        f"as of {REFERENCE_DATE:%d %b %Y}", GOLD)
    st.write("")

    left, mid, right = st.columns(3)
    with left:
        d = customers["Segment"].value_counts().reset_index()
        fig = px.bar(d, x="Segment", y="count", text_auto=True, color="Segment",
                     color_discrete_sequence=PALETTE, title="Customers by Segment")
        fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Customers")
        show_chart(fig)
    with mid:
        d = customers["Region"].value_counts().reset_index()
        fig = px.pie(d, names="Region", values="count", hole=.5, title="Customers by Region",
                     color_discrete_sequence=PALETTE)
        show_chart(fig)
    with right:
        d = customers["Gender"].value_counts().reset_index()
        fig = px.pie(d, names="Gender", values="count", hole=.5, title="Customers by Gender",
                     color_discrete_sequence=[TEAL, NAVY, GOLD])
        show_chart(fig)

    left, right = st.columns(2)
    with left:
        d = customers.groupby(["Age_Group", "Segment"], observed=False).size().reset_index(name="Customers")
        fig = px.bar(d, x="Age_Group", y="Customers", color="Segment",
                     color_discrete_sequence=PALETTE, title="Age Groups by Segment")
        fig.update_layout(xaxis_title="Age group")
        show_chart(fig)
    with right:
        d = customers.groupby("Segment").agg(Avg_Age=("Age", "mean"),
                                             Avg_Tenure=("Tenure_Years", "mean")).round(1).reset_index()
        fig = px.bar(d.melt(id_vars="Segment"), x="Segment", y="value", color="variable",
                     barmode="group", text_auto=True, color_discrete_sequence=[NAVY, GOLD],
                     title="Average Age & Tenure (years) by Segment")
        fig.update_layout(xaxis_title="", yaxis_title="Years", legend_title="")
        show_chart(fig)
    insight("Corporate and Institutional Banking customers are organisations, so Age and Gender "
            "are less meaningful there – age analysis is most useful for Retail.")


# ==================================================================
# TAB 4 - DEPOSITS
# ==================================================================
with tabs[3]:
    c = st.columns(4)
    kpi(c[0], "Total balance", rwf(total_balance))
    kpi(c[1], "Average balance", rwf(accounts["Balance"].mean() if len(accounts) else 0), "per account", NAVY)
    kpi(c[2], "Accounts", f"{len(accounts):,}", f"{accounts['Customer_ID'].nunique():,} customers", GOLD)
    kpi(c[3], "Dormant accounts", f"{(accounts['Account_Status'] == 'Dormant').sum():,}", "need reactivation", RED)
    st.write("")

    left, right = st.columns(2)
    with left:
        d = (accounts.groupby("Segment")["Balance"].sum() / 1e6).sort_values().reset_index()
        fig = px.bar(d, x="Balance", y="Segment", orientation="h", text_auto=",.0f",
                     color_discrete_sequence=[GREEN], title="Total Deposits by Segment (RWF millions)")
        fig.update_layout(xaxis_title="RWF millions", yaxis_title="")
        show_chart(fig)
    with right:
        d = accounts.groupby(["Region", "Account_Type"])["Balance"].sum().reset_index()
        d["Balance"] = d["Balance"] / 1e6
        fig = px.sunburst(d, path=["Region", "Account_Type"], values="Balance",
                          color_discrete_sequence=PALETTE,
                          title="Deposits by Region → Account Type (RWF M)")
        show_chart(fig)

    st.markdown("**Balance summary tables**")
    t1, t2, t3 = st.columns(3)
    for col, by in zip([t1, t2, t3], ["Segment", "Region", "Account_Type"]):
        with col:
            tbl = accounts.groupby(by)["Balance"].agg(Accounts="count", Total="sum", Average="mean")
            show_table(tbl.sort_values("Total", ascending=False).style.format(
                {"Total": "{:,.0f}", "Average": "{:,.0f}"}))

    st.markdown("**Top 10 customers by total balance**")
    top10 = (accounts.groupby(["Customer_ID", "Segment", "Region"])["Balance"].sum()
             .sort_values(ascending=False).head(10).reset_index())
    fig = px.bar(top10, x="Balance", y="Customer_ID", orientation="h", color="Segment",
                 color_discrete_sequence=PALETTE, text_auto=".3s")
    fig.update_layout(yaxis=dict(categoryorder="total ascending", title=""), xaxis_title="Balance (RWF)",
                      title="Top 10 customers")
    show_chart(fig)


# ==================================================================
# TAB 5 - TRANSACTIONS
# ==================================================================
with tabs[4]:
    c = st.columns(4)
    kpi(c[0], "Transactions", f"{len(transactions):,}")
    kpi(c[1], "Total value", rwf(transactions["Amount"].sum()), "", NAVY)
    kpi(c[2], "Digital adoption", f"{digital_share:.1f}%", "of transactions", GREEN)
    kpi(c[3], "Digital customers", f"{transactions.loc[transactions['Digital'], 'Customer_ID'].nunique():,}",
        "used Mobile/Internet at least once", GOLD)
    st.write("")

    left, right = st.columns(2)
    with left:
        d = transactions.groupby("Transaction_Type")["Amount"].agg(["count", "sum"]).reset_index()
        fig = px.treemap(d, path=["Transaction_Type"], values="sum", color="count",
                         color_continuous_scale=["#CFE0F5", BK_BLUE, NAVY],
                         title="Transaction Value by Type (colour = number)")
        fig.update_traces(texttemplate="%{label}<br>RWF %{value:,.3s}")
        show_chart(fig)
    with right:
        d = transactions.groupby("Channel")["Amount"].agg(["count", "sum"]).reset_index()
        fig = px.scatter(d, x="count", y="sum", size="sum", color="Channel", text="Channel",
                         color_discrete_sequence=PALETTE, size_max=55,
                         title="Channels: number vs value of transactions")
        fig.update_traces(textposition="top center")
        fig.update_layout(showlegend=False, xaxis_title="Number", yaxis_title="Value (RWF)")
        show_chart(fig)

    left, right = st.columns(2)
    with left:
        d = (transactions.groupby("Segment")["Digital"].mean() * 100).sort_values().reset_index()
        fig = px.bar(d, x="Digital", y="Segment", orientation="h", text_auto=".1f",
                            color="Digital", color_continuous_scale=[BK_GOLD, BK_BLUE],
                     title="Digital Adoption by Segment (% Mobile + Internet)")
        fig.update_layout(coloraxis_showscale=False, xaxis_title="% of transactions", yaxis_title="")
        show_chart(fig)
    with right:
        d = transactions.groupby(["Month", "Digital"]).size().reset_index(name="Transactions")
        d["Digital"] = d["Digital"].map({True: "Digital", False: "Other channels"})
        fig = px.area(d, x="Month", y="Transactions", color="Digital",
                      color_discrete_map={"Digital": TEAL, "Other channels": "#B8C2D0"},
                      title="Monthly Transactions: Digital vs Other")
        fig.update_layout(legend_title="")
        show_chart(fig)

    if len(transactions):
        low = (transactions.groupby("Segment")["Digital"].mean() * 100).idxmin()
        insight(f"Only <b>{digital_share:.1f}%</b> of transactions are digital. <b>{low}</b> has the lowest "
                f"digital adoption – the best starting point for a digital campaign.")


# ==================================================================
# TAB 6 - LOANS
# ==================================================================
with tabs[5]:
    c = st.columns(5)
    kpi(c[0], "Loans", f"{len(loans):,}", f"{loans['Customer_ID'].nunique():,} borrowers")
    kpi(c[1], "Disbursed", rwf(total_loans), f"Avg {rwf(loans['Loan_Amount'].mean() if len(loans) else 0)}", NAVY)
    kpi(c[2], "Outstanding", rwf(total_outstanding), "", GOLD)
    kpi(c[3], "NPL ratio", f"{npl_ratio:.1f}%", rwf(npl_out), RED)
    kpi(c[4], "At-risk (Watch + NPL)", f"{at_risk_ratio:.1f}%", rwf(npl_out + watch_out), RED)
    st.write("")

    left, right = st.columns(2)
    with left:
        fig = go.Figure(go.Indicator(
            mode="gauge+number", value=npl_ratio, number={"suffix": "%", "valueformat": ".1f"},
            title={"text": "NPL Ratio (% of outstanding)"},
            gauge={"axis": {"range": [0, 20]}, "bar": {"color": NAVY},
                   "steps": [{"range": [0, 5], "color": "#D8F0E1"},
                             {"range": [5, 10], "color": "#FCE9C8"},
                             {"range": [10, 20], "color": "#F7D4D4"}],
                   "threshold": {"line": {"color": RED, "width": 4}, "value": 5}}))
        fig.update_layout(height=330)
        show_chart(fig)
        st.caption("Green < 5% · Amber 5–10% · Red > 10%. The red line marks a common 5% tolerance level.")
    with right:
        seg_loans = loans.groupby("Segment").agg(Loans=("Loan_ID", "count"),
                                                 Outstanding=("Outstanding_Balance", "sum"))
        seg_npl = loans[loans["Loan_Status"] == "Non-Performing"].groupby("Segment")["Outstanding_Balance"].sum()
        seg_loans["NPL_%"] = (seg_npl / seg_loans["Outstanding"] * 100).fillna(0).round(1)
        d = seg_loans.sort_values("NPL_%").reset_index()
        fig = px.bar(d, x="NPL_%", y="Segment", orientation="h", text_auto=".1f",
                     color="NPL_%", color_continuous_scale=["#F2C4C4", RED], title="NPL Ratio by Segment (%)")
        fig.add_vline(x=npl_ratio, line_dash="dash", line_color=NAVY,
                      annotation_text=f"Overall {npl_ratio:.1f}%",
                      annotation_position="bottom right")
        fig.update_layout(coloraxis_showscale=False, xaxis_title="% non-performing", yaxis_title="")
        show_chart(fig)

    view = st.radio("Break loans down by", ["Loan_Type", "Segment", "Region"], horizontal=True)
    d = loans.groupby([view, "Loan_Status"])["Outstanding_Balance"].sum().reset_index()
    d["Outstanding_Balance"] = d["Outstanding_Balance"] / 1e6
    fig = px.bar(d, x=view, y="Outstanding_Balance", color="Loan_Status",
                 color_discrete_map=STATUS_COLORS,
                 category_orders={"Loan_Status": ["Performing", "Watch", "Non-Performing"]},
                 title=f"Outstanding Balance by {view.replace('_', ' ')} and Status (RWF millions)")
    fig.update_layout(xaxis={"categoryorder": "total descending", "title": ""}, yaxis_title="RWF millions")
    show_chart(fig)

    tbl = loans.groupby(view).agg(Loans=("Loan_ID", "count"), Disbursed=("Loan_Amount", "sum"),
                                  Outstanding=("Outstanding_Balance", "sum"))
    show_table(tbl.sort_values("Disbursed", ascending=False).style.format(
        {"Disbursed": "{:,.0f}", "Outstanding": "{:,.0f}"}))


# ==================================================================
# TAB 7 - SEGMENT COMPARISON
# ==================================================================
with tabs[6]:
    st.subheader("All segments in one table")
    seg_loans_all = loans.groupby("Segment")["Outstanding_Balance"].sum()
    seg_npl_all = loans[loans["Loan_Status"] == "Non-Performing"].groupby("Segment")["Outstanding_Balance"].sum()

    summary = pd.DataFrame()
    summary["Customers"] = customers["Segment"].value_counts()
    summary["Total_Balance"] = accounts.groupby("Segment")["Balance"].sum()
    summary["Avg_Balance_per_Customer"] = summary["Total_Balance"] / summary["Customers"]
    summary["Transactions"] = transactions.groupby("Segment")["Transaction_ID"].count()
    summary["Txn_Value"] = transactions.groupby("Segment")["Amount"].sum()
    summary["Digital_%"] = transactions.groupby("Segment")["Digital"].mean() * 100
    summary["Borrowers"] = loans.groupby("Segment")["Customer_ID"].nunique()
    summary["Loan_Outstanding"] = seg_loans_all
    summary["NPL_%"] = (seg_npl_all / seg_loans_all * 100).fillna(0)
    summary = summary.fillna(0)

    show_table(summary.style.format({
        "Customers": "{:,.0f}", "Total_Balance": "{:,.0f}", "Avg_Balance_per_Customer": "{:,.0f}",
        "Transactions": "{:,.0f}", "Txn_Value": "{:,.0f}", "Digital_%": "{:.1f}",
        "Borrowers": "{:,.0f}", "Loan_Outstanding": "{:,.0f}", "NPL_%": "{:.1f}",
    }).background_gradient(cmap="Blues", subset=["Total_Balance", "Avg_Balance_per_Customer"])
      .background_gradient(cmap="Reds", subset=["NPL_%"]))

    d = summary.reset_index(names="Segment")
    fig = px.scatter(d, x="Customers", y="Avg_Balance_per_Customer", size="Total_Balance",
                     color="Segment", text="Segment", size_max=70, color_discrete_sequence=PALETTE,
                     hover_data={"NPL_%": ":.1f", "Digital_%": ":.1f"},
                     title="Segment map: size of base vs value per customer (bubble = total deposits)")
    fig.update_traces(textposition="top center")
    fig.update_layout(showlegend=False, yaxis_title="Avg balance per customer (RWF)")
    show_chart(fig)

    # Radar: each measure scaled 0-100 so segments can be compared on one chart
    measures = ["Customers", "Total_Balance", "Avg_Balance_per_Customer", "Txn_Value", "Digital_%", "Loan_Outstanding"]
    scaled = summary[measures] / summary[measures].max().replace(0, 1) * 100
    fig = go.Figure()
    for i, (seg, row) in enumerate(scaled.iterrows()):
        fig.add_trace(go.Scatterpolar(r=list(row) + [row.iloc[0]], theta=measures + [measures[0]],
                                      name=seg, fill="toself", opacity=.55,
                                      line_color=PALETTE[i % len(PALETTE)]))
    fig.update_layout(title="Segment profile (each measure scaled 0–100, best = 100)",
                      polar=dict(radialaxis=dict(range=[0, 100])), height=520)
    show_chart(fig)

    st.download_button("Download segment summary (CSV)", summary.round(1).to_csv().encode("utf-8"),
                       "Segment_Summary.csv", "text/csv")


# ==================================================================
# TAB 8 - INSIGHTS & RECOMMENDATIONS (numbers update with the filters)
# ==================================================================
with tabs[7]:
    st.subheader("Key insights and recommendations")
    cust_pct = customers["Segment"].value_counts(normalize=True) * 100
    bal_pct = accounts.groupby("Segment")["Balance"].sum() / total_balance * 100 if total_balance else cust_pct * 0

    def pct(series, key):
        return f"{series.get(key, 0):.1f}%"

    seg_npl_pct = summary["NPL_%"].sort_values(ascending=False)
    worst = ", ".join(seg_npl_pct.head(2).index)
    n_watch = (loans["Loan_Status"] == "Watch").sum()
    n_npl = (loans["Loan_Status"] == "Non-Performing").sum()
    dormant = (accounts["Account_Status"] == "Dormant").sum()
    fd_share = (accounts.loc[accounts["Account_Type"] == "Fixed Deposit", "Balance"].sum()
                / total_balance * 100) if total_balance else 0

    cards = [
        ("1. Few customers hold most deposits",
         f"Corporate = {pct(cust_pct, 'Corporate')} of customers but {pct(bal_pct, 'Corporate')} of balances; "
         f"Institutional = {pct(cust_pct, 'Institutional Banking')} of customers but "
         f"{pct(bal_pct, 'Institutional Banking')} of balances.",
         "Assign relationship managers and retention offers to top Corporate/Institutional clients.", ""),
        ("2. Retail is big in numbers but small in value",
         f"Retail = {pct(cust_pct, 'Retail')} of customers but only {pct(bal_pct, 'Retail')} of balances.",
         "Grow Retail savings: goal-based savings, salary accounts, mobile savings products.", ""),
        ("3. Digital adoption is still low",
         f"Mobile + Internet = {digital_share:.1f}% of transactions; the rest go through Branch/ATM/POS/Agent.",
         "Lower fees on Mobile/Internet and run education campaigns, starting with the lowest-adoption segment.", "warn"),
        ("4. Riskiest loan segments",
         f"Highest NPL ratios: {worst} (overall {npl_ratio:.1f}%).",
         "Stronger credit scoring and repayment plans matched to seasonal income (e.g. harvest).", "danger"),
        ("5. Many loans need watching",
         f"{n_npl} Non-Performing + {n_watch} Watch loans; Watch + NPL = {at_risk_ratio:.1f}% of outstanding.",
         "Early-warning follow-up on Watch loans (calls, restructuring) before they default.", "danger"),
        ("6. Unused accounts & low fixed deposits",
         f"{dormant} Dormant accounts; Fixed Deposits hold only {fd_share:.1f}% of balances.",
         "Run a reactivation campaign and offer better fixed-deposit rates.", "warn"),
    ]
    col_a, col_b = st.columns(2)
    for i, (title, evidence, rec, kind) in enumerate(cards):
        with (col_a if i % 2 == 0 else col_b):
            st.markdown(f'<div class="insight {kind}"><b>{title}</b><br>{evidence}<br>'
                        f'<i>{rec}</i></div>', unsafe_allow_html=True)

    st.markdown("#### Download cleaned data")
    c = st.columns(4)
    for col, (name, df) in zip(c, [("Customers", customers), ("Accounts", accounts),
                                   ("Transactions", transactions), ("Loans", loans)]):
        col.download_button(f"{name}", df.to_csv(index=False).encode("utf-8"),
                            f"Clean_{name}.csv", "text/csv", key=f"dl_{name}")
