def format_columns(df):
    rename_map = {
        "text": "raw_text",
        "event_time_primary": "datetime",
        "location_matched_json": "location",
        "post_url": "url",
    }

    df = df.rename(columns=rename_map)

    # Only include columns that exist
    cols = [c for c in [
        "source",
        "page_source",
        "text_content",
        "datetime",
        "location",
        "disaster_type",
        "url"
    ] if c in df.columns]

    return df[cols]
