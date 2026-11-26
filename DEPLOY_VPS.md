# DEPLOY_VPS — ek fresh Ubuntu 24.04 VPS par demo college live karna

Target setup: **1 VPS, 2 GB RAM, Ubuntu 24.04 LTS**, ek deployment = ek college.
Yahan demo college `demo.<your-domain>` par chalega, Postgres + gunicorn + Caddy (HTTPS),
systemd services, daily encrypted backup.

> **Is doc ke baare mein honest baat**
> Commands aur file contents repo ke asli code se banaye gaye hain (`scripts/provision_server.sh`,
> `scripts/backup_db.sh`, `scripts/restore_db.sh`, `college_ums/settings.py`, `deploy/Caddyfile`,
> `manage.py diagnose_college`, `seed_demo`, `create_college`). Lekin **is environment me
> VPS / sudo / systemd / Docker nahi hai**, isliye:
> - `apt`, `ufw`, `fail2ban`, `caddy`, `systemd`, `cron` ke steps **run nahi kiye gaye** —
>   ye standard Ubuntu commands hain, par pehli baar tumhare server par hi sach me chalenge.
> - App ke andar ka hissa (`provision_server.sh`, `migrate`, `seed_demo`, `restore_db.sh`,
>   `diagnose_college`, `/healthz/`, `/readyz/`) locally verify kiya gaya hai — wahi steps
>   neeche "Verified locally" ke roop me mark hain.
> - Jahan "**manual check**" likha hai, wo insaan ko server par dekhna hoga.

---

## 0. Placeholders — pehle ye set karo

Poori guide me ye teen naam use hue hain. Apne value likho aur **yahi shell session** me
export karo (secret kuch bhi file me nahi likhna):

```bash
export DOMAIN="demo.example.com"        # demo college ka domain (DNS pehle se point ho)
export UMS_USER="ums"                   # non-root linux user
export UMS_SLUG="demo"                  # deployment ka slug (folder + db + service name)
```

Aage `$DOMAIN`, `$UMS_USER`, `$UMS_SLUG` hi use honge. Note kar lo: **systemd unit name
`ums-$UMS_SLUG.service`** banega, DB name `ums_$UMS_SLUG`.

---

## 1. Server hardening (root/sudo se, ek hi baar)

### 1.1 Non-root user + SSH key

Apne **laptop** se (root password se pehli baar login karke):

```bash
# laptop -> server (root). Isse root ka key bhi set ho jayega, wo baad me band karenge.
ssh-copy-id root@"$DOMAIN"
ssh root@"$DOMAIN"
```

Server par:

```bash
# 1) naya non-root user + sudo
adduser --disabled-password --gecos "" "$UMS_USER"
usermod -aG sudo "$UMS_USER"

# 2) uska SSH key (laptop ki public key) — laptop se: ssh-copy-id $UMS_USER@$DOMAIN
#    server par manually karne ke liye authorised_keys banao:
install -d -m 700 -o "$UMS_USER" -g "$UMS_USER" "/home/$UMS_USER/.ssh"
# laptop se: cat ~/.ssh/id_ed25519.pub   -> ye line server par paste karo
nano "/home/$UMS_USER/.ssh/authorized_keys"
chown "$UMS_USER":"$UMS_USER" "/home/$UMS_USER/.ssh/authorized_keys"
chmod 600 "/home/$UMS_USER/.ssh/authorized_keys"

# 3) sudo bina password (deploy scripts ke liye zaroori nahi, par aasan hai)
echo "$UMS_USER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/90-$UMS_USER
chmod 440 /etc/sudoers.d/90-$UMS_USER
```

**Test (naya terminal, root band karke):**

```bash
ssh "$UMS_USER"@"$DOMAIN" 'whoami && sudo -n true && echo sudo-ok'
# expected: ums / sudo-ok
```

Key login chalne ke **baad hi** password login band karo (warna apne aap ko lock out kar loge).

### 1.2 Password login band + root login band

```bash
sudo tee /etc/ssh/sshd_config.d/99-hardening.conf >/dev/null <<'EOF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
EOF
sudo sshd -t && sudo systemctl reload ssh
```

**Manual check:** naya terminal kholo, `ssh $UMS_USER@$DOMAIN` chale; `ssh root@$DOMAIN`
refuse ho; `ssh -o PreferredAuthentications=password $UMS_USER@$DOMAIN` "Permission denied" de.

### 1.3 Swap (2 GB RAM par zaroori — build/migrate ke waqt OOM bachata hai)

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h   # Swap line dikhni chahiye
```

### 1.4 Firewall (22/80/443)

```bash
sudo apt-get update
sudo apt-get install -y ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp    comment 'ssh'
sudo ufw allow 80/tcp    comment 'http (ACME + redirect)'
sudo ufw allow 443/tcp   comment 'https'
sudo ufw --force enable
sudo ufw status verbose
```

> 8000 **khula mat rakho** — gunicorn sirf `127.0.0.1:8000` par bind hoga, Caddy proxy karega.

### 1.5 fail2ban (ssh brute force)

```bash
sudo apt-get install -y fail2ban
sudo tee /etc/fail2ban/jail.d/ums.local >/dev/null <<'EOF'
[DEFAULT]
bantime = 1h
findtime = 10m
maxretry = 4

[sshd]
enabled = true
EOF
sudo systemctl enable --now fail2ban
sudo fail2ban-client status sshd
```

### 1.6 Automatic security updates

```bash
sudo apt-get install -y unattended-upgrades apt-listchanges
sudo dpkg-reconfigure -plow unattended-upgrades     # "Yes" chuno
# auto reboot sirf jab zaroori ho, raat 3:30 baje:
sudo tee /etc/apt/apt.conf.d/51ums-autoreboot >/dev/null <<'EOF'
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "03:30";
EOF
systemctl status unattended-upgrades --no-pager
```

### 1.7 Timezone + basic tools

```bash
sudo timedatectl set-timezone Asia/Kolkata
sudo apt-get install -y git curl ca-certificates gnupg rsync htop unattended-upgrades
```

---

## 2. Packages: Python, Postgres, Caddy

### 2.1 Python + build deps

Ubuntu 24.04 par Python **3.12** default hai (project ka deploy target bhi 3.12).

```bash
sudo apt-get install -y python3 python3-venv python3-dev build-essential libpq-dev pkg-config
python3 -V        # 3.12.x
```

### 2.2 PostgreSQL

```bash
sudo apt-get install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql
psql --version    # 16.x
```

DB + user (password **prompt par** daalo, command me mat likho):

```bash
sudo -u postgres psql <<SQL
CREATE ROLE ums_${UMS_SLUG} LOGIN PASSWORD 'CHANGE_ME_STRONG';
CREATE DATABASE ums_${UMS_SLUG} OWNER ums_${UMS_SLUG} ENCODING 'UTF8' TEMPLATE template0;
SQL
```

Password ko `psql` prompt par set karna ho to:

```bash
sudo -u postgres psql -c "CREATE ROLE ums_${UMS_SLUG} LOGIN;"
sudo -u postgres psql -c "\password ums_${UMS_SLUG}"     # interactive
sudo -u postgres psql -c "CREATE DATABASE ums_${UMS_SLUG} OWNER ums_${UMS_SLUG} ENCODING 'UTF8' TEMPLATE template0;"
```

**Test (app user se login):**

```bash
PGPASSWORD='...' psql -h 127.0.0.1 -U ums_${UMS_SLUG} -d ums_${UMS_SLUG} -c 'select current_database(), current_user;'
```

> Local socket auth Ubuntu par `peer` hai; app `127.0.0.1` (TCP + md5/scram) use karega —
> isliye `DB_HOST=127.0.0.1` rakhna, `localhost` nahi.

### 2.3 Caddy (TLS free, auto Let's Encrypt)

```bash
sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
  | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
  | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
sudo apt-get update && sudo apt-get install -y caddy
caddy version
```

(Nginx bhi chalega, par repo ka `deploy/Caddyfile` Caddy ke liye hai — isi liye Caddy
recommended. Nginx use karna ho to `docs/RUNBOOK.md` ka TLS section dekho.)

---

## 3. Private repo clone (deploy key se)

Deployment apne linux user se chalti hai:

```bash
sudo mkdir -p /opt/src && sudo chown "$UMS_USER":"$UMS_USER" /opt/src
sudo -u "$UMS_USER" -H bash -c '
  set -e
  cd /opt/src
  # 1) deploy key (repo-specific, read-only, no passphrase)
  ssh-keygen -t ed25519 -C "ums-deploy-key" -f ~/.ssh/github_deploy -N ""
  echo "--- ye public key GitHub ke Settings > Deploy keys me add karo (Read only) ---"
  cat ~/.ssh/github_deploy.pub
'
```

GitHub par: **repo → Settings → Deploy keys → Add deploy key** → public key paste → *Allow
write access* **tick mat karo** (deploy ko sirf read chahiye).

```bash
sudo -u "$UMS_USER" -H bash -c '
  set -e
  cat >> ~/.ssh/config <<CFG
Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/github_deploy
  IdentitiesOnly yes
CFG
  chmod 600 ~/.ssh/config
  ssh-keyscan -H github.com >> ~/.ssh/known_hosts 2>/dev/null
  cd /opt/src
  git clone git@github.com:<your-org>/<your-repo>.git college_ums
  cd college_ums && git status --short && git log --oneline -1
'
```

**Hardening note:** deploy key ko repo ke andar kabhi copy mat karo; `.env` aur `backups/`
repo me nahi jaate (`.gitignore` me hain).

---

## 4. Provision + demo data + HTTPS

### 4.1 `.env` pehle banao (DB settings ke saath)

`provision_server.sh` `.env` **tabhi** banata hai jab wo maujood na ho — aur `.env` na hone
par wo pehle SQLite par migrate kar deta hai. Isliye Postgres `.env` **pehle** likhte hain,
phir provision chalate hain (taaki seedha Postgres par migrate + college create ho).

```bash
sudo -u "$UMS_USER" -H bash -c "
  set -e
  mkdir -p /opt/ums/$UMS_SLUG
  cp /opt/src/college_ums/.env.example /opt/ums/$UMS_SLUG/.env
  chmod 600 /opt/ums/$UMS_SLUG/.env
"
```

Secrets **generate** karo (screen par print nahi honge, seedha `.env` me jaayenge):

```bash
sudo -u "$UMS_USER" -H bash -c "
  set -e
  ENV=/opt/ums/$UMS_SLUG/.env
  setenv() {  # setenv KEY VALUE  (existing key replace, warna append)
    python3 - \"\$1\" \"\$2\" \"\$ENV\" <<'PY'
import re, sys
key, value, path = sys.argv[1:4]
text = open(path, encoding='utf-8').read()
line = f'{key}={value}'
pat = re.compile(rf'^{re.escape(key)}=.*\$', re.MULTILINE)
text = pat.sub(line, text, count=1) if pat.search(text) else text.rstrip('\n') + '\n' + line + '\n'
open(path, 'w', encoding='utf-8').write(text)
PY
  }
  setenv DEBUG False
  setenv ENVIRONMENT production
  setenv SECRET_KEY \"\$(openssl rand -base64 48 | tr -d '\n')\"
  setenv BACKUP_ENCRYPTION_KEY \"\$(openssl rand -base64 32)\"
  setenv PLATFORM_METRICS_TOKEN \"\$(openssl rand -hex 24)\"
  setenv ALLOWED_HOSTS '$DOMAIN,127.0.0.1,localhost'
  setenv CSRF_TRUSTED_ORIGINS 'https://$DOMAIN'
  setenv COLLEGE_SLUG '$UMS_SLUG'
  setenv COLLEGE_DOMAIN '$DOMAIN'
  setenv PORTAL_URL 'https://$DOMAIN'
  setenv COLLEGE_NAME '\"Demo College\"'
  setenv DB_ENGINE django.db.backends.postgresql
  setenv DB_NAME ums_$UMS_SLUG
  setenv DB_USER ums_$UMS_SLUG
  setenv DB_HOST 127.0.0.1
  setenv DB_PORT 5432
  setenv TRUST_PROXY_HEADERS True
  setenv BACKUP_DIR /opt/ums/$UMS_SLUG/backups
  setenv LOG_FORMAT json
  chmod 600 \$ENV
  echo '.env ready (600)'; grep -c . \$ENV
"
```

**DB_PASSWORD abhi haath se daalo** (secret command line me nahi jaana chahiye):

```bash
sudo -u "$UMS_USER" -H nano /opt/ums/$UMS_SLUG/.env
#   DB_PASSWORD=<jo psql me set kiya tha>
#   COLLEGE_EMAIL / COLLEGE_PHONE / COLLEGE_ADDRESS / PRIMARY_COLOR bhi yahin set karo
```

> **`.env` ka trap (README me bhi likha hai):** inline comment value ka hissa ban jaata hai.
> `DEBUG=False   # prod` likhne par app start hi nahi karega. Comment alag line par rakho.

### 4.2 Provision chalao

```bash
sudo -u "$UMS_USER" -H bash -c '
  cd /opt/src/college_ums
  ./scripts/provision_server.sh '"$UMS_SLUG"' \
      --name "Demo College" \
      --domain '"$DOMAIN"' \
      --plan pro \
      --repo /opt/src/college_ums \
      --demo
'
```

Script kya karta hai (idempotent — fail hone par dobara chala sakte ho, `.env` overwrite
nahi hota): venv → requirements → migrate → `seed_plans` → `compile_translations` →
`collectstatic` → `create_college` → `seed_demo --force` → `diagnose_college`. Aakhir me
exit code deta hai: **0 = ok, 1 = broken, 2 = warnings**.

`--demo` demo data (students/teachers/attendance/marks/fees/notices) daal deta hai. Note:
`seed_demo` `DEBUG=False` par `--force` ke bina refuse karta hai — script wahi flag deta hai.

Login credentials: `create_college` ek **set-password link** print karta hai (koi plaintext
password nahi). Us link se admin ka password set karo, phir `create_college`/admin panel se
demo students ke links export kar sakte ho (`/admin-panel/credentials/export-links/`).

**Manual check:** provision ka output copy karke rakh lo — usme set-password link ek hi baar
milta hai.

### 4.3 gunicorn + qcluster systemd services

Repo me systemd unit files nahi hain; ye do files banao (paths `$UMS_SLUG` ke saath):

```bash
sudo tee /etc/systemd/system/ums-${UMS_SLUG}.service >/dev/null <<EOF
[Unit]
Description=College UMS web (${UMS_SLUG})
After=network.target postgresql.service
Wants=postgresql.service

[Service]
User=${UMS_USER}
Group=${UMS_USER}
WorkingDirectory=/opt/ums/${UMS_SLUG}
EnvironmentFile=/opt/ums/${UMS_SLUG}/.env
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/ums/${UMS_SLUG}/.venv/bin/gunicorn college_ums.wsgi:application \\
    --bind 127.0.0.1:8000 --workers 2 --threads 2 --timeout 60 \\
    --access-logfile - --error-logfile -
Restart=always
RestartSec=3
# thoda extra safety: agar memory leak ho to service khud restart ho jaye
MemoryMax=900M

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/ums-${UMS_SLUG}-worker.service >/dev/null <<EOF
[Unit]
Description=College UMS background jobs (${UMS_SLUG})
After=network.target postgresql.service
Wants=postgresql.service

[Service]
User=${UMS_USER}
Group=${UMS_USER}
WorkingDirectory=/opt/ums/${UMS_SLUG}
EnvironmentFile=/opt/ums/${UMS_SLUG}/.env
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/ums/${UMS_SLUG}/.venv/bin/python manage.py qcluster
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now ums-${UMS_SLUG}.service ums-${UMS_SLUG}-worker.service
systemctl status ums-${UMS_SLUG}.service --no-pager
```

> 2 GB box par `--workers 2 --threads 2` kaafi hai. Load badhe to workers 3–4 karo
> (RAM dekh kar; `MemoryMax=900M` hatana padega).

### 4.4 Caddy (HTTPS) — demo.<domain>

```bash
sudo tee /etc/caddy/Caddyfile >/dev/null <<EOF
${DOMAIN} {
    encode zstd gzip

    header {
        X-Content-Type-Options nosniff
        X-Frame-Options DENY
        Referrer-Policy same-origin
        -Server
    }

    # /media/* Caddy se serve NA karo: uploads me personal data hai, Django login
    # check ke baad serve karta hai (students/views/media.py).
    reverse_proxy 127.0.0.1:8000
}
EOF
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl enable --now caddy
sudo systemctl reload caddy
journalctl -u caddy -n 30 --no-pager      # certificate issue hote hue dekho
```

> DNS ka `A` (aur IPv6 ho to `AAAA`) record `$DOMAIN` → server IP hona chahiye, warna
> Let's Encrypt challenge fail hoga. Port 80 khula hona zaroori hai (HTTP-01).

---

## 5. Background me chalna + reboot ke baad bhi

Upar `enable --now` kar diya hai, iska matlab:

```bash
systemctl is-enabled ums-${UMS_SLUG}.service ums-${UMS_SLUG}-worker.service   # enabled
systemctl is-active  ums-${UMS_SLUG}.service ums-${UMS_SLUG}-worker.service   # active
```

**Reboot test (manual check):**

```bash
sudo reboot
# 2-3 min baad:
ssh "$UMS_USER"@"$DOMAIN" 'systemctl is-active ums-'"$UMS_SLUG"'.service ums-'"$UMS_SLUG"'-worker.service && curl -sS -o /dev/null -w "%{http_code}\n" https://'"$DOMAIN"'/readyz/'
```

Logs:

```bash
journalctl -u ums-${UMS_SLUG}.service -f          # web
journalctl -u ums-${UMS_SLUG}-worker.service -f   # qcluster (mail/notifications)
```

---

## 6. Daily backup cron + ek restore test

### 6.1 Cron (roz 02:30, encrypted, 14 din retention)

`BACKUP_ENCRYPTION_KEY` `.env` me hai; **uski ek copy offline** (password manager) rakho —
uske bina backup restore nahi hoga.

```bash
sudo tee /etc/cron.d/ums-${UMS_SLUG}-backup >/dev/null <<EOF
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin
30 2 * * * ${UMS_USER} cd /opt/ums/${UMS_SLUG} && ./scripts/backup_db.sh >> /var/log/ums-${UMS_SLUG}-backup.log 2>&1
0 7 * * * ${UMS_USER} cd /opt/ums/${UMS_SLUG} && .venv/bin/python manage.py send_error_digest --only-if-errors >> /var/log/ums-${UMS_SLUG}-digest.log 2>&1
EOF
sudo touch /var/log/ums-${UMS_SLUG}-backup.log
sudo chown ${UMS_USER}:${UMS_USER} /var/log/ums-${UMS_SLUG}-backup.log /var/log/ums-${UMS_SLUG}-digest.log
```

Abhi ek backup chala kar dekho:

```bash
sudo -u "$UMS_USER" -H bash -c 'cd /opt/ums/'"$UMS_SLUG"' && ./scripts/backup_db.sh'
ls -lh /opt/ums/$UMS_SLUG/backups | tail -3
```

Backup script **fail loudly** karta hai (missing `pg_dump`/key par empty "valid" file nahi
banata) — isliye output me `OK`/file size zaroor dekho.

### 6.2 Restore test (haan, ek baar karna zaroori)

Live DB par restore mat karo. Ek scratch database banao aur usme restore karke row count
compare karo:

```bash
# 1) scratch DB
sudo -u postgres psql -c "DROP DATABASE IF EXISTS ums_${UMS_SLUG}_restoretest;"
sudo -u postgres psql -c "CREATE DATABASE ums_${UMS_SLUG}_restoretest OWNER ums_${UMS_SLUG};"

# 2) latest backup ka naam
sudo -u "$UMS_USER" -H bash -c 'ls -t /opt/ums/'"$UMS_SLUG"'/backups | head -1'

# 3) restore into the scratch DB (env overrides sirf is command ke liye)
sudo -u "$UMS_USER" -H bash -c '
  cd /opt/ums/'"$UMS_SLUG"'
  FILE=$(ls -t backups | head -1)
  DB_NAME=ums_'"$UMS_SLUG"'_restoretest ENV_FILE=.env ./scripts/restore_db.sh --file "backups/$FILE" --yes
'
```

Script restore ke baad table row counts print karta hai. Unhe live se milao:

```bash
sudo -u "$UMS_USER" -H bash -c 'cd /opt/ums/'"$UMS_SLUG"' && .venv/bin/python manage.py shell -c "
from students.models import *
print(\"live:\", StudentProfile.objects.count(), Attendance.objects.count(), FeePayment.objects.count())
"'
```

**Manual check:** dono numbers same hone chahiye (restore ke baad ek extra ErrorEvent row aa
sakti hai — wo normal hai). Test ke baad scratch DB hata do:

```bash
sudo -u postgres psql -c "DROP DATABASE ums_${UMS_SLUG}_restoretest;"
```

---

## 7. Verification checklist

```bash
# 1) liveness (DB touch nahi karta, auth nahi)
curl -sS https://$DOMAIN/healthz/ ; echo
# expected: {"status": "ok", "environment": "production"}

# 2) readiness (DB + cache)
curl -sS -o /dev/null -w '%{http_code}\n' https://$DOMAIN/readyz/
# expected: 200   (503 = DB/cache down)

# 3) HTTP -> HTTPS redirect
curl -sSI http://$DOMAIN/ | head -3

# 4) deployment diagnosis (~19 checks; exit 0 ok / 1 broken / 2 warnings)
sudo -u "$UMS_USER" -H bash -c 'cd /opt/ums/'"$UMS_SLUG"' && .venv/bin/python manage.py diagnose_college '"$DOMAIN"

# 5) services + TLS
systemctl is-active ums-${UMS_SLUG} ums-${UMS_SLUG}-worker caddy postgresql
curl -sSI https://$DOMAIN/login/ | grep -Ei 'HTTP/|strict-transport|x-frame|content-type'

# 6) version jo chal raha hai
sudo -u "$UMS_USER" git -C /opt/ums/$UMS_SLUG log --oneline -1 2>/dev/null || \
  echo '(code provision ne copy kiya hai; /opt/src/college_ums me git hai)'
```

Role-wise login (**manual check**, browser se):

| Role | URL | Kaise |
|---|---|---|
| Admin / staff | `https://$DOMAIN/login/` | `create_college` ne jo set-password link diya |
| Teacher | `https://$DOMAIN/login/` | demo seed ka teacher (credentials seed output/README me) |
| Student | `https://$DOMAIN/login/` | demo student; pehli baar set-password link se |
| Parent | `https://$DOMAIN/parent/` | `/admin-panel/students/<id>/` se `add_guardian` |
| Anonymous | `https://$DOMAIN/` | landing page, login button |

Phone se: mobile data par (Wi-Fi off) `https://$DOMAIN/login/` kholo — HTTPS valid, login
form mobile par ek column me, sidebar drawer (☰) khulta ho.

Agar demo ke credentials bhool gaye:

```bash
sudo -u "$UMS_USER" -H bash -c 'cd /opt/ums/'"$UMS_SLUG"' && .venv/bin/python manage.py shell -c "
from django.contrib.auth.models import User
print([u.username for u in User.objects.filter(is_superuser=True)])
"'
# password reset: admin panel -> students -> \"set password link\" export, ya
# .venv/bin/python manage.py changepassword <username>
```

---

## 8. Update kaise karein / rollback

### 8.1 Update (naya code)

```bash
# 1) pehle backup (rollback ka bharosa isi par hai)
sudo -u "$UMS_USER" -H bash -c 'cd /opt/ums/'"$UMS_SLUG"' && ./scripts/backup_db.sh'

# 2) source repo update + tag chuno
sudo -u "$UMS_USER" -H bash -c 'cd /opt/src/college_ums && git fetch --tags --prune && git tag --sort=-creatordate | head -5'

export NEW_TAG="v1.1.0-ui"       # jo tag deploy karna hai
sudo -u "$UMS_USER" -H bash -c "cd /opt/src/college_ums && git checkout -f $NEW_TAG && git log --oneline -1"

# 3) code deployment folder me sync (repo ke apne provision jaisa hi; .env safe rehta hai)
sudo -u "$UMS_USER" -H bash -c '
  set -e
  cd /opt/src/college_ums
  rsync -a --delete \
    --exclude=.venv --exclude=.git --exclude=media --exclude=staticfiles \
    --exclude=db.sqlite3 --exclude=backups --exclude=deployments --exclude=.env \
    ./ /opt/ums/'"$UMS_SLUG"'/
'

# 4) dependencies + migrate + static + restart
sudo -u "$UMS_USER" -H bash -c '
  set -e
  cd /opt/ums/'"$UMS_SLUG"'
  .venv/bin/pip install -q -r requirements.txt
  .venv/bin/python manage.py migrate --noinput
  .venv/bin/python manage.py compile_translations
  .venv/bin/python manage.py collectstatic --noinput
  .venv/bin/python manage.py check --deploy
'
sudo systemctl restart ums-${UMS_SLUG}.service ums-${UMS_SLUG}-worker.service

# 5) verify
curl -sS -o /dev/null -w 'readyz %{http_code}\n' https://$DOMAIN/readyz/
sudo -u "$UMS_USER" -H bash -c 'cd /opt/ums/'"$UMS_SLUG"' && .venv/bin/python manage.py diagnose_college '"$DOMAIN"
```

> `staticfiles` par purane hashed files reh jaate hain — usse koi dikkat nahi.
> `collectstatic` ke baad restart zaroori hai (manifest reload hota hai).

### 8.2 Rollback

```bash
export OLD_TAG="v1.0.0"      # pichla tag
sudo -u "$UMS_USER" -H bash -c "
  cd /opt/src/college_ums && git checkout -f $OLD_TAG
  rsync -a --delete --exclude=.venv --exclude=.git --exclude=media --exclude=staticfiles \
    --exclude=db.sqlite3 --exclude=backups --exclude=deployments --exclude=.env \
    ./ /opt/ums/$UMS_SLUG/
  cd /opt/ums/$UMS_SLUG && .venv/bin/python manage.py collectstatic --noinput
"
sudo systemctl restart ums-${UMS_SLUG}.service ums-${UMS_SLUG}-worker.service
curl -sS -o /dev/null -w 'readyz %{http_code}\n' https://$DOMAIN/readyz/
```

**Important:** code rollback **migrations ko undo nahi karta**. Agar naye release ne
migration add ki thi aur tum data bhi purana chahte ho, to backup restore karo:

```bash
sudo -u "$UMS_USER" -H bash -c '
  cd /opt/ums/'"$UMS_SLUG"'
  ./scripts/restore_db.sh --file backups/<file>.sql.gz.enc --yes
'
sudo systemctl restart ums-${UMS_SLUG}.service ums-${UMS_SLUG}-worker.service
```

---

## 9. Common errors aur fix

| Lakshan | Wajah | Fix |
|---|---|---|
| `502 Bad Gateway` (Caddy) | gunicorn band hai / port galat | `systemctl status ums-$UMS_SLUG`; `journalctl -u ums-$UMS_SLUG -n 50`; `.env` me `ALLOWED_HOSTS` me domain hai? |
| Site 301 → `https://localhost` | `SECURE_SSL_REDIRECT` + galat `ALLOWED_HOSTS`/`COLLEGE_DOMAIN` | `.env` me `COLLEGE_DOMAIN=$DOMAIN`, `ALLOWED_HOSTS` me domain, `CSRF_TRUSTED_ORIGINS=https://$DOMAIN` |
| `DisallowedHost` | Host header allow nahi | wahi fix; phir `systemctl restart` |
| `CSRF verification failed` (login par) | `CSRF_TRUSTED_ORIGINS` missing | `https://$DOMAIN` add karo, restart |
| App start hi nahi hota, `SECRET_KEY` error | placeholder/`django-insecure…` key ya inline comment | `SECRET_KEY` regenerate, comment alag line par |
| `psycopg`/DB connection refused | Postgres band ya `DB_HOST=localhost` | `systemctl status postgresql`; `DB_HOST=127.0.0.1` |
| `permission denied for schema public` | DB owner galat | `sudo -u postgres psql -c 'ALTER DATABASE ums_$UMS_SLUG OWNER TO ums_$UMS_SLUG;'` |
| Static files 404 / CSS nahi | `collectstatic` nahi chala | `manage.py collectstatic --noinput` + restart |
| Logout/login loop | cookies `Secure` hain par HTTP par test kar rahe ho | production me sirf HTTPS use karo (ya staging par `SESSION_COOKIE_SECURE=False`) |
| Certificate issue nahi hua | DNS galat / port 80 band | `dig +short $DOMAIN`, `ufw status`, `journalctl -u caddy -n 50` |
| `seed_demo` refuse | `DEBUG=False` | `--force` (provision `--demo` wahi karta hai) |
| Backup script "**pg_dump not found**" | client tools `PATH` me nahi | `sudo apt-get install -y postgresql-client`, ya `PG_BIN_DIR=/usr/lib/postgresql/16/bin ./scripts/backup_db.sh` |
| Backup me "**No environment variable BACKUP_ENCRYPTION_KEY**" | key `.env` se aayi par export nahi hui thi | fix ho chuka (script khud export karta hai); phir bhi aaye to key `.env` me hai? `grep -c BACKUP_ENCRYPTION_KEY /opt/ums/$UMS_SLUG/.env` |
| Backup file 0 bytes | `pg_dump` fail hua par purani script ne file bana di | naya script fail loudly karta hai — log dekho (`/var/log/ums-$UMS_SLUG-backup.log`) |
| Restore "database does not exist" | scratch DB nahi banaya | pehle `CREATE DATABASE`, phir restore |
| Emails nahi ja rahe | `EMAIL_BACKEND` khaali / SMTP galat | `.env` me `EMAIL_BACKEND`, `EMAIL_HOST*` set karo; `manage.py check_email` chalao |
| qcluster crash loop | DB down ya `Q_CLUSTER` galat | `journalctl -u ums-$UMS_SLUG-worker -n 50` |
| 2 GB box par `Out of memory` / build fail | swap nahi | step 1.3 ka swap add karo; gunicorn workers kam karo |
| Server reboot ke baad site down | `enable` nahi kiya | `systemctl enable ums-$UMS_SLUG ums-$UMS_SLUG-worker caddy postgresql` |
| `diagnose_college` exit 1 | asli problem hai | output me `BROKEN` / `WARN` lines dekho — har line ke saath problem likhi hoti hai |

---

## 10. Jo main verify nahi kar saka (saaf-saaf)

1. **Server-level commands** (`apt`, `ufw`, `fail2ban`, `unattended-upgrades`, `caddy`,
   `systemd`, `cron`): is machine par sudo/systemd nahi hai — ye steps **nahi chale**.
2. **`provision_server.sh` ka VPS par poora run**: script locally review + parts verify kiye
   hain, par fresh Ubuntu par end-to-end nahi chalaya.
3. **HTTPS/Let's Encrypt**: asli domain + public IP ke bina possible nahi. Caddyfile
   ka syntax repo ke `deploy/Caddyfile` se liya hai, `caddy validate` bhi yahan nahi chala.
4. **Postgres par app**: guide ke exact `.env` keys (`DB_ENGINE/DB_NAME/DB_USER/
   DB_PASSWORD/DB_HOST/DB_PORT`) ke saath ek **asli Postgres** par `migrate` →
   `seed_plans` → `create_college` → `seed_demo --force` → `diagnose_college` →
   `backup_db.sh` → `restore_db.sh` (scratch DB me) chalaya gaya — sab pass, row counts
   match. Jo verify **nahi** hua: Ubuntu ke packaged Postgres 16 par (yahan PG 18 binaries),
   aur password-auth ke saath `pg_hba.conf` ka default Ubuntu setup.
5. **Phone se access**: browser test yahan desktop Chrome par hua; iOS Safari/Android Chrome
   par layout **manual check** chahiye.
6. **2 GB RAM par load**: `PERFORMANCE.md` ke numbers Postgres par purane hain; pehle hafte
   `htop` dekh lo.
7. **Mail/SMS/payment**: asli `EMAIL_*`/`TWILIO_*`/`RAZORPAY_*` credentials ke bina delivery
   verify nahi ho sakti (`manage.py check_email` se SMTP config check kar sakte ho).

---

## 11. Deploy ke baad ek nazar (5 minute)

- [ ] `https://$DOMAIN/healthz/` = `{"status": "ok"}`
- [ ] `https://$DOMAIN/readyz/` = 200
- [ ] `manage.py diagnose_college $DOMAIN` = exit 0
- [ ] admin/teacher/student login, ek page open
- [ ] `/admin-panel/system-status/` par DB, backup, errors sab green
- [ ] `backup_db.sh` chala, file bani, restore test pass
- [ ] reboot karke sab services wapas aayin
- [ ] `.env` ka `BACKUP_ENCRYPTION_KEY` aur `SECRET_KEY` offline copy me hai
- [ ] `fail2ban-client status sshd` me koi ban nahi (apna IP ban na jaye — dhyaan)
