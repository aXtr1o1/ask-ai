# CI/CD setup: Frontend tests + Backend deploy to AWS t2.small

## What the workflow does

- **CI**: On every push/PR, runs **frontend tests only** (Node 18, `npm test` in `nanosoft-ai-frontend`).
- **CD**: On push to `main` or `master`, after tests pass, deploys **backend only** to your t2.small EC2 via SSH (git pull + venv + restart).

Frontend is not deployed; only the backend is deployed to EC2.

---

## 1. One-time setup on the EC2 (t2.small)

SSH into the instance and run:

```bash
# Install git and Python 3.11 if needed
sudo apt update
sudo apt install -y git python3.11 python3.11-venv python3-pip

# Clone the repo (use your real repo URL; HTTPS is fine for read-only deploy)
sudo mkdir -p /home/ubuntu/ask-ai
sudo chown ubuntu:ubuntu /home/ubuntu/ask-ai
cd /home/ubuntu/ask-ai
git clone https://github.com/YOUR_ORG/ask-ai.git .

# Backend venv and deps
cd nanosoft-ai-backend
python3.11 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

# Create .env with URL, KEY, etc. (copy from your local or set in GitHub / Parameter Store)
nano .env   # add URL=..., KEY=..., etc.

# Install and enable systemd service (path must match your app location)
sudo cp deploy/nanosoft-backend.service /etc/systemd/system/
# If your app is not in /home/ubuntu/ask-ai, edit the service file paths first:
# sudo nano /etc/systemd/system/nanosoft-backend.service
sudo systemctl daemon-reload
sudo systemctl enable nanosoft-backend
sudo systemctl start nanosoft-backend
sudo systemctl status nanosoft-backend
```

Ensure port **8000** is open in the EC2 security group (inbound TCP 8000 from 0.0.0.0/0 or your load balancer).

---

## 2. GitHub repository secrets

In the repo: **Settings → Secrets and variables → Actions**, add:

| Secret           | Description |
|------------------|-------------|
| `EC2_HOST`       | EC2 public IP or DNS (e.g. `ec2-xx-xx-xx-xx.compute.amazonaws.com`) |
| `EC2_USER`       | SSH user (usually `ubuntu`) |
| `EC2_SSH_KEY`    | Full contents of the **private** key (.pem) used to **SSH into the EC2** (this is the key you added; it is not used for Git). Paste the **entire** key including `-----BEGIN ... PRIVATE KEY-----` and `-----END ... PRIVATE KEY-----` and keep newlines. |
| `EC2_APP_PATH`   | Path to the repo on the server (e.g. `/home/ubuntu/ask-ai`) |
| `GH_DEPLOY_TOKEN` | **(Private repo, Option B only)** A GitHub Personal Access Token (or fine-grained token) with `repo` read scope. The workflow uses it so EC2 can pull via HTTPS without a deploy key. |

**If the deploy step fails:** The workflow has a "Verify deploy secrets" step. If any of `EC2_HOST`, `EC2_USER`, `EC2_SSH_KEY`, or `EC2_APP_PATH` are missing, the run will fail there with a clear error. If the SSH step itself fails, check: EC2 security group allows SSH (port 22) from the internet or from GitHub’s IPs; `EC2_SSH_KEY` is the full PEM with correct newlines; `EC2_HOST` is the public IP or DNS of the instance.

### Private repo: how EC2 pulls from GitHub

The key in `EC2_SSH_KEY` is only for GitHub Actions to SSH into your t2.small. The **EC2 instance itself** must be able to pull from your **private** repo when the workflow runs `git fetch` / `git reset`. Use one of these:

**Option A – Deploy key (SSH on EC2)**  
1. On your EC2: `ssh-keygen -t ed25519 -C "deploy" -f ~/.ssh/github_deploy -N ""`  
2. Add the **public** key to the repo: **Settings → Deploy keys → Add deploy key** (read-only is enough).  
3. On EC2, set the Git remote to SSH and use that key:
   ```bash
   cd /home/ubuntu/ask-ai
   git remote set-url origin git@github.com:YOUR_ORG/ask-ai.git
   # Ensure ssh uses the deploy key for github.com (e.g. in ~/.ssh/config)
   ```
   Example `~/.ssh/config` on EC2:
   ```
   Host github.com
     HostName github.com
     User git
     IdentityFile ~/.ssh/github_deploy
     IdentitiesOnly yes
   ```

**Option B – Token in GitHub Secrets (no key on EC2)**  
1. Create a **Personal Access Token** (or fine-grained token) with `repo` (read) scope.  
2. Add it as a repository secret: **Settings → Secrets → Actions** → `GH_DEPLOY_TOKEN`.  
3. The workflow is set up to use this: it will configure the remote on EC2 to use `https://x-access-token:TOKEN@github.com/...` before each `git fetch`, so the server can pull without a deploy key.

---

## 3. Deploy flow

1. **Push to `Testing`** (or open a PR targeting `Testing`) → workflow runs.
2. **test-frontend** always runs: installs frontend deps and runs `npm test`.
3. **deploy-backend** runs only on **push** to `Testing` (not on PRs):
   - SSHs into EC2, `cd EC2_APP_PATH`
   - Updates Git remote (if `GH_DEPLOY_TOKEN` is set), then `git fetch` and `git checkout -B Testing origin/Testing`
   - In `nanosoft-ai-backend`: venv, `pip install -r requirements.txt`, `sudo systemctl restart nanosoft-backend`

---

## 4. How to test the Actions

You do **not** push from EC2. You push from your **local machine** (or another dev); that triggers the workflow and the deploy step updates EC2.

**From your local (after you’ve pulled the old Testing code on EC2):**

1. On your machine, switch to `Testing` and push any new commit:
   ```bash
   git checkout Testing
   git pull origin Testing
   # make a small change if you want, or just re-push
   git push origin Testing
   ```
2. On GitHub: **Actions** tab → open the run that started for the push.
3. You should see:
   - **test-frontend** run (and turn green when frontend tests pass).
   - **deploy-backend** run only if the trigger was a **push** (not a PR). It will SSH to EC2, update code to latest `Testing`, and restart the backend.
4. To test **without** deploying: open a **Pull Request** into `Testing`. Only **test-frontend** will run; **deploy-backend** is skipped for PRs.

**After a successful deploy:** SSH to EC2 and check:
   ```bash
   cd /home/ubuntu/ask-ai && git log -1 --oneline
   sudo systemctl status nanosoft-backend
   curl -s http://localhost:8000/docs  # or your health endpoint
   ```

---

## 5. Optional: deploy via rsync (no git on server)

If you prefer not to clone the repo on EC2, you can deploy by rsync from the runner. In `.github/workflows/main.yml`:

- Comment out or remove the **Deploy backend to EC2** step that uses `appleboy/ssh-action`.
- Uncomment the **deploy-backend-rsync** job and adjust the steps so the only deploy job is the rsync one.

Then on the server you only need:

- `EC2_APP_PATH` = directory where the backend should live (e.g. `/home/ubuntu/app`).
- Python 3.11, venv, and the systemd unit updated so `WorkingDirectory` and paths point to that directory (e.g. `/home/ubuntu/app/nanosoft-ai-backend`).

---

## 6. Frontend tests only

Backend tests are **not** run in this workflow; only frontend tests are. To run backend tests again in CI, add a job that uses `actions/setup-python` and runs `pytest` in `nanosoft-ai-backend`.
