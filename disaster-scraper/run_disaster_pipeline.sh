#!/bin/bash
# --------------------------------------------
# Disaster Scraper Pipeline - macOS Cron Wrapper
# --------------------------------------------

cd "/Users/casseygempesaw/Desktop/Thesis/disaster-scraper"

# If using a virtualenv, uncomment:
# source venv/bin/activate

echo "[$(date)] Starting Disaster Pipeline..." >> logs/pipeline_cron.log 2>&1
/usr/local/bin/python3 src/run_full_pipeline.py --auto >> logs/pipeline_cron.log 2>&1
echo "[$(date)] Pipeline finished." >> logs/pipeline_cron.log 2>&1

# macOS notification
osascript -e 'display notification "Disaster pipeline finished successfully ✅" with title "Cron Job Complete" sound name "Ping"'
