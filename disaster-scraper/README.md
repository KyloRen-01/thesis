# 🌊 Disaster-Scraper

**Automated Social Media Data Pipeline for Disaster Monitoring and Analysis**

This repository powers the **DisasterReady AI Chatbot** dataset pipeline — an end-to-end system that scrapes, cleans, and processes social-media posts (Facebook, X/Twitter) for disaster-related content in the Philippines.  
It integrates **XLM-RoBERTa-based Named Entity Recognition (NER)** for extracting locations and datetimes, plus **zero-shot classification** for disaster type labeling.

Each step is modular, timestamped, and can be skipped or chained via the unified script `run_full_pipeline.py`.

---

## 🧩 Pipeline Overview

```
1️⃣ Scrape → 2️⃣ NER (Location, Datetime) → 3️⃣ Cleaning → 4️⃣ Classification → 5️⃣ Upload / Output
```

Each phase automatically saves timestamped CSVs in `data/raw`, `data/interim`, and `data/processed`.

---

## 📁 Repository Structure

```
disaster-scraper/
├── data/
│   ├── raw/          # raw scraped CSVs (Facebook/X)
│   ├── interim/      # intermediate outputs (NER, cleaned, partial)
│   ├── processed/    # final processed datasets (for ingestion to backend)
│   └── lookup/       # PSGC or other reference tables
│
├── src/
│   ├── scraping/
│   │   ├── fb_disaster_scraper.py
│   │   ├── x_disaster_scraper.py
│   │   └── social_media_config.py
│   │
│   ├── ner/
│   │   ├── extract_location.py
│   │   ├── extract_datetime.py
│   │   └── classify_disaster.py
│   │
│   ├── preprocessing/
│   │   ├── data_cleaning_pipeline.py
│   │   ├── format_columns.py
│   │   ├── drop_tail_near_duplicates.py
│   │   ├── clean_text.py
│   │   ├── extract_pagesource.py
│   │   └── location_filter.py
│   │
│   ├── utils/
│   │   ├── file_ops.py
│   │   ├── upload_to_backend.py
│   │   └── helpers.py
│   │
│   └── run_full_pipeline.py
│
├── requirements.txt
├── .gitignore
└── README.md
```

---

## ⚙️ Setup & Installation

### 1️⃣ Clone and install dependencies

```bash
git clone https://github.com/<yourusername>/disaster-scraper.git
cd disaster-scraper
pip install -r requirements.txt
```

Use Python **3.9+**.  
Make sure you have valid scraping credentials or cookies in `.env` if applicable.

---

## 🚀 Running the Full Pipeline

### ▶️ Run all steps (end-to-end)

```bash
python3 src/run_full_pipeline.py
```

This will:

1. Scrape Facebook & X posts
2. Extract locations and datetimes
3. Clean and normalize the text
4. Classify disaster type
5. Save timestamped CSVs under `data/processed/`

---

### ⚡ Optional CLI Flags

You can skip any step to reuse previous outputs.

| Flag                  | Description                                         |
| --------------------- | --------------------------------------------------- |
| `--skip-scrape`       | Use latest CSV from `data/raw/` instead of scraping |
| `--skip-ner-loc`      | Skip NER (Location extraction)                      |
| `--skip-ner-datetime` | Skip NER (Datetime extraction)                      |
| `--skip-clean`        | Skip data cleaning and filtering                    |
| `--skip-classify`     | Skip disaster type classification                   |
| `--auto`              | Automatically upload the final CSV to backend       |

### Example:

```bash
# Run NER and classification only (no scraping or cleaning)
python3 src/run_full_pipeline.py --skip-scrape --skip-clean
```

---

## 🔁 Example Run Output

```bash
🚀 Starting Disaster Data Pipeline...

🌐  [1] Scraping social media posts...
✅ Scraped 45 FB + 50 X posts → 95 total
💾 Saved raw data → data/raw/merged_raw_disaster_posts_2025-10-26_1130.csv

📍  [2] Extracting LOCATION entities from posts...
✅ Location extraction complete → data/interim/ner_with_locations_2025-10-26_1131.csv

📅  [3] Extracting DATETIME entities from posts...
✅ Datetime extraction complete → data/interim/ner_with_datetime_2025-10-26_1132.csv

🧹  [4] Running cleaning pipeline...
✅ Cleaning complete → data/interim/cleaned_ner_with_locations_datetime_2025-10-26_1133.csv

🗂️  [5] Classifying disaster type...
✅ Final dataset saved (89 rows) → data/processed/final_output_2025-10-26_1134.csv

🎉 Pipeline execution finished successfully.
```

---

## 🤖 Auto Upload (to Disaster Chatbot Backend)

If you deployed your backend on **Railway** (`https://disaster-chatbot-backend-production.up.railway.app`),  
you can automatically upload the new dataset when the pipeline completes:

```bash
python3 src/run_full_pipeline.py --auto
```

If upload fails, the script retries once after 5 seconds.  
Upload logic is handled in `utils/upload_to_backend.py` → `ingest_new_data()`.

---

## 🧠 Models Used

| Task                    | Model                             | Source      |
| ----------------------- | --------------------------------- | ----------- |
| Location Extraction     | `Davlan/xlm-roberta-base-ner-hrl` | HuggingFace |
| Datetime Extraction     | `programmersilvanus/ner-xlmr`     | HuggingFace |
| Disaster Classification | `joeddav/xlm-roberta-large-xnli`  | HuggingFace |

---

## 📊 Output Schema

| Column               | Description                                  |
| -------------------- | -------------------------------------------- |
| `source`             | Platform (Facebook or X)                     |
| `text_content`       | Cleaned and normalized post text             |
| `event_time_primary` | Parsed datetime (standardized ISO format)    |
| `location`           | Extracted and PSGC-aligned location          |
| `disaster_type`      | Predicted disaster category (flood, quake…)  |
| `sentiment_score`    | (Optional) sentiment or relevance confidence |
| `url`                | Original post link                           |

---

## 🧰 File Management

- **Timestamped filenames:**  
  Each intermediate and final CSV is automatically saved with a timestamp:

  ```
  data/processed/final_output_2025-10-26_1134.csv
  ```

- **Automatic latest loading:**  
  If a step is skipped, the pipeline automatically detects the most recent file with the correct prefix (e.g. `ner_with_datetime_*`).

---

## 🪄 Example Cron Job (for daily automation)

```bash
# Run full pipeline daily at 11:30 AM and upload to backend
30 11 * * * /usr/bin/python3 /path/to/disaster-scraper/src/run_full_pipeline.py --auto >> ~/logs/pipeline_cron.log 2>&1
```

---

## 🌐 Backend Integration (for Disaster Chatbot)

This repository integrates with your deployed backend:

```
https://disaster-chatbot-backend-production.up.railway.app
```

The backend ingests processed datasets into a **Qdrant vector database**,  
serving as the retrieval layer for your **Expo-based mobile chatbot**.

The `--auto` flag in this pipeline automatically calls:

```
POST /ingest
Content-Type: multipart/form-data
file: final_output_<timestamp>.csv
```

to update the chatbot’s knowledge base with the latest disaster posts.

---

## 🧾 License

MIT © 2025 — DisasterReady AI / Ateneo de Davao University  
Developed by **Cassey Gempesaw**  
Part of the _Flood and Disaster Resilience Chatbot Project_ 🌀
