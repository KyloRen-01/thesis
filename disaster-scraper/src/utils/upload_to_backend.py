# src/utils/upload_to_backend.py
import os
import requests

BACKEND_URL = "http://localhost:8000/scraper"

# 1 Upload CSV only (store in backend /data)
def upload_csv_to_backend(csv_path: str):
    """
    Uploads a cleaned CSV file to the backend for storage only
    (no embedding or ingestion to Qdrant).
    """
    endpoint = "/upload-csv"
    url = BACKEND_URL.rstrip("/") + endpoint

    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        return

    with open(csv_path, "rb") as f:
        files = {"file": (os.path.basename(csv_path), f, "text/csv")}
        try:
            res = requests.post(url, files=files, timeout=300)
            res.raise_for_status()
            print(f"Uploaded CSV to backend → {url}")
            print("Response:", res.json())
        except requests.RequestException as e:
            print(f"Upload failed: {e}")
            if res is not None:
                print("Response:", res.text)

# 2 Ingest new data (embed + upsert into Qdrant)
def ingest_new_data(csv_path: str):
    """
    Sends a CSV file to the backend to be embedded and upserted into Qdrant.
    """
    endpoint = "/ingest-new-data" 
    url = BACKEND_URL.rstrip("/") + endpoint

    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        return

    with open(csv_path, "rb") as f:
        files = {"file": (os.path.basename(csv_path), f, "text/csv")}
        try:
            res = requests.post(url, files=files, timeout=600)
            res.raise_for_status()
            print(f"Ingested new data into Qdrant → {url}")
            print("Response:", res.json())
        except requests.RequestException as e:
            print(f"Ingestion failed: {e}")
            if res is not None:
                print("Response:", res.text)
