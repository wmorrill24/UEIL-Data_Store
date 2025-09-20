import pandas as pd


def format_search_results(df):
    """Formats a DataFrame of search results for better display."""
    if df.empty:
        return pd.DataFrame()

    # Reorder columns for better readability
    desired_order = [
        "file_name",
        "research_project_id",
        "author",
        "file_type",
        "experiment_type",
        "date_conducted",
        "size_bytes",
        "custom_tags",
        "upload_timestamp",
        "file_id",
        "minio_object_path",
    ]
    # Filter out columns that don't exist in the dataframe
    existing_columns = [col for col in desired_order if col in df.columns]

    # Create a copy to avoid SettingWithCopyWarning
    df = df[existing_columns].copy()

    # Format dates and sizes
    if "date_conducted" in df.columns:
        df["date_conducted"] = pd.to_datetime(df["date_conducted"]).dt.strftime(
            "%Y-%m-%d"
        )
    if "upload_timestamp" in df.columns:
        df["upload_timestamp"] = pd.to_datetime(df["upload_timestamp"]).dt.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    # Convert size_bytes to a human-readable format
    if "size_bytes" in df.columns:
        df["size_bytes"] = df["size_bytes"].fillna(0).astype(int)
        # Rename column for clarity in display
        df.rename(columns={"size_bytes": "size_in_bytes"}, inplace=True)

    return df
