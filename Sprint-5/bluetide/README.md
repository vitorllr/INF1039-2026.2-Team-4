# BlueTide

BlueTide compares beach conditions by collection point and only recommends a point when the minimum quality and freshness data are available.
The default setup uses deterministic demonstration data and labels that mode in every data-driven flow.

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

`BLUETIDE_DATA_MODE` accepts `fixture` or `live` and defaults to `fixture`.
`BLUETIDE_HTTP_TIMEOUT` is the bounded Open-Meteo timeout in seconds and defaults to `4.0`.
`BLUETIDE_DATA_CACHE_SECONDS` controls the in-process live-data cache and defaults to `300`.
`BLUETIDE_WATER_DATA_FILE` must point to an updated water-quality JSON file before live mode can recommend any point.
`DJANGO_SECRET_KEY` must be set to a private value outside development.
`DJANGO_DEBUG` defaults to `true` and must be `false` in production.
`DJANGO_ALLOWED_HOSTS` is a comma-separated host list.
`DJANGO_DB_PATH` optionally selects a SQLite file for isolated validation.

The accepted water-quality schema is demonstrated in `bluetideapp/fixtures/conditions.json`.
The local fixture uses relative ages so automated checks stay deterministic.
Production ingestion should write current official timestamps as relative ages immediately before the application reads the file, or adapt the provider to the official feed when a stable feed is available.

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
python manage.py check --deploy
python manage.py runserver 127.0.0.1:8000
curl --fail --silent --show-error http://127.0.0.1:8000/web/ >/dev/null
```

## Persona demo video

The reproducible script records the running application through a real Chromium session at 1280 by 720 pixels.
It uses the deterministic fixture and shows the complete Pedro journey, including unavailable, stale, and incomplete data states.

Start the application in another terminal.

```bash
BLUETIDE_DATA_MODE=fixture python manage.py runserver 127.0.0.1:8765
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
