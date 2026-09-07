# lawkey.ai.kr AWS/Cloudflare Deployment Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Serve Lawkey AI at `lawkey.ai.kr` from a stable AWS origin without depending on a temporary `trycloudflare.com` tunnel.

**Architecture:** Preferred path is AWS Seoul EC2 running Lawkey under `systemd`, with a persistent Cloudflare named Tunnel routing `lawkey.ai.kr` directly to `http://127.0.0.1:8037`. Nginx is an optional fallback only for a public Elastic IP origin; it is not the default path because the buylow lesson was to keep the public route same-origin and avoid extra stale proxy layers.

**Tech Stack:** Expo static web export, FastAPI/Uvicorn backend, Python venv, Node/npm, systemd, Cloudflare named Tunnel/DNS, AWS EC2/EBS. Optional fallback: Nginx reverse proxy.

---

### Task 1: Confirm Domain Control

**Files:**
- Reference: `deploy/systemd/lawkey-cloudflared.service`

**Steps:**
1. Add `lawkey.ai.kr` as a Cloudflare zone if it is a separately delegated `.kr` third-level domain.
2. At the domain registrar, change `lawkey.ai.kr` nameservers to the two nameservers Cloudflare gives for the zone.
3. Preferred: create a Cloudflare named Tunnel public hostname:
   - Hostname: `lawkey.ai.kr`
   - Service: `http://127.0.0.1:8037`
   - Also add `www.lawkey.ai.kr` if needed.
4. Cloudflare will create the tunnel-backed DNS record, or create a CNAME to `<tunnel-uuid>.cfargotunnel.com`.
5. Elastic IP fallback only: create `A @ <Elastic IP>` and `CNAME www lawkey.ai.kr`.
6. Verify DNS returns an address for `lawkey.ai.kr`.

**Current Cloudflare state (2026-04-13 KST):**
- Correct zone created: `lawkey.ai.kr`, zone id `90ea2537dea55f566c9d13917a19c286`, status `active`.
- Cloudflare assigned nameservers:
  - `keanu.ns.cloudflare.com`
  - `sydney.ns.cloudflare.com`
- Previous/original nameservers observed by Cloudflare:
  - `jewel.ns.cloudflare.com`
  - `oswald.ns.cloudflare.com`
- Named tunnel created: `lawkey-prod`, tunnel id `ee9900d1-e7fb-4ffc-9262-cb876927bbd4`, status `healthy` while the AWS connector is running.
- Tunnel ingress configured:
  - `lawkey.ai.kr` -> `http://127.0.0.1:8037`
  - `www.lawkey.ai.kr` -> `http://127.0.0.1:8037`
- DNS records created:
  - proxied `CNAME lawkey.ai.kr -> ee9900d1-e7fb-4ffc-9262-cb876927bbd4.cfargotunnel.com`
  - proxied `CNAME www.lawkey.ai.kr -> ee9900d1-e7fb-4ffc-9262-cb876927bbd4.cfargotunnel.com`
- Local tunnel token saved outside the repo at `~/.secrets/lawkey-cloudflared-token`.
- External DNS now returns the correct Cloudflare nameservers and proxied `A`/`AAAA` records.
- `http://lawkey.ai.kr/api/health`, `https://lawkey.ai.kr/api/health`, and both `www` variants return `{"status":"ok"}` from the AWS origin connector.
- AWS production origin is provisioned and active:
  - `i-0ad8fda1d5cf03152` (`t3a.large`, 100GB gp3, `43.200.191.87`)
  - security group `sg-0639431e2a59e837c` (SSH from admin `/32` only)
  - `lawkey.service` and `lawkey-cloudflared.service` both enabled/active.
- WSL bridge connector was stopped after cutover; traffic now comes through AWS cloudflared.
- Gemini key provisioning on AWS is now applied (`GEMINI_API_KEYS` populated; scheduler check showed `keyCount=10` on verification job).
- Remaining validation task is a full real-domain E2E completion run without manual cancellation.
- Historical mistake: an earlier pass created `law.ai.kr` zone id `82ded1d42902283b15eb5254495a77c5` with `jewel.ns.cloudflare.com` and `oswald.ns.cloudflare.com`. Do not use it as the Lawkey production domain unless the user explicitly changes scope.

### Task 2: Provision AWS Origin

**Files:**
- Reference: `deploy/systemd/lawkey.service`
- Reference: `deploy/systemd/lawkey-cloudflared.service`
- Reference: `deploy/lawkey.env.example`

**Steps:**
1. Use Seoul region.
2. Do not reuse the existing `buylow-prod` instance for Lawkey without resizing: it has only about 11GB free and the Lawkey precedent database directory is about 11GB.
3. Minimum origin shape: Ubuntu 24.04, 8GB RAM, 60GB gp3 EBS.
4. Safer origin shape for concurrent document jobs: 16GB RAM, 80GB gp3 EBS.
5. Security group for preferred tunnel path:
   - SSH `22` only from the admin IP.
   - No inbound HTTP/HTTPS required; `cloudflared` makes outbound connections.
6. Security group for Elastic IP fallback:
   - SSH `22` only from the admin IP.
   - HTTP `80` and HTTPS `443` from the public internet or Cloudflare IP ranges.

**Execution status:** done (2026-04-13). One post-cutover task remains outside provisioning: set production Gemini keys in `/srv/lawkey/shared/lawkey.env`.

### Task 3: Package Lawkey

**Files:**
- Run: `scripts/deploy/build-lawkey-release.sh`

**Steps:**
1. Run `scripts/deploy/build-lawkey-release.sh`.
2. Confirm the archive path printed under `.tmp/releases/`.
3. Copy the archive to the EC2 host.

### Task 4: Install Lawkey on EC2

**Files:**
- Run on EC2: `scripts/deploy/install-lawkey-release-on-ubuntu.sh`
- Install: `deploy/systemd/lawkey.service`
- Install: `deploy/systemd/lawkey-cloudflared.service`
- Optional fallback: `deploy/nginx/lawkey.ai.kr.conf`
- Configure: `/srv/lawkey/shared/lawkey.env`

**Steps:**
1. Run the installer with the release archive path.
2. Copy the runtime dependency tree:
   - `/srv/lawkey/work16/scripts/legal_evidence_rag.py`
   - `/srv/lawkey/work16/scripts/precedent_search_index.py`
   - `/srv/lawkey/work16/저장파일/unified_precedent_db_2026-04-10_run3/precedents.sqlite3`
3. Fill `/srv/lawkey/shared/lawkey.env` with the Gemini key set and exact Lawkey paths.
4. Put the Cloudflare named tunnel token in `/srv/lawkey/shared/cloudflared.token` with mode `600`.
5. Start:
   - `sudo systemctl enable --now lawkey.service`
   - `sudo systemctl enable --now lawkey-cloudflared.service`
6. Verify:
  - `curl -fsS http://127.0.0.1:8037/api/health`
   - `curl -fsS http://lawkey.ai.kr/api/health`
7. Optional nginx fallback:
   - `LAWKEY_INSTALL_NGINX=1 scripts/deploy/install-lawkey-release-on-ubuntu.sh <archive>`
   - `sudo systemctl reload nginx`
   - `curl -fsS http://127.0.0.1/api/health -H 'Host: lawkey.ai.kr'`

### Task 5: Cut Over Cloudflare

**Files:**
- Reference: `deploy/systemd/lawkey-cloudflared.service`
- Optional fallback: `deploy/nginx/lawkey.ai.kr.conf`

**Steps:**
1. Preferred: point the Cloudflare public hostname to the named tunnel service `http://127.0.0.1:8037`.
2. Confirm `http://lawkey.ai.kr/api/health` returns `{"status":"ok"}`.
3. HTTPS is handled at the Cloudflare edge for the named tunnel path. No Nginx TLS layer is required.
4. Elastic IP fallback only:
   - Point Cloudflare DNS to the Elastic IP.
   - Use Nginx 443 with a real origin certificate and Cloudflare SSL mode `Full (strict)`.
5. Run browser E2E on the real domain:
   - Ask a question.
   - Continue to `고소장 작성해줘`.
   - Select `고소장 프리셋`.
   - Answer required questions.
   - Confirm final document exports and preview render.

### Task 6: Multiple Domains/Systems

**Files:**
- Reference: Cloudflare public hostname routes for the named tunnel
- Optional fallback: Nginx server blocks under `/etc/nginx/sites-enabled/`
- Reference: systemd unit per app

**Steps:**
1. Run each system on a separate localhost port, for example:
   - Buylow: `127.0.0.1:4000`
   - Lawkey: `127.0.0.1:8037`
2. Preferred Cloudflare tunnel path: add one public hostname route per domain/service.
3. Optional Elastic IP fallback: add one Nginx `server_name` block per domain.
4. Keep one `systemd` unit and one release directory per system.
5. Do not share a small 2GB/19GB EC2 instance for Buylow and Lawkey; use separate or resized infrastructure.
