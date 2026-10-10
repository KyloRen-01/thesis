import pandas as pd

ref_cities = pd.read_csv("data/lookup/refcitymun.csv")
ref_provs  = pd.read_csv("data/lookup/refprovince.csv")
ref_regs   = pd.read_csv("data/lookup/refregion.csv")

# combine
PH_LOCATIONS = set(
    pd.concat([ref_cities["citymunDesc"], ref_provs["provDesc"], ref_regs["regDesc"]],
              ignore_index=True).str.lower().str.strip().unique()
)
PH_LOCATIONS.update(["philippines", "pilipinas", "ph"])

def mentions_ph_location(text: str) -> bool:
    if not isinstance(text, str):
        return False
    return any(loc in text.lower() for loc in PH_LOCATIONS)
