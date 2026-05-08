# ClubHub Backend Deployment

This backend has two separate runtime jobs:

- API server: long-running Flask process on port `5001`
- Sync runner: periodic scraper job that refreshes `clubhub.db`

## Local Mac: keep it running with `launchd`

### One-time setup

```bash
cd /Users/devinmcnair/Desktop/ClubHub/backend
chmod +x clubhub_api.sh clubhub_sync.sh install_launchd_api.sh install_launchd_sync.sh
./install_launchd_api.sh
./install_launchd_sync.sh
```

### What this does

- `com.clubhub.api`: starts the backend automatically at login and restarts it if it exits
- `com.clubhub.sync`: runs the scraper sync every `259200` seconds (every 3 days)

### Check status

```bash
launchctl list | grep clubhub
curl -s http://localhost:5001/api/status
```

### Logs

- `logs/api.log`
- `logs/sync.log`
- `logs/launchd.api.out.log`
- `logs/launchd.api.err.log`
- `logs/launchd.out.log`
- `logs/launchd.err.log`

### If the job exits immediately with code `127`

On macOS, `launchd` can fail when the repo lives under protected folders like `Desktop`, `Documents`, or `Downloads`.

If that happens, move the repo to a non-protected path such as:

```bash
~/Code/ClubHub
```

Then update any hard-coded paths in the plist and shell wrapper files before reinstalling the jobs.

### Stop or restart

```bash
launchctl unload ~/Library/LaunchAgents/com.clubhub.api.plist
launchctl unload ~/Library/LaunchAgents/com.clubhub.sync.plist
```

```bash
launchctl load ~/Library/LaunchAgents/com.clubhub.api.plist
launchctl load ~/Library/LaunchAgents/com.clubhub.sync.plist
```

## Production VPS: recommended shape

Use one Linux VPS with persistent disk. Keep the SQLite database on that server.

### Backend setup

```bash
cd backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

### Environment

Optional variables:

```bash
CLUBHUB_HOST=0.0.0.0
CLUBHUB_PORT=5001
CLUBHUB_DEBUG=0
CLUBHUB_ADMIN_TOKEN=replace-with-a-long-random-secret
CLUBHUB_ALLOWED_ORIGINS=https://your-frontend-domain.com
```

### Run manually

```bash
./venv/bin/python app.py
```

### Keep it running on Linux

Use:

- `systemd` service for `app.py`
- `systemd` timer or cron for `run_sync.py`

Example API service command:

```bash
/path/to/backend/venv/bin/python /path/to/backend/app.py
```

Example sync command:

```bash
/path/to/backend/venv/bin/python /path/to/backend/run_sync.py
```

## Important current behavior

- `app.py` now reads `CLUBHUB_HOST`, `CLUBHUB_PORT`, and `CLUBHUB_DEBUG`
- sync logic is lazy-loaded so the API process starts without eagerly importing all scraper modules
