# Hardcore Fashion Store

[![CI/CD Pipeline](https://github.com/mbayocharles26-netizen/Hardcore-fashion/actions/workflows/ci.yml/badge.svg)](https://github.com/mbayocharles26-netizen/Hardcore-fashion/actions/workflows/ci.yml)

A full-stack e-commerce web application built with **Django REST Framework** (backend) and **HTML/CSS/JavaScript** (frontend), backed by **PostgreSQL**.

> **GitHub Repository:** https://github.com/mbayocharles26-netizen/Hardcore-fashion

---

## Project Structure

```
E-commerce-final/
├── backend/
│   ├── ecommerce/          # Django project settings & URLs
│   ├── store/              # App: models, views, serializers, admin, URLs
│   ├── manage.py
│   └── requirements.txt
├── frontend/
│   ├── templates/          # HTML templates (base, index, products, cart, checkout, auth)
│   └── static/
│       ├── css/style.css
│       └── js/main.js
├── database/
│   ├── setup.sql           # DB creation script
│   └── seed_data.sql       # Sample product data
├── readme/
│   └── README.md
├── docker-compose.yml
└── .env.example
```

---

## Features

- JWT authentication (register, login, logout)
- Product listing with category filters and search
- Product detail pages
- Shopping cart (add, remove, quantity)
- Checkout & order creation
- Django Admin panel
- Responsive dark-themed UI (black, white, gold)
- REST API with DRF

---

## Setup

### Prerequisites
- Python 3.10+
- PostgreSQL 14+
- Node.js (optional, for tooling)

### 1. Database
```sql
-- In psql or pgAdmin, run:
\i database/setup.sql
```

### 2. Environment
```bash
cp .env.example .env
# Edit .env with your DB credentials and secret key
```

Generate required secrets:
```bash
# Django SECRET_KEY
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# OTP_HASH_SECRET
python -c "import secrets; print(secrets.token_hex(32))"
```

> **Never commit `.env` to version control.** It is listed in `.gitignore`. Only commit `.env.example` with placeholder values.
>
> For production/CI, set all secrets as environment variables in your hosting provider (Render, Railway) or as GitHub Actions repository secrets (**Settings → Secrets and variables → Actions**).

### 3. Backend
```bash
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### 4. Seed Data (optional)
```bash
# After migrations, run in psql:
\i database/seed_data.sql
```

### 5. Access
| URL | Description |
|-----|-------------|
| http://localhost:8000/ | Homepage |
| http://localhost:8000/products/ | Shop |
| http://localhost:8000/admin/ | Django Admin |
| http://localhost:8000/api/ | REST API |

---

## Live Deployment

> **URL:** `https://hardcore-fashion.onrender.com` *(update after Render deployment)*

---

## Docker

```bash
docker-compose up --build
```

---

## CI/CD Pipeline

GitHub Actions workflow at `.github/workflows/ci.yml` runs on every push and pull request to `main`.

### Jobs

| Job | Trigger | What it does |
|-----|---------|-------------|
| **lint** | every push/PR | Runs `flake8` — max line length 120, skips migrations |
| **test** | after lint | Spins up PostgreSQL 15 service, runs `migrate` + `manage.py test` |
| **docker** | after test | Builds the Docker image using Buildx with GHA layer cache |
| **deploy** | after docker, `main` push only | Triggers Render deploy hook via `RENDER_DEPLOY_HOOK_URL` secret |

### Required GitHub Secrets

Add these in **Settings → Secrets and variables → Actions**:

| Secret | Where to get it |
|--------|-----------------|
| `RENDER_DEPLOY_HOOK_URL` | Render dashboard → your service → Settings → Deploy Hook |

### Pipeline flow

```
push to main
    │
    ▼
  lint  ──fail──▶  ✗ blocked
    │
    ▼
  test (+ postgres service)  ──fail──▶  ✗ blocked
    │
    ▼
  docker build
    │
    ▼
  deploy → Render
```

---

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /api/register/ | No | Register user |
| POST | /api/token/ | No | Get JWT token |
| GET | /api/products/ | No | List products |
| GET | /api/products/{slug}/ | No | Product detail |
| GET | /api/categories/ | No | List categories |
| GET/POST | /api/cart/ | Yes | View/add to cart |
| DELETE | /api/cart/{id}/ | Yes | Remove cart item |
| POST | /api/checkout/ | Yes | Place order |
| GET | /api/orders/ | Yes | Order history |

---

## Rate Limiting

This project uses Django REST Framework throttling to protect the API from abuse.

- Global throttling is enabled in `backend/ecommerce/settings.py`.
- Unauthenticated clients are limited to `20/hour`.
- Authenticated users are limited to `100/hour`.
- Sensitive endpoints such as login, OTP, and payment initialization have stricter limits.
- Vendors also have a dedicated `VendorRateThrottle` for vendor-scoped rate limiting.

If you deploy multiple app instances, using a shared cache backend such as Redis is recommended for consistent throttling across servers.

## Row-Level Security (RLS)

This application includes PostgreSQL Row-Level Security for per-user and per-vendor access control.

- RLS session variables are set in `backend/store/middleware.py` by `PostgresRLSMiddleware`.
- Policies are created automatically by the migration `backend/store/migrations/0008_rls_policies.py`.
- Customers may only access their own orders.
- Vendors may only access their own products, vendor orders, and vendor notifications.
- Admin users are granted unrestricted access through role-aware policies.

> Run `python manage.py migrate` after switching to PostgreSQL to install the RLS policies.

## Loading Skeleton UI

The frontend now uses skeleton loaders for a smoother loading experience.

- Home page product cards and category filters show animated shimmer placeholders while API data loads.
- Cart page displays table row skeletons until the cart response arrives.
- Vendor dashboard shows skeleton metrics, chart, and table placeholders while vendor data fetches.
- Skeleton styles are defined in `frontend/static/css/style.css` using a reusable `.skeleton` shimmer utility.
