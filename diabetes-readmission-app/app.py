"""
Diabetes Readmission Explorer
Streamlit app for BAN 601 - Project 1

Run with:
    streamlit run app.py
"""

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from data_prep import (A1C_ORDER, AGE_ORDER, DX_ORDER, clean_data,
                       first_visit_only, load_data)

st.set_page_config(page_title="Diabetes Readmission Explorer",
                   layout="wide")

# Chart colors (kept the same across every chart so a color always means
# the same thing: orange = not tested, blue = tested)
BLUE = "#2a78d6"
ORANGE = "#eb6834"
VIOLET = "#4a3aa7"
TEXT = "#52514e"
GRID = "#e4e3df"

MIN_GROUP_SIZE = 30  # hide bars based on fewer patients than this


# ------------------------------------------------------------------
# Load data (cached so it only runs once)
# ------------------------------------------------------------------
@st.cache_data
def get_data():
    raw = load_data()
    return clean_data(raw)


df_all = get_data()


# ------------------------------------------------------------------
# Helper functions
# ------------------------------------------------------------------
def readmit_rate_table(data, group_col, order):
    """Patients and 30-day readmission rate (%) for each group."""
    table = data.groupby(group_col)["readmit_30"].agg(["size", "mean"])
    table.columns = ["patients", "rate"]
    table["rate"] = table["rate"] * 100
    table = table.reindex([g for g in order if g in table.index])
    return table


def style_axes(ax, ylabel):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=TEXT, length=0)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_ylabel(ylabel, color=TEXT)


def label_bars(ax, bars):
    top = ax.get_ylim()[1]
    tallest = max([b.get_height() for b in bars if not pd.isna(b.get_height())] + [0])
    ax.set_ylim(0, max(top, tallest * 1.15))
    for bar in bars:
        height = bar.get_height()
        if pd.isna(height):
            continue
        ax.annotate(f"{height:.1f}%",
                    (bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=9, color=TEXT)


# ------------------------------------------------------------------
# Header
# ------------------------------------------------------------------
st.title("Diabetes Readmission Explorer")
st.markdown(
    "**Should this patient get an HbA1c test?** "
    "Diabetic patients admitted to the hospital for any reason are often "
    "readmitted within 30 days, and readmissions are costly for hospitals. "
    "Only about 1 in 5 patients in this data had an HbA1c (blood sugar) test. "
    "Use this app to see which patients are at higher risk of a 30-day "
    "readmission and whether HbA1c testing is linked to fewer readmissions."
)
st.caption(
    "Data: UCI Diabetes 130-US Hospitals, 1999-2008. "
    "Patients who died or were sent to hospice are excluded. "
    "These are associations, not proof that testing causes fewer readmissions."
)

# ------------------------------------------------------------------
# Sidebar controls
# ------------------------------------------------------------------
st.sidebar.header("Filter patients")

one_per_patient = st.sidebar.checkbox(
    "Count each patient once (first visit only)", value=True,
    help="Some patients were admitted many times. Checking this keeps only "
         "each patient's first hospital stay so frequent visitors don't "
         "count more than once.")

a1c_choice = st.sidebar.multiselect(
    "HbA1c test result", A1C_ORDER, default=A1C_ORDER,
    help="'Not tested' means no HbA1c test was done during the stay.")

age_choice = st.sidebar.multiselect(
    "Age group", AGE_ORDER, default=AGE_ORDER)

dx_choice = st.sidebar.multiselect(
    "Primary diagnosis (reason for the stay)", DX_ORDER, default=DX_ORDER)

inpatient_range = st.sidebar.slider(
    "Hospital stays in the prior year", min_value=0, max_value=5,
    value=(0, 5), help="5 means 5 or more stays.")

med_choice = st.sidebar.radio(
    "Diabetes medication changed during stay?",
    ["All patients", "Changed", "Not changed"])

# Apply the filters
df = df_all.copy()
if one_per_patient:
    df = first_visit_only(df)

df = df[df["a1c_status"].isin(a1c_choice)]
df = df[df["age_group"].isin(age_choice)]
df = df[df["primary_dx"].isin(dx_choice)]
df = df[(df["prior_inpatient"] >= inpatient_range[0]) &
        (df["prior_inpatient"] <= inpatient_range[1])]
if med_choice != "All patients":
    df = df[df["med_change"] == med_choice]

if len(df) == 0:
    st.warning("No patients match these filters. Try selecting more options "
               "in the sidebar.")
    st.stop()

# ------------------------------------------------------------------
# Key numbers
# ------------------------------------------------------------------
tested = df[df["a1c_tested"] == "Tested"]
not_tested = df[df["a1c_tested"] == "Not tested"]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Patients in selection", f"{len(df):,}")
col2.metric("30-day readmission rate", f"{df['readmit_30'].mean() * 100:.1f}%")
col3.metric("Had an HbA1c test", f"{len(tested) / len(df) * 100:.1f}%")
if len(tested) > 0 and len(not_tested) > 0:
    gap = (not_tested["readmit_30"].mean() - tested["readmit_30"].mean()) * 100
    col4.metric("Gap: untested vs. tested",
                f"{gap:+.1f} pts",
                help="Positive means untested patients came back more often.")
else:
    col4.metric("Gap: untested vs. tested", "n/a",
                help="Select both tested and untested patients to compare.")

st.divider()

# ------------------------------------------------------------------
# Chart 1 - HbA1c result vs readmission
# ------------------------------------------------------------------
left, right = st.columns(2)

with left:
    st.subheader("1. Are tested patients readmitted less often?")
    st.caption("Share of patients readmitted within 30 days, by HbA1c result.")

    a1c_table = readmit_rate_table(df, "a1c_status", A1C_ORDER)
    a1c_table = a1c_table[a1c_table["patients"] >= MIN_GROUP_SIZE]

    fig, ax = plt.subplots(figsize=(6, 4))
    colors = []
    for status in a1c_table.index:
        if status == "Not tested":
            colors.append(ORANGE)
        else:
            colors.append(BLUE)
    bars = ax.bar(a1c_table.index, a1c_table["rate"], color=colors, width=0.6)
    label_bars(ax, bars)
    style_axes(ax, "Readmitted within 30 days (%)")
    ax.tick_params(axis="x", labelsize=9)
    st.pyplot(fig)
    plt.close(fig)

    st.caption("Orange = not tested, blue = tested. "
               "Bars with fewer than 30 patients are hidden.")

# ------------------------------------------------------------------
# Chart 2 - Prior inpatient stays vs readmission
# ------------------------------------------------------------------
with right:
    st.subheader("2. Do frequent visitors come back more?")
    st.caption("Share readmitted within 30 days, by number of hospital stays "
               "in the year before this one.")

    visit_order = [0, 1, 2, 3, 4, 5]
    visit_table = readmit_rate_table(df, "prior_inpatient", visit_order)
    visit_table = visit_table[visit_table["patients"] >= MIN_GROUP_SIZE]
    visit_labels = []
    for v in visit_table.index:
        if v == 5:
            visit_labels.append("5+")
        else:
            visit_labels.append(str(v))

    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(visit_labels, visit_table["rate"], color=VIOLET, width=0.6)
    label_bars(ax, bars)
    style_axes(ax, "Readmitted within 30 days (%)")
    ax.set_xlabel("Hospital stays in the prior year", color=TEXT)
    st.pyplot(fig)
    plt.close(fig)

    st.caption("A steep rise here means prior stays are a strong warning sign.")

# ------------------------------------------------------------------
# Chart 3 - Tested vs not tested, by diagnosis
# ------------------------------------------------------------------
st.subheader("3. For which diagnoses is testing linked to fewer readmissions?")
st.caption("30-day readmission rate for tested vs. untested patients, split "
           "by the main reason for the hospital stay.")

by_dx = df.groupby(["primary_dx", "a1c_tested"])["readmit_30"].agg(["size", "mean"])
by_dx = by_dx.reset_index()
by_dx = by_dx[by_dx["size"] >= MIN_GROUP_SIZE]
by_dx["rate"] = by_dx["mean"] * 100

rates = by_dx.pivot(index="primary_dx", columns="a1c_tested", values="rate")
rates = rates.reindex([d for d in DX_ORDER if d in rates.index])

if len(rates) == 0:
    st.info("Not enough patients in this selection to compare diagnoses.")
else:
    fig, ax = plt.subplots(figsize=(12, 4))
    positions = range(len(rates))
    width = 0.38
    if "Not tested" in rates.columns:
        bars = ax.bar([p - width / 2 for p in positions], rates["Not tested"],
                      width=width, color=ORANGE, label="Not tested")
        label_bars(ax, bars)
    if "Tested" in rates.columns:
        bars = ax.bar([p + width / 2 for p in positions], rates["Tested"],
                      width=width, color=BLUE, label="Tested")
        label_bars(ax, bars)
    ax.set_xticks(list(positions))
    ax.set_xticklabels(rates.index)
    style_axes(ax, "Readmitted within 30 days (%)")
    ax.legend(frameon=False, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2)
    st.pyplot(fig)
    plt.close(fig)

    st.caption("Look for diagnoses where the blue bar is clearly lower than "
               "the orange bar. Groups with fewer than 30 patients are hidden.")

st.divider()

# ------------------------------------------------------------------
# Break-even check
# ------------------------------------------------------------------
st.subheader("Does testing make economic sense for this group?")
st.markdown(
    "Enter your hospital's own costs. The app compares the cost of one test "
    "with the readmission cost that *might* be avoided, based on the "
    "readmission gap for the patients currently selected."
)

cost_col1, cost_col2 = st.columns(2)
test_cost = cost_col1.number_input(
    "Cost of one HbA1c test ($)", min_value=0, value=50, step=5,
    help="Placeholder value. Replace with your hospital's actual cost.")
readmit_cost = cost_col2.number_input(
    "Cost of one readmission ($)", min_value=0, value=15000, step=500,
    help="Placeholder value. Replace with your hospital's actual cost.")

if len(tested) >= MIN_GROUP_SIZE and len(not_tested) >= MIN_GROUP_SIZE:
    gap_share = not_tested["readmit_30"].mean() - tested["readmit_30"].mean()
    savings_per_test = gap_share * readmit_cost
    if gap_share <= 0:
        st.info("In this selection, tested patients were **not** readmitted "
                "less often, so the data gives no cost case for testing here.")
    elif savings_per_test >= test_cost:
        st.success(
            f"Untested patients were readmitted {gap_share * 100:.1f} "
            f"percentage points more often. At these costs that is about "
            f"**\\${savings_per_test:,.0f} of readmission cost per patient**, "
            f"more than the \\${test_cost:,} test.")
    else:
        st.warning(
            f"The readmission gap ({gap_share * 100:.1f} points) is worth about "
            f"\\${savings_per_test:,.0f} per patient, less than the "
            f"\\${test_cost:,} test.")
    st.caption("This is a rough screening check. The gap is an association: "
               "tested patients may differ in other ways, so testing alone "
               "may not produce the full saving.")
else:
    st.info("Select both tested and untested patients (at least 30 of each) "
            "to run the break-even check.")

# ------------------------------------------------------------------
# Data table and notes
# ------------------------------------------------------------------
with st.expander("View the filtered data"):
    show_cols = ["age_group", "gender", "race", "primary_dx", "a1c_status",
                 "prior_inpatient", "number_emergency", "time_in_hospital",
                 "med_change", "insulin", "readmitted"]
    st.dataframe(df[show_cols].head(500), width="stretch")
    st.caption(f"Showing the first 500 of {len(df):,} rows.")
    st.download_button("Download filtered data (CSV)",
                       df[show_cols].to_csv(index=False),
                       file_name="filtered_patients.csv", mime="text/csv")

with st.expander("About the data and definitions"):
    st.markdown(
        """
- **Source:** UCI Machine Learning Repository, *Diabetes 130-US Hospitals
  for Years 1999-2008* (101,766 hospital stays of diabetic patients).
- **30-day readmission:** the `readmitted` column equals `<30`. Readmissions
  after 30 days and no readmission both count as "not readmitted".
- **HbA1c test:** `A1Cresult`. "None" in the file means no test was done.
  Normal is under 7%, Elevated is 7-8%, High is over 8%.
- **Primary diagnosis:** ICD-9 code in `diag_1`, grouped into Circulatory
  (390-459, 785), Respiratory (460-519, 786), Digestive (520-579, 787),
  Diabetes (250.xx), Injury (800-999), Musculoskeletal (710-739),
  Genitourinary (580-629, 788), and Other.
- **Excluded:** stays that ended in death or hospice, and 3 rows with an
  invalid gender.
        """
    )
