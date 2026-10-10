"""Configuration for the flood-focused Facebook collector."""


FACEBOOK = {
    "users": [ #facebook pages
        "atenews",
        "BFPRHQ11",
        "civildefensedavao",
        "DavaoDevUpdates",  
        "davaocitydrmmc",
        "DavaoDRRMO",
        "davaocitydisasterradio",
        "mprsdcdo",
        "NIASNewsChannelPH",
        "PIADavaoRegion",  
        "sunstardavaonews",
        "stormchasersPH",
        "weather.davao",
        
    ],
    "search_queries": [ #hashtags in facebook 
        "BahaPH",
        "FloodAlert",
        "FloodingPhilippines",
        "FlashFlood",
        "StreetFloodAlert",
        "FloodWarning",
        "BahaDavao",
        "FloodDavao",
        "Pagbaha",

    ],
}


# Original flood-only keyword set.
KEYWORDS = [ #keywords to search for in facebook posts
    "flood",
    "flooding",
    "flash flood",
    "floodwater",
    "river overflow",
    "street flood",
    "urban flood",
    "flood alert",
    "flood warning",
    "baha",
    "pagbaha",
    "nabaha",
    "nabahaan",
    "binaha",
    "binabaha",
    "lunop",
    "paglunop",
    "#flood",
    "#floodalert",
    "#bahaph",
    "#streetfloodalert",

]


# Fallback location terms keep the scraper usable before Philippine reference
# CSVs are added to this project.
PH_LOCATIONS = [
    "philippines",
    "pilipinas",
    "davao",
    "davao city",
    "tagum",
    "panabo",
    "samal",
    "mati",
    "digos",
    "general santos",
    "gensan",
    "cagayan de oro",
    "cebu",
    "manila",
    "quezon city",
    "metro manila",
]
