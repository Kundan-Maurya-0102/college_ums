# Backup & Restore — College UMS

Har college deployment ka apna DB hai, isliye backup bhi per-deployment hota hai.
Backups **always encrypted** hote hain (AES-256-CBC, PBKDF2 200k iterations), warna script
plaintext backup likhne se mana kar deti hai.

## 1. Encryption key (ek baar)

```bash
openssl rand -base64 32
```

Output ko deployment ke `.env` mein daalo (aur password manager mein copy rakho):

```env
BACKUP_ENCRYPTION_KEY=<paste here>
```

⚠️ Ye key kho gayi to purane backups restore nahi honge. Key ko **backup ke saath
alag jagah** store karo (password manager / sealed envelope), same disk par nahi.

## 2. Backup lena

```bash
cd /opt/ums/<college-slug>
./scripts/backup_db.sh
```

- Postgres (prod, compose ke andar): `pg_dump` → gzip → encrypt → `backups/<slug>-YYYYmmdd-HHMM.sql.gz.enc`
- SQLite (dev/local): `iterdump` → gzip → encrypt (same pipeline)
- Script khud verify karta hai: `gzip -t` + ek decrypt test, phir hi success bolta hai.
- Folder permission `700`, file permission `600`.
- Retention: `RETENTION_DAYS` (default 14) se purane `*.sql.gz[.enc]` delete.

Cron (roz 2:30 AM):

```cron
30 2 * * * cd /opt/ums/<slug> && ./scripts/backup_db.sh >> /var/log/ums-backup.log 2>&1
```

Off-site copy (recommended): `rclone copy backups/ remote:ums-<slug>/` (backups ko alag
region/disk par le jao — server ke saath same disk par mat rakho).

### 2.1 Agar `pg_dump` PATH par nahi hai

Kai hosts par postgres client tools `PATH` se bahar hote hain
(`/usr/lib/postgresql/16/bin`). Script **fail loudly** karta hai, chupchaap
empty backup nahi likhta:

```bash
PG_BIN_DIR=/usr/lib/postgresql/16/bin ./scripts/backup_db.sh
```

`PG_BIN_DIR` ko `.env` me bhi rakh sakte ho (script wahan se padhta hai).

Backup ke baad script `manage.py record_backup` chala kar DB me row daal deta hai —
isi se `/admin-panel/system-status/` par "Last backup" dikhta hai.

## 3. Restore karna (tested process)

### 3.1 Pehle ek safe copy

```bash
./scripts/backup_db.sh          # current state bhi save kar lo
docker compose stop web         # naye writes rok do
```

### 3.2 Restore

```bash
BACKUP_ENCRYPTION_KEY=<key> ./scripts/restore_db.sh \
  --file backups/ums-20261124-0230.sql.gz.enc --yes
```

Script khud dekhta hai ki target database maujood hai ya nahi. **Naye server par
database hota hi nahi** — us case me wo `CREATE DATABASE` chala kar phir restore karta
hai (yahi disaster-recovery ka asli case hai). `psql` PATH par na ho to:

```bash
PG_BIN_DIR=/usr/lib/postgresql/16/bin ./scripts/restore_db.sh --file ... --yes
```

SQLite (dev):

```bash
DB_ENGINE=sqlite DB_PATH=db.sqlite3 ./scripts/restore_db.sh \
  --file backups/<file>.sql.gz.enc --yes
```

`--yes` ke bina script restore nahi karta (safety). Restore se pehle current DB ka
`<db>.pre-restore.<timestamp>` copy bhi ban jata hai.

### 3.3 Verify (ye steps skip mat karo)

1. `python manage.py check` — koi error nahi.
2. `python manage.py showmigrations | grep "\[ \]"` — koi unapplied migration nahi.
3. Admin login → dashboard par students/fees counts expected hain.
4. Ek student profile kholo, uske marks aur ek fee receipt match karo.
5. `/healthz/` → `{"status": "ok"}`.
6. `docker compose start web`.

## 4. Tested evidence

### 4.1 SQLite round-trip (dev)

```
$ BACKUP_ENCRYPTION_KEY=... DB_ENGINE=sqlite DB_PATH=db.sqlite3 ./scripts/backup_db.sh
[..] encrypted backup written: /tmp/ums-backup-test/scratch-20261124-2209.sql.gz.enc (64K)
$ strings <backup>.enc | grep -c "INSERT INTO"   →  0        # ciphertext, no plaintext SQL
$ DB_PATH=/tmp/ums-restore-test.sqlite3 ./scripts/restore_db.sh --file ... --yes
restored tables: 33 | students: 15 | users: 19 | integrity: ok
```

### 4.2 **Postgres disaster drill (release candidate, asli cycle)**

Postgres 18 par poora college (51 students, 1400 attendance rows, 200 marks, 40 fee
payments, 61 users, 24 subjects, guardian + platform rows) banaya, backup liya,
**database ko DROP kar diya**, phir backup se restore kiya:

```
1. backup : ./scripts/backup_db.sh → rc-test-20261125-2335.sql.gz.enc (60K, encrypted)
2. disaster: DROP DATABASE ums_rc
   →  /readyz/ = 503 {"status":"degraded","db":false, "db_error":"database ... does not exist"}
      /healthz/ = 200  (liveness DB-free rehta hai — sahi behaviour)
      /login/ = 500    (expected: DB hi nahi hai)
3. restore: ./scripts/restore_db.sh --file <backup> --yes
   →  database nahi tha, script ne khud CREATE DATABASE kiya, phir restore
4. verify : row counts before/after — 11 of 12 tables identical:
      users 61=61, students 51=51, teachers 8=8, subjects 24=24,
      attendance 1400=1400, marks 200=200, fees 40=40, notices 5=5,
      guardians 1=1, colleges 1=1, plans 3=3
      errors 2 → 3  (12vi row restore ke *baad* likhi gayi nayi error thi:
                     django-q2 ka "reincarnated pusher" CRITICAL — data loss nahi)
5. app    : /login/ 200, /readyz/ 200 {"db":true,"cache":true}
```

### 4.3 Negative tests

- `BACKUP_ENCRYPTION_KEY` ke bina backup → **refuse**.
- `--yes` ke bina restore → **refuse**.
- `pg_dump` na mile to backup → **exit 1, koi (khali) file nahi likhti**. Pehle ye bug
  tha: pipeline ka output gzip me chala jata tha aur 20-byte "valid" backup ban jata tha.
- `DB_ENGINE=postgres` (script ki short form) Django ke `DB_ENGINE` ko shadow kar deta
  tha → `manage.py` crash. Ab settings short names accept karti hai aur script apna
  `BACKUP_DB_ENGINE` use karta hai.

## 5. System status page aur diagnose

- `/admin-panel/system-status/` (staff) — last backup age + staleness flag, storage,
  pending/failed jobs, error count.
- `.venv/bin/python manage.py diagnose_college <domain>` — backup record, disk, DB,
  migrations, static, e-mail keys. Backup row `WARN` deta hai agar 48h se purana ho
  (`BACKUP_MAX_AGE_HOURS`).

## 6. Restore drill — har 6 mahine

1. Backup file + key se ek **naye** temporary DB par restore karo (production ko chhedo mat).
2. Upar ke 6 verification steps chalao.
3. Notes likho: time taken, koi error, kya missing tha.
4. Drill ke baad temp DB delete kar do.

## 7. Retention aur privacy

- Backup mein student ka personal data hota hai — encrypted hi rakho, public bucket mat banao.
- Student anonymisation/erasure ke baad purane backups mein data reh sakta hai; retention
  window (default 14 din) ke baad wo backups delete ho jate hain. Legal erasure request par
  purane backups bhi manually delete karo (deployment owner ka kaam).
- `BACKUP_ENCRYPTION_KEY` ko git mein kabhi commit mat karo (`.env` gitignored hai).
