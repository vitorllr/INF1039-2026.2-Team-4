# BlueTide

BlueTide compares beach conditions by collection point and only recommends a point when the minimum quality and freshness data are available.
The default setup shows real INEA water quality with live Open-Meteo sea and weather.
The deterministic demonstration data is an explicit mode and is labelled in every data-driven flow.

## Live weather data

The details screen used to call the Open-Meteo marine API on every request.
That call now lives in `bluetideapp/services/providers.py`, with the same endpoint, the same Ipanema Posto 9 coordinates and the same four marine fields (wave height, wave period, sea surface temperature and sea level).
It runs in the default live mode, with the same Open-Meteo marine fields as before.
Water quality comes from real INEA data, see "INEA water data" below.
`BLUETIDE_DATA_MODE=demo` brings back the demonstration values and the "Modo demonstração" notice.

```bash
python manage.py runserver
```

If Open-Meteo is unreachable the screens show the "Atualização incompleta" notice and every card reads "Sem recomendação".
The details screen also shows the "Atualização ao vivo falhou" notice with the same reason.

## Local setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/web/`.

## Data configuration

`BLUETIDE_DATA_MODE` accepts `live` or `demo` and defaults to `live`.
`live` shows real INEA water quality from `bluetideapp/data/agua_inea.json` plus Open-Meteo sea and weather.
`demo` uses the deterministic fixture and is what the automated tests and the demo video use.
`BLUETIDE_HTTP_TIMEOUT` is the bounded Open-Meteo timeout in seconds and defaults to `4.0`.
`BLUETIDE_DATA_CACHE_SECONDS` controls the in-process live-data cache and defaults to `300`.
`BLUETIDE_WATER_DATA_FILE` overrides the water-quality JSON file and defaults to the committed INEA file.
`DJANGO_SECRET_KEY` must be set to a private value outside development.
`DJANGO_DEBUG` defaults to `true` and must be `false` in production.
`DJANGO_ALLOWED_HOSTS` is a comma-separated host list.
`DJANGO_DB_PATH` optionally selects a SQLite file for isolated validation.
`DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_SESSION_COOKIE_SECURE`, and `DJANGO_CSRF_COOKIE_SECURE` enable the corresponding production HTTPS protections.
`DJANGO_SECURE_HSTS_SECONDS` sets the HSTS duration and should only be enabled after HTTPS is confirmed for the entire domain.
`DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` and `DJANGO_SECURE_HSTS_PRELOAD` should only be enabled when every subdomain is permanently HTTPS-ready.

The accepted water-quality schema is demonstrated in `bluetideapp/fixtures/conditions.json`.
The demo fixture uses relative ages so automated checks stay deterministic.
The INEA file stores the absolute `collected_on` date, so the age shown in the app is always computed from the real collection date.

## INEA water data

INEA has no API, so `python manage.py atualizar_agua_inea` downloads the yearly history PDF from the INEA Rio de Janeiro page and rewrites `bluetideapp/data/agua_inea.json`.
It needs `pip install -r requirements-inea.txt` and keeps the previous file if anything fails.
`--pdf` reads a local PDF and `--output` writes elsewhere.
Each posto is mapped to the nearest INEA monitoring point in `bluetideapp/data/inea_pontos.json`, estimated by distance.
INEA does not monitor by posto, so the app labels these as the nearest INEA point.
The Sprint 9 rule marks a collection older than 9 days as old and older than 30 days as unusable, and the notice in the app says so.

The command finds the "Último Boletim Divulgado" and the year-history links by link text, never by a fixed PDF address, and downloads with a 30 s timeout and a `User-Agent` that names the project.
PDFs are cached by SHA-256 in `.inea-cache/` next to the output file (`--cache-dir` changes it).
Before writing, it checks that at least 30 points and 10 collection dates were read, that every mapped point has a valid collection that is not in the future, and that no posto goes back in time compared with the current file.
The write is atomic (temporary file, then rename).
On any failure it writes nothing, prints the reason and exits with status 1.
If neither the PDF nor the day changed since the last success it exits 0 without rewriting, and `--force` rewrites anyway.
In January, when the new-year history is not on the page yet, it uses the previous year's history plus the one-page "Último Boletim Divulgado" and logs "plano B".

### Scheduling

INEA collects mostly on Wednesdays and publishes about a day later, so twice a day is enough.
Each run makes 2 small requests.

cron, at 10:00 and 17:00:

```cron
0 10,17 * * * cd /path/to/Sprint-5/bluetide && .venv/bin/python manage.py atualizar_agua_inea --output /var/lib/bluetide/agua.json >> /var/log/bluetide-inea.log 2>&1
```

launchd (macOS), saved as `~/Library/LaunchAgents/br.bluetide.inea.plist` and loaded with `launchctl load`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>br.bluetide.inea</string>
  <key>WorkingDirectory</key><string>/path/to/Sprint-5/bluetide</string>
  <key>ProgramArguments</key>
  <array>
    <string>/path/to/Sprint-5/bluetide/.venv/bin/python</string>
    <string>manage.py</string>
    <string>atualizar_agua_inea</string>
    <string>--output</string>
    <string>/var/lib/bluetide/agua.json</string>
  </array>
  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Hour</key><integer>10</integer><key>Minute</key><integer>0</integer></dict>
    <dict><key>Hour</key><integer>17</integer><key>Minute</key><integer>0</integer></dict>
  </array>
  <key>StandardOutPath</key><string>/tmp/bluetide-inea.log</string>
  <key>StandardErrorPath</key><string>/tmp/bluetide-inea.log</string>
</dict>
</plist>
```

Point `BLUETIDE_WATER_DATA_FILE` at the same output path when starting the app.
Alert when the job exits non-zero or when `generated_at` in the file is more than 10 days old.

Live marine and weather data come from Open-Meteo.
If Open-Meteo fails, the UI keeps the supporting values visible but suspends recommendations.
If the official water-quality file is missing, live weather alone cannot produce a recommendation.

## Validation

Run the focused tests first.

```bash
python manage.py test bluetideapp.tests.RecommendationTests bluetideapp.tests.ProviderTests -v 2
python manage.py test bluetideapp.tests.ViewTests -v 2
```

Then run the complete checks.

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test -v 2
ruff check .
```

Use an isolated clean database for migration validation.

```bash
validation_dir="$(mktemp -d)"
DJANGO_DB_PATH="$validation_dir/db.sqlite3" python manage.py migrate --noinput
DJANGO_DB_PATH="$validation_dir/db.sqlite3" python manage.py showmigrations --plan
```

Verify the production data boundary without printing credentials.

```bash
export BLUETIDE_DATA_MODE=live
export BLUETIDE_WATER_DATA_FILE=/secure/path/boletim-atual.json
export BLUETIDE_HTTP_TIMEOUT=4
export DJANGO_SECRET_KEY='set-this-outside-the-repository'
export DJANGO_DEBUG=false
export DJANGO_ALLOWED_HOSTS='bluetide.example.com'
export DJANGO_SECURE_SSL_REDIRECT=true
export DJANGO_SESSION_COOKIE_SECURE=true
export DJANGO_CSRF_COOKIE_SECURE=true
export DJANGO_SECURE_HSTS_SECONDS=31536000
export DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=true
export DJANGO_SECURE_HSTS_PRELOAD=true
python manage.py check --deploy
python manage.py runserver 127.0.0.1:8000
curl --fail --silent --show-error http://127.0.0.1:8000/web/ >/dev/null
```

## Persona demo video

The reproducible script records the running application through a real Chromium session at 1280 by 720 pixels.
It uses the deterministic fixture and shows the complete Pedro journey, including unavailable, stale, and incomplete data states.

Start the application in another terminal.

```bash
BLUETIDE_DATA_MODE=demo python manage.py runserver 127.0.0.1:8765
```

Install the recording dependency and generate the video.

```bash
pip install -r requirements-demo.txt
python -m playwright install ffmpeg
python scripts/record_demo.py
```

Play the generated artifact.

```bash
ffplay artifacts/bluetide-pedro-demo.mp4
```

The detailed storyboard is in `docs/demo-pedro.md`.
