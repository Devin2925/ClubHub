# ClubHub Launch Checklist

This is the practical checklist for getting ClubHub live without losing data quality or operational visibility.

## Recommended Production Setup

Use one small Linux VPS first.

- Frontend: Next.js on port `3000`
- Backend: Flask on port `5001`
- Reverse proxy: `Caddy` or `nginx`
- Database: keep `backend/clubhub.db` on persistent disk
- Sync runner: cron or systemd timer on the server

Do not split the frontend and backend onto different hobby services first. The app depends on scheduled scraping, a writable SQLite database, backups, and local source-health tracking. A single VPS is simpler and more reliable.

## Pre-Launch Requirements

### App health

- [ ] `http://localhost:3000/status` looks clean locally
- [ ] `GET /api/status` returns `healthy > 0`, `error = 0`, `stale = 0`
- [ ] `GET /api/source-alerts` returns no alerts
- [ ] `GET /api/venue-alerts` returns no alerts
- [ ] Manual rerun from status page works
- [ ] Scheduled sync works without manual intervention

### Data quality

- [ ] Major municipalities show upcoming events
- [ ] UVic appears in municipality filters
- [ ] Date chips filter correctly
- [ ] Sport icons are mapped correctly
- [ ] `other` is now treated as `Community` in the UI
- [ ] No expired events appear on the public pages

### Operational safety

- [ ] DB backups are being created before syncs
- [ ] Backup restore procedure is tested once
- [ ] Logs rotate correctly
- [ ] Admin reruns are restricted to localhost or `CLUBHUB_ADMIN_TOKEN`

## Production Environment Variables

Frontend:

```bash
NEXT_PUBLIC_API_URL=https://your-domain.com
```

Backend:

```bash
CLUBHUB_ADMIN_TOKEN=replace-with-long-random-secret
```

If the site is public, do not leave admin reruns exposed only by localhost rules.

## Production Deployment Steps

### 1. Provision server

- Ubuntu 24.04 LTS or similar
- install:
  - `python3`
  - `python3-venv`
  - `node`
  - `npm`
  - `sqlite3`
  - `caddy` or `nginx`

### 2. Copy project

```bash
git clone <repo>
cd ClubHub
```

### 3. Backend setup

```bash
cd backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python run_sync.py
```

### 4. Frontend setup

```bash
cd ../frontend
npm install
npm run build
```

### 5. Start services

You want long-running services, not terminal sessions.

Use:

- `systemd` service for Flask backend
- `systemd` service for Next frontend
- `systemd` timer or cron for `backend/run_sync.py`

Do not use macOS `launchd` on the production server. That is only for the local Mac setup.

## Live Monitoring Checklist

Check these after every scheduled sync:

- `/status`
- `/api/source-alerts`
- `/api/venue-alerts`

Interpretation:

- `source alert` means a connector failed or dropped sharply
- `venue alert` means a venue likely lost rows compared with a previous run
- `stale` means the sync is no longer current enough

## What To Do If Something Breaks

### Source failed

1. Open `/status`
2. Check `/api/source-alerts`
3. Re-run just the affected source
4. If it still fails, inspect:
   - schedule page changed
   - PDF URL changed
   - widget/API changed

### Venue suddenly empty

1. Check `/api/venue-alerts`
2. Compare that venue with its public website
3. Re-run its municipality or source
4. If still empty, the connector needs maintenance

### Bad DB state

1. Stop app services
2. Restore latest backup from `backend/backups`
3. Start app again
4. Recheck `/status`

## Weekly / Every-Few-Days Data Accuracy Routine

This is the minimum routine to keep data trustworthy:

1. Scheduled sync runs automatically
2. Check `/status`
3. If `source alerts = 0` and `venue alerts = 0`, leave it alone
4. If not, inspect only the affected source or venue

This is already supported by the current app structure.

## Traffic Readiness

Before trying to drive traffic, make sure users can trust what they see.

- [ ] show last updated time visibly
- [ ] keep venue pages populated with upcoming data only
- [ ] keep CARSA / UVic data visible in filters
- [ ] no major source alerts for at least a few consecutive sync cycles

Once that is stable:

- [ ] connect domain
- [ ] add Google Search Console
- [ ] add Bing Webmaster Tools
- [ ] submit sitemap
- [ ] keep municipality / venue pages indexable
- [ ] share venue-specific pages, not just the homepage

## Launch Decision Rule

ClubHub is ready for a small public launch when:

- scheduled syncs are stable
- source alerts stay at zero across several cycles
- venue alerts stay at zero across several cycles
- the highest-traffic venues look correct by manual spot check
- backup/restore has been tested once

If those are not true, do not push traffic yet.
