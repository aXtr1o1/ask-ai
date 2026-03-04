# Deploy — systemd service files

## Testing vs Production

| Environment | Backend | Frontend |
|-------------|---------|----------|
| **Testing** | Backend only (`nanosoft-model.service`) | Not deployed |
| **Production** | `nanosoft-model-production.service` | `nanosoft-frontend-production.service` |

---

## Backend (FastAPI)

| File | Environment | User | Path |
|------|-------------|------|------|
| **nanosoft-model.service** | Testing / CI-CD | `ubuntu` | `/home/ubuntu/ask-ai/ask-ai/nanosoft-ai-backend` |
| **nanosoft-model-production.service** | Production | `deploy` | `/var/www/html/ask-ai/nanosoft-ai-backend` |

- **Testing instance:** use only `nanosoft-model.service` (CI/CD deploys backend here; no frontend).
- **Production instance:** use `nanosoft-model-production.service`; ensure the `deploy` user exists and the app is under `/var/www/html/ask-ai/`.

### Production backend install

```bash
sudo cp nanosoft-ai-backend/deploy/nanosoft-model-production.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable nanosoft-model-production
sudo systemctl start nanosoft-model-production
sudo systemctl status nanosoft-model-production
```

Logs: `journalctl -u nanosoft-model-production -f`

---

## Frontend (Next.js)

| File | Environment | User | Path |
|------|-------------|------|------|
| **nanosoft-frontend.service** | Testing (optional) | `ubuntu` | `/home/ubuntu/ask-ai/ask-ai/nanosoft-ai-frontend` |
| **nanosoft-frontend-production.service** | Production | `deploy` | `/var/www/html/ask-ai/nanosoft-ai-frontend` |

Frontend is **not** deployed on the testing instance; only the production instance runs the frontend.

The production frontend service uses **nvm** (Node 20) and runs Next.js on **port 4000** (`npm run start -- -p 4000`). Ensure nvm is installed for the `deploy` user and Node 20 is installed (`nvm install 20`). If the deploy user’s home is not `/home/deploy`, edit the service file and set `NVM_DIR` to the correct path (e.g. `~deploy/.nvm`).

### Production frontend install

```bash
sudo cp nanosoft-ai-backend/deploy/nanosoft-frontend-production.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable nanosoft-frontend-production
sudo systemctl start nanosoft-frontend-production
sudo systemctl status nanosoft-frontend-production
```

Logs: `journalctl -u nanosoft-frontend-production -f`
