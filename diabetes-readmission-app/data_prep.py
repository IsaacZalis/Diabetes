"""
Data preparation for the Diabetes Readmission Explorer.

Loads the UCI "Diabetes 130-US Hospitals (1999-2008)" file, keeps the columns
our team selected, and adds a few easy-to-read columns the app uses:

    readmit_30      1 if the patient came back within 30 days, else 0
    a1c_status      readable HbA1c result ("Not tested", "Normal", ...)
    a1c_tested      "Tested" or "Not tested"
    age_group       "70-79" instead of "[70-80)"
    primary_dx      diagnosis group for diag_1 (Circulatory, Diabetes, ...)
    prior_inpatient hospital admissions in the year before, capped at "5+"
    med_change      "Changed" or "Not changed"

Run this file directly to print a quick data check:
    python data_prep.py
"""

import pandas as pd

DATA_PATH = "data/diabetic_data.csv"

# Columns our team decided to use (see README "Variables")
COLUMNS = [
    "encounter_id", "patient_nbr",
    # demographics
    "race", "gender", "age",
    # prior utilization (year before this stay)
    "number_outpatient", "number_emergency", "number_inpatient",
    # clinical severity (this stay)
    "time_in_hospital", "num_lab_procedures", "num_procedures",
    "number_diagnoses", "diag_1", "diag_2", "diag_3",
    # lab test
    "A1Cresult",
    # discharge / admission context
    "discharge_disposition_id", "admission_type_id", "admission_source_id",
    # treatment
    "insulin", "change", "diabetesMed",
    # target
    "readmitted",
]

# discharge_disposition_id codes for patients who died or went to hospice.
# They cannot be readmitted, so we leave them out (see IDS_mapping.csv).
EXPIRED_OR_HOSPICE = [11, 13, 14, 19, 20, 21]

A1C_LABELS = {
    "None": "Not tested",
    "Norm": "Normal (<7%)",
    ">7": "Elevated (7-8%)",
    ">8": "High (>8%)",
}
A1C_ORDER = ["Not tested", "Normal (<7%)", "Elevated (7-8%)", "High (>8%)"]

AGE_ORDER = ["0-9", "10-19", "20-29", "30-39", "40-49",
             "50-59", "60-69", "70-79", "80-89", "90-99"]

DX_ORDER = ["Circulatory", "Respiratory", "Digestive", "Diabetes", "Injury",
            "Musculoskeletal", "Genitourinary", "Other"]


def load_data(filepath=DATA_PATH):
    # The file marks missing values with "?".
    # keep_default_na=False stops pandas from turning the text "None"
    # (which means "HbA1c test not performed") into a missing value.
    df = pd.read_csv(filepath, na_values="?", keep_default_na=False,
                     low_memory=False)
    return df


def check_missing_values(df):
    missing_counts = df.isna().sum()
    missing_counts = missing_counts[missing_counts > 0]
    missing_counts = missing_counts.sort_values(ascending=False)
    return missing_counts


def diagnosis_group(code):
    """Turn an ICD-9 code like '428' or '250.83' into a readable group."""
    if pd.isna(code):
        return "Other"
    code = str(code).strip()
    # V and E codes are supplementary codes, not a disease group
    if code.startswith("V") or code.startswith("E"):
        return "Other"
    number = float(code)
    if code.startswith("250"):
        return "Diabetes"
    if (390 <= number <= 459) or number == 785:
        return "Circulatory"
    if (460 <= number <= 519) or number == 786:
        return "Respiratory"
    if (520 <= number <= 579) or number == 787:
        return "Digestive"
    if 800 <= number <= 999:
        return "Injury"
    if 710 <= number <= 739:
        return "Musculoskeletal"
    if (580 <= number <= 629) or number == 788:
        return "Genitourinary"
    return "Other"


def age_label(age_text):
    """'[70-80)' -> '70-79'"""
    age_text = age_text.replace("[", "").replace(")", "")
    low, high = age_text.split("-")
    return low + "-" + str(int(high) - 1)


def clean_data(df):
    df = df[COLUMNS].copy()

    # trim whitespace in text columns
    for col in df.columns:
        if not pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].str.strip()

    # remove patients who died or went to hospice (cannot be readmitted)
    df = df[~df["discharge_disposition_id"].isin(EXPIRED_OR_HOSPICE)]

    # remove the 3 rows with an invalid gender
    df = df[df["gender"] != "Unknown/Invalid"]

    # target: readmitted within 30 days (1) vs. not (0)
    df["readmit_30"] = (df["readmitted"] == "<30").astype(int)

    # HbA1c
    df["a1c_status"] = df["A1Cresult"].map(A1C_LABELS)
    df["a1c_tested"] = "Tested"
    df.loc[df["a1c_status"] == "Not tested", "a1c_tested"] = "Not tested"

    # readable age groups
    df["age_group"] = df["age"].apply(age_label)

    # primary diagnosis group
    df["primary_dx"] = df["diag_1"].apply(diagnosis_group)

    # prior inpatient visits, with 5 or more grouped together
    df["prior_inpatient"] = df["number_inpatient"].clip(upper=5)

    # medication change
    df["med_change"] = "Not changed"
    df.loc[df["change"] == "Ch", "med_change"] = "Changed"

    df = df.reset_index(drop=True)
    return df


def first_visit_only(df):
    """Keep one row per patient (their earliest encounter)."""
    df = df.sort_values("encounter_id")
    df = df.drop_duplicates(subset="patient_nbr", keep="first")
    return df


if __name__ == "__main__":
    raw = load_data()
    print("Raw shape:", raw.shape)
    print("\nMissing values in raw file:")
    print(check_missing_values(raw))
    print("\nDuplicate encounter IDs:", raw["encounter_id"].duplicated().sum())
    print("Patients with more than one encounter:",
          raw["patient_nbr"].duplicated().sum())

    clean = clean_data(raw)
    print("\nClean shape:", clean.shape)
    print("30-day readmission rate:", round(clean["readmit_30"].mean() * 100, 1), "%")
    print("HbA1c tested:", round((clean["a1c_tested"] == "Tested").mean() * 100, 1), "%")

    one_per_patient = first_visit_only(clean)
    print("\nFirst visit per patient:", one_per_patient.shape)
    print("HbA1c tested:",
          round((one_per_patient["a1c_tested"] == "Tested").mean() * 100, 1), "%")
