# Vercel Frontend + Local Backend Setup

This is the fastest way to share ClubHub with friends before moving the backend to a real server.

If you do not need live refreshes during the test, use the frozen demo mode instead. That is simpler and more reliable than tunneling your laptop.

## Architecture

- Frontend: Vercel
- Backend: your local machine
- Database: local `backend/clubhub.db`
- Public backend access: a tunnel

Important:

- your local backend must be reachable from the internet
- `localhost:5001` is not reachable by Vercel or your friends
- if your laptop sleeps, shuts down, loses internet, or the tunnel dies, the live site breaks

This is fine for testing. It is not a stable production setup.

## Recommended Temporary Setup

Use:

- Vercel for the `frontend`
- a tunnel for `http://localhost:5001`

Two reasonable tunnel options:

1. `ngrok`
   - easiest for a quick test
   - free URLs usually rotate
2. `Cloudflare Tunnel`
   - better if you want a more stable tunnel URL

## Step 1: Make Backend Accept Your Vercel Frontend

The backend now supports extra CORS origins using:

```bash
CLUBHUB_ALLOWED_ORIGINS
```

Example:

```bash
export CLUBHUB_ALLOWED_ORIGINS="https://clubhub-yourname.vercel.app"
```

If you later add a custom domain:

```bash
export CLUBHUB_ALLOWED_ORIGINS="https://clubhub-yourname.vercel.app,https://clubhub.ca"
```

## Step 2: Run the Backend Locally

```bash
cd /Users/devinmcnair/Desktop/ClubHub/backend
./venv/bin/python app.py
```

Or use the normal project startup script:

```bash
cd /Users/devinmcnair/Desktop/ClubHub
./start_clubhub.sh
```

Confirm locally:

- `http://localhost:5001/api/status`

## Step 3: Expose the Backend Publicly

Example with `ngrok`:

```bash
ngrok http 5001
```

That will give you a public URL like:

```bash
https://abc123.ngrok-free.app
```

Confirm from your browser:

- `https://abc123.ngrok-free.app/api/status`

If that does not work, the frontend will not work either.

## Step 4: Deploy the Frontend to Vercel

Deploy only the `frontend` directory.

In Vercel project settings, set:

```bash
NEXT_PUBLIC_API_URL=https://abc123.ngrok-free.app
```

You can use [frontend/.env.example](/Users/devinmcnair/Desktop/ClubHub/frontend/.env.example) as the reference.

## Step 5: Make CORS Match

Once Vercel gives you a frontend URL like:

```bash
https://clubhub-yourname.vercel.app
```

restart the local backend with:

```bash
export CLUBHUB_ALLOWED_ORIGINS="https://clubhub-yourname.vercel.app"
cd /Users/devinmcnair/Desktop/ClubHub
./start_clubhub.sh
```

Then confirm the Vercel site can load schedules.

## Step 6: Verify Live Health

Check:

- frontend status page:
  - `https://clubhub-yourname.vercel.app/status`
- backend status:
  - `https://abc123.ngrok-free.app/api/status`
- source alerts:
  - `https://abc123.ngrok-free.app/api/source-alerts`
- venue alerts:
  - `https://abc123.ngrok-free.app/api/venue-alerts`

You want:

- `healthy > 0`
- `error = 0`
- `source alerts = 0`
- `venue alerts = 0`

## Step 7: What To Expect

This setup works for friend testing, but it has real fragility:

- if your computer sleeps, the app breaks
- if your home internet changes, the tunnel may break
- if your tunnel URL changes, Vercel env vars must be updated

## What To Do If It Breaks

### Frontend loads but no schedules show

Check:

- is the backend still running?
- is the tunnel still up?
- does `.../api/status` load publicly?
- is `NEXT_PUBLIC_API_URL` correct in Vercel?
- does `CLUBHUB_ALLOWED_ORIGINS` include the Vercel URL?

### Vercel site shows CORS/network errors

Restart backend with the correct allowed origin:

```bash
export CLUBHUB_ALLOWED_ORIGINS="https://clubhub-yourname.vercel.app"
```

### Sync still works locally but public site fails

That usually means:

- backend is healthy
- tunnel or Vercel env config is wrong

## Best Next Step After Friend Testing

Move the backend off your laptop.

At that point:

- keep frontend on Vercel
- move backend + SQLite + sync job to a small VPS
- point `NEXT_PUBLIC_API_URL` at that server

That is the first real stable public setup.
