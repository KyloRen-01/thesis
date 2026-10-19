# Flood-scraper

Flood-scraper collects flood-related posts from Facebook and X, downloads
available post images, cleans the text, and combines both sources into one
CSV file.

## Clone and install

Requirements:

- Python 3.10 or newer
- Google Chrome
- Internet access

Clone the repository and enter the Flood-scraper directory:

```powershell
git clone https://github.com/KyloRen-01/thesis.git
cd thesis\flood-scrapers\Flood-scraper
```

Create the virtual environment and install the dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, run this once and then activate the
environment again:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Initialize the browser sessions

The pipeline uses two persistent Chrome profiles:

```text
.facebook_dummy_chrome_profile
.x_dummy_chrome_profile
```

If the profiles are not already available or a session has expired, initialize
them manually:

```powershell
python src\init_social_sessions.py
```

Log in to Facebook when its browser window opens, return to PowerShell, and
press `Enter`. Then log in to X and press `Enter` again. The sessions are saved
in the two profile directories for later runs.

If Facebook is already saved and only X needs to be initialized:

```powershell
python src\init_social_sessions.py --skip-facebook
```

Close any Chrome windows using these profiles before running the pipeline.

## Run the full pipeline

From the `Flood-scraper` directory, run:

```powershell
python src\run_full_pipeline.py
```

This command reuses the saved Facebook and X sessions, includes existing raw
Facebook and X data, and keeps short posts. Therefore, `--login` is not needed
for normal runs.

Use this command without `--include-history` when only the newest Facebook and
X scrape should be cleaned:

```powershell
python src\run_full_pipeline.py --headed --min-length 0
```

## Current pipeline flow

The full pipeline runs in this order:

1. **Facebook scraping**

   The configured Facebook pages, hashtags, and searches are scraped. A new
   timestamped raw CSV is written to `data/raw/facebook/`. Available images
   are downloaded to `data/raw/facebook/images/`. Posts without images are
   retained.

2. **X scraping**

   The configured X accounts and flood-related searches are scraped. A new
   timestamped raw CSV is written to `data/raw/twitter/`. Available images are
   downloaded to `data/raw/twitter/images/`. Posts without images are retained.

3. **History selection**

   With `--include-history`, all non-empty raw Facebook and X CSV files are
   included, including previously scraped Facebook data. Without this option,
   only the newest raw CSV from each source is used.

4. **Text cleaning**

   URLs, emojis, HTML, control characters, repost boilerplate, repeated
   whitespace, duplicates, and near-duplicate tails are removed. Posts are
   not discarded just because they have no image. The original `text` column
   and cleaned `text_content` column are retained.

5. **Merged output**

   The cleaned combined dataset is written to:

   ```text
   data/merged/merged_flood_data.csv
   ```

   If that file already exists, a timestamped filename is created so the
   previous result is not overwritten.

