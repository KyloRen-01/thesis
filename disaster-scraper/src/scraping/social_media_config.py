# Facebook user and search query scraper configuration
FACEBOOK = {
    "users": [
        "abscbnNEWS","atenews","BFPRHQ11", "civildefensedavao", "davaocitydrmmc", 
        "DavaoDRRMO", "davaocitydisasterradio", "DZMMTeleradyo.MSPC"
        "gmanews", "inquirerdotnet", 
        "manilabulletin", "mprsdcdo", "mindanews"
        "mrpsd.com.ph", "NDRRMC", "pagasa.dost.gov.ph",
        "PhilstarNews", "PHIVOLCS", "PIAgovernment",
        "rapplerdotcom", "sunstardavaonews", "sunstarphilippines",
        "stormchasersPH", "UNTVNewsRescue", "weather.davao", 'mprsdcdo'
    ],

    "search_queries": [
        "BahaPH", "EarthquakeAlert", "EarthquakePH",
        "FireAlert", "FireandRescuePH", "FloodAlert",
        "LandslideAlert", "LandslidePH", "RescuePH",
        "StreetFloodAlert", "tsunamialert"
    ]
}

# X user and search query scraper configuration
X = {
    "users": [
        "ABSCBNNews", "dost_pagasa", "gmanews",
        "inquirerdotnet", "mindanewsdotcom", "NDRRMC_OpCen", 
        "News5PH", "PhilstarNews", "phivolcs_dost", "PilipinasToday_"
        "rapplerdotcom", "SunStarDavao", "TVPatrol"
    ],

    "search_queries": [
        "Disaster news Davao", "disaster news philippines",
        "Earthquake in Davao", "earthquake philippines",
        "Fire in Davao", "fire philippines",
        "Flood in Davao", "flood philippines",
        "Landslide in Davao", "landslide philippines",
        "Typhoon in Davao", "typhoon philippines",
        "Volcano eruption Davao", "volcano eruption philippines"
    ]
}

# keywords for filtering disaster-related posts
KEYWORDS = [
    # Typhoon / Storm
    "typhoon", "storm", "storm surge",
    "tropical storm", "tropical depression",
    "super typhoon", "tropical cyclone",   
    "bagyo", "unos", "thunderstorm", "lightning",
    "malakas na bagyo", "malakas na hangin", 
    "#typhoon", "#storm", 

    # Rain / Weather
    "rain", "raining", "rainfall",
    "heavy rain", "heavy rainshowers", "monsoon",
    "LPA", "low pressure area",
    "malakas na ulan",
    
    # Flood (and related)
    "flood", "flooding", "flash flood", "river overflow", 
    "street flood", "baha", "lunop",
    "pagbaha", "paglunop", "flood alert",   
    "#flood", "#FloodAlert", "#BahaPH", "#StreetFloodAlert",

    # Landslide / Mudslide
    "landslide", "mudslide", "soil erosion", "slope failure",
    "pagguho ng lupa", "nangurog",  
    "#landslide", "#LandslideAlert", "#LandslidePH",

    # Earthquake
    "earthquake", "aftershock", "ground shaking", "seismic",
    "lindol", "linog", "pagyanig",       
    "#EarthquakeAlert", "#EarthquakePH",

    # Tsunami
    "tsunami", "tidal wave", "sea surge", "coastal surge",
    "daluyong",                     
    "#tsunami",

    # Fire / Wildfire
    "fire", "blaze", "burning", "wildfire",
    "sunog", "nasunog","apoy",            
    "#FireAlert",

    # Volcano
    "volcano", "volcanic", "eruption", "ashfall", "lava",
    "bulkan", "pagputok ng bulkan",  
    "#volcano", "Taal", "Mayon", "Pinatubo", "Kanlaon", "Balusan",

    # General disaster / emergency
    "disaster", "emergency", "rescue", "relief",
    "evacuate", "evacuation", "evacuated", "#evacuation",
    "disaster response", "disaster relief",

    # Warnings & Alerts
    "warning", "alert", "advisory", "bulletin",
    "babala", "abiso",              
    "#warning", "#alert",

    # Tagalog / Cebuano extras
    "pag-uga", "pagbaha", "paglikas", "malakas na ulan",
    "mainit na bato", "kalamidad", "sakuna",
    "pahimangno", "pasidaan",

    # Bisaya / Cebuano extras
    "nahulog ang yuta", "nabahaan",
    "kusog nga ulan", "ting-ulan",
    "tabang"
]
