# Nanosoft AI Backend — Ubuntu Cloud Deployment Guide

Use this guide during a screen-share meeting to deploy the **Nanosoft AI Backend** (FastAPI + WebSocket) on an **Ubuntu** cloud instance. Follow the steps in order; each section has copy-paste commands where possible.

---

## What You’ll Deploy

- **FastAPI app** (chat + WebSocket) — runs on port **8001**
- **Sync runner** (optional) — scheduled via cron for data sync
- **Systemd service** — keeps the API running and restarts on failure

**Dependencies:** Python 3.10+, PostgreSQL (remote), Redis (remote), Google API key. No local DB/Redis install required if you use existing hosted services.

---

## 1. Prerequisites (Before the Meeting)

- Ubuntu server (20.04 or 22.04) with SSH access.
- **IP/hostname** and **SSH key or password** for the client.
- **Git repo URL** (e.g. your GitHub/GitLab URL for the project).
- **Environment values** ready (see Section 5): PostgreSQL, Redis, Google API key, etc. (Keep them in a secure note; do not paste into chat.)

---

## 2. Connect to the Server

Ask the client to open a terminal and SSH in (replace with their IP and user):

```bash
ssh ubuntu@<SERVER_IP>
```

If they use a key:

```bash
ssh -i /path/to/key.pem ubuntu@<SERVER_IP>
```

---

## 3. Initial Server Setup (One-Time)

Run these once on a fresh Ubuntu instance.

### 3.1 Update system and install basics

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y software-properties-common git curl
```

### 3.2 Install Python 3.11 (or 3.10+)

```bash
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev
```

Check:

```bash
python3.11 --version
```

### 3.3 Open firewall for the API (and SSH)

```bash
sudo ufw allow 22/tcp
sudo ufw allow 8001/tcp
sudo ufw enable
sudo ufw status
```

---

## 4. Clone the Project and Set Up the App

### 4.1 Choose app directory

We’ll use `/home/ubuntu/ask-ai` as the project root. If the repo is the **backend only**, clone into a folder that matches the systemd service path below.

**Option A — Repo contains the whole repo (e.g. `ask-ai` with `nanosoft-ai-backend` inside):**

```bash
cd /home/ubuntu
git clone <YOUR_REPO_URL> ask-ai
cd ask-ai/ask-ai/nanosoft-ai-backend
```

**Option B — Repo is only the backend:**

```bash
cd /home/ubuntu
mkdir -p ask-ai/ask-ai
git clone <YOUR_REPO_URL> ask-ai/ask-ai/nanosoft-ai-backend
cd ask-ai/ask-ai/nanosoft-ai-backend
```

Confirm you’re in the backend folder (should see `app/`, `requirements.txt`):

```bash
pwd
ls -la
```

### 4.2 Create virtual environment and install dependencies

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 5. Configure Environment (.env)

The app reads `.env` from the **app** folder: `nanosoft-ai-backend/app/.env`.

### 5.1 Create the file

```bash
nano app/.env
```

### 5.2 Paste the following and replace placeholders with real values

Use the client’s actual PostgreSQL, Redis, and Google API details. **Do not commit this file to Git.**

```env
# --- Cache / memory ---
L1_TTL_SECONDS=120
L2_TTL_SECONDS=120
L1_SIZE_THRESHOLD=5

# --- Google AI ---
GOOGLE_API_KEY=<THEIR_GOOGLE_API_KEY>
GOOGLE_AI_MODEL=gemini-2.5-flash-lite

# --- Redis (e.g. Redis Cloud) ---
REDIS_HOST=<REDIS_HOST>
REDIS_PORT=11355
REDIS_USERNAME=default
REDIS_PASSWORD=<REDIS_PASSWORD>

# --- Session ---
SESSION_TTL_SECONDS=86400
MAX_HISTORY=5

# --- PostgreSQL ---
PG_HOST=<PG_HOST>
PG_PORT=5432
PG_DATABASE=nanosoft_ask
PG_USER=postgres
PG_PASSWORD=<PG_PASSWORD>

# --- Optional: WebSocket timeouts (defaults used if missing) ---
# WS_SESSION_TIMEOUT=120
# WS_PING_INTERVAL=30

# --- Sync (if using sync_runner with cron) ---
SYNC_INTERVAL_MINUTES=20
SYNC_PAGE_SIZE=1000
```

Save and exit: **Ctrl+O**, **Enter**, **Ctrl+X**.

### 5.3 Optional: DATABASE_API_URL

If the app or sync uses an external “database API”, add:

```env
DATABASE_API_URL=<URL_IF_NEEDED>
```

---

## 6. Test Run (Manual)

From the backend directory, with venv activated:

```bash
cd /home/ubuntu/ask-ai/ask-ai/nanosoft-ai-backend
source .venv/bin/activate
uvicorn app.main:chatbot_app --host 0.0.0.0 --port 8001
```

- From the server: `curl http://127.0.0.1:8001/health`
- From a browser: `http://<SERVER_IP>:8001/health`  
  Expected: `{"status":"ok","service":"Facility Management AI Assistant"}`

Stop the server: **Ctrl+C**.

---

## 7. Install Systemd Service (Run on Boot + Auto-Restart)

### 7.1 Paths

The service file assumes:

- **WorkingDirectory:** `/home/ubuntu/ask-ai/ask-ai/nanosoft-ai-backend`
- **ExecStart:** same directory’s `.venv/bin/uvicorn`

If you used a different path in Section 4, adjust the paths in the service file and in the commands below.

### 7.2 Copy service file and enable

```bash
sudo cp /home/ubuntu/ask-ai/ask-ai/nanosoft-ai-backend/deploy/nanosoft-model.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable nanosoft-model
sudo systemctl start nanosoft-model
sudo systemctl status nanosoft-model
```

You should see **active (running)**. Check logs:

```bash
sudo journalctl -u nanosoft-model -f
```

Exit logs: **Ctrl+C**.

### 7.3 If you changed the project path

Edit the service file before copying:

```bash
nano /home/ubuntu/ask-ai/ask-ai/nanosoft-ai-backend/deploy/nanosoft-model.service
```

Update **WorkingDirectory** and **ExecStart** to match your actual path, then run the `sudo cp` and `systemctl` commands again.

---

## 8. Optional: Sync Runner with Cron

If the client needs the **sync_runner** (e.g. every 20 minutes):

```bash
crontab -e
```

Add (adjust path if different):

```cron
*/20 * * * * cd /home/ubuntu/ask-ai/ask-ai/nanosoft-ai-backend && .venv/bin/python app/sync_runner.py >> /home/ubuntu/sync_runner.log 2>&1
```

Save and exit. Check after 20 minutes:

```bash
tail -50 /home/ubuntu/sync_runner.log
```

---

## 9. Optional: Nginx Reverse Proxy (Port 80 / HTTPS)

If the client wants the API on port 80 or behind HTTPS:

### 9.1 Install Nginx

```bash
sudo apt install -y nginx
```

### 9.2 Create config (replace `your-domain.com` or use server IP)

```bash
sudo nano /etc/nginx/sites-available/nanosoft-ai
```

Paste (replace `your-domain.com` and optionally uncomment WebSocket lines if needed):

```nginx
server {
    listen 80;
    server_name your-domain.com;   # or server IP

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # WebSocket support
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

Enable and test:

```bash
sudo ln -s /etc/nginx/sites-available/nanosoft-ai /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

Open: `http://your-domain.com/health` (or `http://<SERVER_IP>/health`).

### 9.3 HTTPS with Let’s Encrypt (optional)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

Follow prompts. Certbot will adjust Nginx for HTTPS.

---

## 10. Post-Deploy Checklist

- [ ] `http://<SERVER_IP>:8001/health` (or via Nginx) returns `{"status":"ok",...}`  
- [ ] WebSocket URL: `ws://<SERVER_IP>:8001/ws/chat` (or `wss://` if using Nginx + SSL)  
- [ ] `.env` is in `app/.env` and not committed to Git  
- [ ] `sudo systemctl status nanosoft-model` shows **active (running)**  
- [ ] If using cron sync: `tail sync_runner.log` shows no errors after one run  

---

## 11. Useful Commands (For the Client)

| Task | Command |
|------|--------|
| View API logs | `sudo journalctl -u nanosoft-model -f` |
| Restart API | `sudo systemctl restart nanosoft-model` |
| Stop API | `sudo systemctl stop nanosoft-model` |
| Start API | `sudo systemctl start nanosoft-model` |
| Sync runner log | `tail -100 /home/ubuntu/sync_runner.log` |

---

## 12. Security Reminder

- **Do not** commit `app/.env` or share it in chat/email.  
- Prefer **SSH keys** over passwords for SSH.  
- Keep **firewall** enabled and only open ports you need (e.g. 22, 8001 or 80/443).  
- Rotate **PostgreSQL**, **Redis**, and **Google API** credentials if they were ever exposed.

---

**End of deployment guide.** Use Sections 1–7 for a minimal working deploy; add 8–9 as needed for sync and Nginx/HTTPS.
