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

## 3. Restore karna (tested process)

### 3.1 Pehle ek safe copy

```bash
./scripts/backup_db.sh          # current state bhi save kar lo
docker compose stop web         # naye writes rok do
```

### 3.2 Restore

```bash
docker compose exec -T db dropdb -U ums --if-exists ums_restore
docker compose exec -T db createdb -U ums ums_restore
BACKUP_ENCRYPTION_KEY=<key> ./scripts/restore_db.sh \
  --file backups/ums-20261124-0230.sql.gz.enc --yes
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

## 4. Tested evidence (is machine par chalaya gaya)

Is machine par Docker/Postgres nahi hai, isliye round-trip **SQLite** par actually chala kar
verify kiya gaya (pipeline identical hai):

```
$ BACKUP_ENCRYPTION_KEY=... DB_ENGINE=sqlite DB_PATH=db.sqlite3 ./scripts/backup_db.sh
[..] backing up engine=sqlite slug=scratch
[..] encrypted backup written: /tmp/ums-backup-test/scratch-20261124-2209.sql.gz.enc (64K)

$ strings <backup>.enc | grep -c "INSERT INTO"   →  0        # ciphertext, no plaintext SQL

$ DB_PATH=/tmp/ums-restore-test.sqlite3 ./scripts/restore_db.sh --file ... --yes
[..] backup decrypted and verified: 1776 lines
restored tables: 33
students: 15
users: 19
integrity: ok
```

Negative tests bhi pass: key ke bina backup **refuse**, `--yes` ke bina restore **refuse**.

## 5. Restore drill — har 6 mahine

1. Backup file + key se ek **naye** temporary DB par restore karo (production ko chhedo mat).
2. Upar ke 6 verification steps chalao.
3. Notes likho: time taken, koi error, kya missing tha.
4. Drill ke baad temp DB delete kar do.

## 6. Retention aur privacy

- Backup mein student ka personal data hota hai — encrypted hi rakho, public bucket mat banao.
- Student anonymisation/erasure ke baad purane backups mein data reh sakta hai; retention
  window (default 14 din) ke baad wo backups delete ho jate hain. Legal erasure request par
  purane backups bhi manually delete karo (deployment owner ka kaam).
- `BACKUP_ENCRYPTION_KEY` ko git mein kabhi commit mat karo (`.env` gitignored hai).
