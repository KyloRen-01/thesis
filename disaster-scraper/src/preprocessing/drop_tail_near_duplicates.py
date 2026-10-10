from rapidfuzz import fuzz
import pandas as pd
from tqdm import tqdm

def drop_tail_near_duplicates(df, text_col="text_content",
                              prefix_len=300,
                              prefix_threshold=97,
                              full_threshold=90):
    """
    Strict version:
    Removes posts that share the same main body (prefix) but differ only by added
    comments or trailing sentences. Keeps the shortest 'clean' base version.

    Args:
        df: DataFrame
        text_col: column containing text
        prefix_len: how much of the start to compare
        prefix_threshold: prefix similarity % to consider same update
        full_threshold: overall similarity % to consider near-duplicate
    """
    texts = df[text_col].fillna("").astype(str).tolist()
    keep_indices = []
    seen = []  # (prefix, text, index)

    for i, t in tqdm(enumerate(texts), total=len(texts),
                     desc="🧹 Removing tail/comment duplicates"):
        clean_text = " ".join(t.split()).strip().lower()
        prefix = clean_text[:prefix_len]

        duplicate_group = None
        for (seen_prefix, seen_text, seen_idx) in seen:
            # 1️⃣ If prefixes are very similar
            if fuzz.ratio(prefix, seen_prefix) >= prefix_threshold:
                # 2️⃣ Check full-text similarity (overall body same)
                if fuzz.ratio(clean_text, seen_text) >= full_threshold:
                    duplicate_group = (seen_prefix, seen_text, seen_idx)
                    break

        if duplicate_group:
            # keep the shorter/cleaner one
            if len(clean_text) < len(duplicate_group[1]):
                # replace longer version
                seen.remove(duplicate_group)
                seen.append((prefix, clean_text, i))
                keep_indices.remove(duplicate_group[2])
                keep_indices.append(i)
            # otherwise, ignore (keep the shorter one already stored)
        else:
            seen.append((prefix, clean_text, i))
            keep_indices.append(i)

    cleaned_df = df.iloc[keep_indices].reset_index(drop=True)
    print(f"🧹 Removed {len(df) - len(cleaned_df)} near/tail duplicates "
          f"(kept shortest base version, prefix≥{prefix_threshold}%, full≥{full_threshold}%)")
    return cleaned_df
