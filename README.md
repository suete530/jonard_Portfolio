# Portfolio (Flask + MySQL)

Freelancer portfolio na may **backend**, **database**, at **admin panel**.
Purong Python (Flask) + MySQL (XAMPP) + Tailwind CSS.

## Features

- **Public site**: Home, Projects showcase, Project detail, Contact form
- **Admin panel** (`/admin`): login, dashboard, **CRUD ng projects**, messages inbox
- **Contact form** na nagsa-save ng messages sa MySQL **at nagpapadala ng email** notification (SMTP/Gmail)
- **Image upload** para sa projects (png/jpg/webp/gif, max 4MB)

## Security

- Password **hashing** (PBKDF2-SHA256, hindi plaintext)
- **Parameterized queries** (SQL injection protection)
- **CSRF protection** sa lahat ng forms (Flask-WTF)
- **XSS protection** (Jinja2 auto-escaping)
- **Brute-force protection** (rate limit sa login at contact)
- **Secure session cookies** (HttpOnly, SameSite)
- **Secrets sa `.env`**, hindi sa code
- **Input validation** at generic error messages

## Setup (local)

```powershell
# 1. Pumunta sa folder
cd C:\Users\suete\Documents\portfolio

# 2. Gumawa ng virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. I-install ang dependencies
pip install -r requirements.txt

# 4. Gumawa ng .env (kopyahin ang example at palitan ang SECRET_KEY)
Copy-Item .env.example .env

# 5. Siguraduhing naka-start ang MySQL sa XAMPP, tapos gumawa ng admin account
python seed_admin.py

# 6. Patakbuhin ang app (optional: magdagdag ng FLASK_DEBUG=1 para sa debug mode)
python app.py
```

> Naka-off ang Flask debug by default. Sa dev: `$env:FLASK_DEBUG="1"; python app.py`

Buksan: http://127.0.0.1:5000  &middot;  Admin: http://127.0.0.1:5000/admin

## Email notification (contact form)

Ang contact form ay nagsa-save sa DB **at** nagpapadala ng email sa `MAIL_TO`.
I-set ang mga ito sa `.env` (blangko = disabled, DB save pa rin ang gagawin):

```env
SMTP_USER=your.email@gmail.com
SMTP_PASSWORD=your-16-char-app-password   # Gmail App Password
MAIL_TO=your.email@gmail.com
```

> Gmail: kailangan ng **App Password** (Google Account > Security > App passwords),
> hindi ang normal na password. Kung mabigo ang pag-send, naka-save pa rin ang
> mensahe sa admin inbox at may warning na makikita ang user.

## Deploy (VPS — Oracle Cloud Always Free) — $0

Pinaka-rekomendado kung gusto mong **lahat ng features** (MySQL + image uploads +
email) nang libre. Ang Oracle Cloud Always Free ay may 2 OCPU / 12 GB RAM /
200 GB storage, libre forever.

**Sa server (Ubuntu ARM/AMD):**

```bash
# 1. Clone ang repo
git clone <iyong-github-repo-url> ~/portfolio
cd ~/portfolio

# 2. One-time setup (gagawa ng DB, venv, nginx, systemd, firewall)
#    Palitan ang DOMAIN ng public IP + ".sslip.io" para libre ang HTTPS,
#    hal. DOMAIN=129.146.10.5.sslip.io
sudo DOMAIN=<public-ip>.sslip.io bash deploy/setup.sh

# 3. Gumawa ng admin account (tatanungin ang username/password)
sudo -u portfolio /opt/portfolio/.venv/bin/python /opt/portfolio/seed_admin.py

# 4. I-edit ang .env (SMTP/AI kung gusto)
sudo nano /opt/portfolio/.env
sudo systemctl restart portfolio
```

Buksan: `http://<public-ip>/` (o `https://<public-ip>.sslip.io` pag naka-TLS).

**HTTPS (Let's Encrypt, libre):** pag naka-`DOMAIN` na gamit ang `sslip.io`:

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d <public-ip>.sslip.io
```

**Mahalagang paalala:** sa Oracle Console, buksan din ang **Security List**
(ingress TCP 80 at 443) — hiwalay ito sa iptables na na-setup na ng `setup.sh`.

## Deploy (Render — $0, walang credit card)

Stack (lahat libre, walang card):
- **Web**: Render Free (Web Service)
- **MySQL**: [Aiven Free MySQL](https://aiven.io/free-mysql-database)
- **Images**: [Cloudinary Free](https://cloudinary.com/) — hindi nawawala sa redeploy
- **Email**: [Resend Free](https://resend.com/) — HTTP API (blocked ang SMTP sa Render free)

1. I-push ang project sa GitHub.
2. Sa Render: **New > Blueprint** (para gamitin ang `render.yaml`) o **New > Web Service**.
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn app:app`
3. Sa **Aiven**: gumawa ng MySQL service → kopyahin ang `host`, `port`, `user`,
   `password`, `database`. I-download ang **CA certificate** (`ca.pem`) →
   ilagay sa repo bilang `certs/aiven-ca.pem`.
4. Sa **Cloudinary**: kopyahin ang `CLOUDINARY_URL`.
5. Sa **Resend**: gumawa ng API key → `RESEND_API_KEY`; `MAIL_TO` = email mo.
6. Sa Render **Environment** tab, ilagay ang mga ito:
   `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_SSL_CA=certs/aiven-ca.pem`,
   `RESEND_API_KEY`, `MAIL_TO`, `MAIL_FROM`, `CLOUDINARY_URL`.
7. Deploy → buksan ang site → gumawa ng admin account (isa-isa sa Render Shell):
   `python seed_admin.py`

> **Note:** natutulog ang Render free pag walang bisita (~30-60s cold start);
> natutulog din ang Aiven free pag idle. Ang rate limiter ay in-memory by
> default (per-worker); magdagdag ng Render Key Value (Redis) at i-set ang
> `RATELIMIT_STORAGE_URI` kung gusto ng shared limits.

## Project structure

```
portfolio/
├─ app.py              # Flask app factory + error handlers
├─ config.py           # config (env-based)
├─ database.py         # MySQL helper + schema (reused sa class pattern)
├─ security.py         # password hashing, login_required, validation
├─ mailer.py           # email notifications (Resend API o smtplib)
├─ uploads.py          # cloud image storage (Cloudinary, stdlib)
├─ assistant.py        # AI chat (OpenAI-compatible)
├─ extensions.py       # shared csrf + limiter
├─ seed_admin.py       # gumagawa ng admin account
├─ blueprints/
│  ├─ main.py          # public routes
│  └─ admin.py         # admin routes (CRUD)
├─ templates/          # Jinja2 + Tailwind
├─ static/uploads/     # uploaded images (fallback kapag walang Cloudinary)
├─ deploy/             # VPS setup (systemd, nginx, setup.sh)
├─ render.yaml         # Render blueprint (card-free deploy)
├─ schema.sql          # reference DDL
└─ requirements.txt
```
