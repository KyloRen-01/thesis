# Flood Facebook Scraper

This project collects flood-related public posts from configured Facebook
pages, hashtags, and post searches. Matching posts are filtered for flood
keywords and Philippine locations, then saved as CSV files.

## Requirements

- Python 3.10 or newer
- Google Chrome
- An active internet connection
- A Facebook account, if Facebook asks you to log in

Selenium can automatically download or locate a compatible ChromeDriver. If
that does not work on your machine, install ChromeDriver manually and provide
its path when running the scraper.

## Installation on Windows

Open PowerShell and run these commands from the directory containing the
`Flood-scraper` folder:

```powershell
cd Flood-scraper
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r src\requirements.txt
```

If PowerShell does not allow activation, run this once in PowerShell as your
user:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## First run and Facebook login

Run the scraper in visible-browser mode the first time. The `--login` option
opens Chrome and waits while you log in manually:

```powershell
python src\scraper\fb_flood_scraper.py --login
```

After logging in, return to PowerShell and press `Enter`. The scraper then
visits the configured pages and searches, and saves the results.

The login session is stored in `.facebook_chrome_profile` so later runs can
reuse it. Do not share or commit this directory because it contains browser
session data.

Close any Chrome window using this profile before starting another run.

## Run the scraper

To run using the saved Facebook session:

```powershell
python src\scraper\fb_flood_scraper.py --headed
```

To run without displaying Chrome:

```powershell
python src\scraper\fb_flood_scraper.py
```

By default, the scraper has no timestamp cutoff and collects the posts that
Facebook loads while scrolling. To collect only recent posts, provide the
number of hours separately for page feeds and search feeds. For example, the
following collects posts from approximately the last 30 days:

```powershell
python src\scraper\fb_flood_scraper.py --hours-page 720 --hours-search 720
```

Use the help command to see all available options:

```powershell
python src\scraper\fb_flood_scraper.py --help
```

## Output files

Each run creates a new timestamped CSV in:

```text
data/raw/facebook/fb_raw_floodData_MM-DD-YYYY_HHMMSS.csv
```

For example:

```text
data/raw/facebook/fb_raw_floodData_10-10-2026_143015.csv
```

You can request a custom output path with `--output`:

```powershell
python src\scraper\fb_flood_scraper.py `
  --output data\raw\facebook\my_flood_posts.csv
```

The scraper saves checkpoints after each page, hashtag, and search feed. If
you stop it with `Ctrl+C`, the latest completed checkpoint remains in the CSV.

## Configuration

Edit [`src/scraper/fb_scraping_config.py`](scraper/fb_scraping_config.py) to
change:

- Facebook page usernames in `FACEBOOK["users"]`
- Hashtags and search terms in `FACEBOOK["search_queries"]`
- Flood-related matching terms in `KEYWORDS`
- Philippine location terms in `PH_LOCATIONS`

Only add verified Facebook page usernames. The scraper processes content that
is visible in the browser and does not bypass login screens, CAPTCHA, or other
access controls.

## ChromeDriver troubleshooting

If Selenium cannot start ChromeDriver, provide the executable path directly:

```powershell
python src\scraper\fb_flood_scraper.py `
  --headed `
  --chromedriver C:\tools\chromedriver-win64\chromedriver.exe
```

Alternatively, set the `CHROMEDRIVER_PATH` environment variable for the
current PowerShell session:

```powershell
$env:CHROMEDRIVER_PATH = 'C:\tools\chromedriver-win64\chromedriver.exe'
python src\scraper\fb_flood_scraper.py --headed
```
