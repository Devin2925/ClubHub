# Backup And Restore

ClubHub creates a SQLite backup before every sync run in [backups](/Users/devinmcnair/Desktop/ClubHub/backend/backups).

## What happens automatically

- Every sync creates a timestamped backup file:
  - `backend/backups/clubhub-YYYYMMDD-HHMMSS.sqlite3`
- The system keeps the most recent `12` backups.
- Old backups are deleted automatically.

## Restore the database

1. Stop the running app processes.
   - `./stop_clubhub.sh`
2. Pick the backup file you want from [backups](/Users/devinmcnair/Desktop/ClubHub/backend/backups).
3. Replace the live DB.

```bash
cp /Users/devinmcnair/Desktop/ClubHub/backend/backups/clubhub-YYYYMMDD-HHMMSS.sqlite3 \
  /Users/devinmcnair/Desktop/ClubHub/backend/clubhub.db
```

4. Start the app again.
   - `./start_clubhub.sh`

## Verify after restore

- Open `http://localhost:3000/status`
- Check `http://localhost:5001/api/status`
- Run:

```bash
cd /Users/devinmcnair/Desktop/ClubHub/backend
./venv/bin/python rerun_health.py
```
