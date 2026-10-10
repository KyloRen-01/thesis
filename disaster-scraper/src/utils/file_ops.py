import os
import pandas as pd


def ensure_dir_exists(path: str):
    """Create directory if it doesn't exist."""
    os.makedirs(os.path.dirname(path), exist_ok=True)


def save_to_csv(df: pd.DataFrame, path: str, encoding: str = "utf-8-sig"):
    """
    Save a DataFrame to CSV safely with directory creation and basic logging.
    """
    ensure_dir_exists(path)
    df.to_csv(path, index=False, encoding=encoding)
    print(f"💾 Saved CSV → {path} ({len(df)} rows)")


def load_csv(path: str, encoding: str = "utf-8-sig") -> pd.DataFrame:
    """
    Load a CSV safely, with error handling and informative logs.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"❌ CSV not found: {path}")
    df = pd.read_csv(path, encoding=encoding)
    print(f"📂 Loaded CSV ← {path} ({len(df)} rows)")
    return df


def list_csvs(folder: str) -> list[str]:
    """
    List all CSV files in a given folder (non-recursive).
    """
    if not os.path.exists(folder):
        print(f"⚠️ Folder not found: {folder}")
        return []
    return [f for f in os.listdir(folder) if f.endswith(".csv")]
