# Frontend Setup on Ubuntu Instance

Use this guide to deploy the **Nanosoft AI Frontend** (Next.js) on the same Ubuntu instance as the backend. Follow the steps in order.

---

## What You’ll Deploy

- **Next.js app** — runs on port **3000**
- **Systemd service** — keeps the app running and restarts on failure

**Prerequisites:** Backend API already running (e.g. on port 8001). The frontend needs `NEXT_PUBLIC_API_BASE_URL` pointing to that API.

---

## 1. Prerequisites

- Ubuntu server (20.04 or 22.04) with SSH access.
- Repo already cloned (e.g. under `/home/ubuntu/ask-ai`) so that the frontend path is `/home/ubuntu/ask-ai/ask-ai/nanosoft-ai-frontend`. If your paths differ, adjust the commands and service file below.

---

## 2. Install Node.js (18 or 20 LTS)

Run once on the server.

### Option A — NodeSource (recommended)

```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
node -v   # should show v20.x
npm -v
```

### Option B — NVM (per-user)

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.bashrc   # or reopen terminal
nvm install 20
nvm use 20
node -v
```

If you use NVM, the systemd service must run Node via nvm (e.g. `ExecStart=/home/ubuntu/.nvm/versions/node/v20.x.x/bin/node` and run `next start` from the app directory), or use a wrapper script. For simplicity, Option A is easier with systemd.

---

## 3. Open Firewall for the Frontend

```bash
sudo ufw allow 3000/tcp
sudo ufw status
```

---

## 4. Go to the Frontend Directory

If the repo is already cloned with the full structure:

```bash
cd /home/ubuntu/ask-ai/ask-ai/nanosoft-ai-frontend
```

If not, clone the repo first (same as backend guide):

```bash
cd /home/ubuntu
git clone <YOUR_REPO_URL> ask-ai
cd ask-ai/ask-ai/nanosoft-ai-frontend
```

Confirm you see `package.json`, `app/`:

```bash
pwd
ls -la
```

---

## 5. Install Dependencies and Build

```bash
npm ci
# or: npm install
npm run build
```

If `npm run build` fails, fix any TypeScript or env errors (see Section 6 for env).

---

## 6. Configure Environment

The frontend needs the backend API base URL so it can call the REST API and WebSocket.

Create `.env.local` in the frontend root:

```bash
nano .env.local
```

Add (replace with your backend URL; use the **instance IP or domain** so browsers can reach it):

```env
# Backend API base URL (no trailing slash). Use http or https depending on how you serve the API.
NEXT_PUBLIC_API_BASE_URL=http://<SERVER_IP>:8001
```

Examples:

- Backend on same server, port 8001: `NEXT_PUBLIC_API_BASE_URL=http://YOUR_SERVER_IP:8001`
- Backend behind Nginx with HTTPS: `NEXT_PUBLIC_API_BASE_URL=https://api.yourdomain.com`

Save and exit: **Ctrl+O**, **Enter**, **Ctrl+X**.

**Important:** After changing `.env.local`, run `npm run build` again so Next.js bakes the new value into the client bundle.

---

## 7. Test Run (Manual)

```bash
npm run start
```

- On the server: `curl http://127.0.0.1:3000`
- From a browser: `http://<SERVER_IP>:3000`

Stop with **Ctrl+C**.

---

## 8. Install Systemd Service (Run on Boot + Auto-Restart)

### 8.1 Copy the service file

From the **backend** deploy folder (where the service file lives):

```bash
sudo cp /home/ubuntu/ask-ai/ask-ai/nanosoft-ai-backend/deploy/nanosoft-frontend.service /etc/systemd/system/
```

If your frontend lives elsewhere, edit the service file first (see 8.3).

### 8.2 Enable and start

```bash
sudo systemctl daemon-reload
sudo systemctl enable nanosoft-frontend
sudo systemctl start nanosoft-frontend
sudo systemctl status nanosoft-frontend
```

You should see **active (running)**. Logs:

```bash
sudo journalctl -u nanosoft-frontend -f
```

### 8.3 If your paths are different

Edit the service file before copying:

```bash
nano /home/ubuntu/ask-ai/ask-ai/nanosoft-ai-backend/deploy/nanosoft-frontend.service
```

Update **WorkingDirectory** and **ExecStart** to match your frontend path and Node/npm path. Then run the `sudo cp` and `systemctl` commands again.

---

## 9. After Code or Env Changes

When you pull new frontend code or change `.env.local`:

```bash
cd /home/ubuntu/ask-ai/ask-ai/nanosoft-ai-frontend
git pull
npm ci
npm run build
sudo systemctl restart nanosoft-frontend
```

---

## 10. Optional: Nginx in Front of Frontend and Backend

To serve both on port 80 (and optionally HTTPS):

- **Frontend:** `http://your-domain.com` → proxy to `http://127.0.0.1:3000`
- **Backend:** `http://your-domain.com/api` → proxy to `http://127.0.0.1:8001`

Then set `NEXT_PUBLIC_API_BASE_URL=https://your-domain.com/api` (or `http://...`) so the browser talks to the same origin.

Example Nginx snippet for the frontend:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 11. Post-Setup Checklist

- [ ] `http://<SERVER_IP>:3000` loads the chat UI.
- [ ] Chat/WebSocket works (backend must be reachable at `NEXT_PUBLIC_API_BASE_URL`).
- [ ] `sudo systemctl status nanosoft-frontend` shows **active (running)**.
- [ ] `.env.local` is not committed to Git.

---

## 12. Useful Commands

| Task | Command |
|------|--------|
| View frontend logs | `sudo journalctl -u nanosoft-frontend -f` |
| Restart frontend | `sudo systemctl restart nanosoft-frontend` |
| Stop frontend | `sudo systemctl stop nanosoft-frontend` |
| Start frontend | `sudo systemctl start nanosoft-frontend` |

---

**End of frontend setup.** For backend deployment, see **UBUNTU_DEPLOYMENT_GUIDE.md**.
