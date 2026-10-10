import pandas as pd
from preprocessing.clean_text import clean_text
from preprocessing.extract_pagesource import extract_pagesource
from preprocessing.format_columns import format_columns
from preprocessing.location_filter import mentions_ph_location
from preprocessing.drop_tail_near_duplicates import drop_tail_near_duplicates


def run_cleaning_pipeline(input_data):
    """
    Runs text cleaning, filtering, and column formatting on merged raw or NER data.
    Accepts either a CSV path (string) or a DataFrame.
    """
    if isinstance(input_data, str):
        df = pd.read_csv(input_data)
    else:
        df = input_data.copy()

    df["text_content"] = df.get("text", df.get("text_content", "")).fillna("").apply(clean_text)

    before = len(df)
    df = df[df["text_content"].str.strip().astype(bool)].copy()
    print(f"Dropped empty rows: {before - len(df)}")

    before = len(df)
    df = df.drop_duplicates(subset=["text_content"], keep="first").copy()
    print(f"Dropped exact duplicates: {before - len(df)}")

    before = len(df)
    df = drop_tail_near_duplicates(df, "text_content")
    print(f"Dropped near-duplicates (same prefix): {before - len(df)}")

    df = df[df["text_content"].apply(mentions_ph_location)].copy()
    print(f"Dropped non-PH context posts: {before - len(df)}")

    df["page_source"] = df["post_url"].apply(extract_pagesource)
    print(f"Extracted page source..")

    df = format_columns(df)
    print("Formatted columns...")


    print("✅ Cleaning complete. Returning DataFrame.")
    return df
