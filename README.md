# Order Management System (Flask + SQLite)

A full-stack, bilingual order management system with a modern HTML/JS frontend, Flask API backend, and SQLite storage. It covers VAT-ready order capture, customer and product catalogs, safety-stock inventory alerts, pre-order pricing, commission tracking, courier details, CSV import/export, and PDF/Excel invoices.

## Features
- **Order workflows**: Create, view, fulfill orders with automatic totals and UK VAT calculation.
- **Customer CRM**: Persisted customer directory with locale metadata.
- **Inventory + safety stock**: Stock levels, safety thresholds, and pre-order items that bypass stock deductions.
- **Pre-order & early bird**: Product-level early bird price plus multi-stage preorder pricing windows.
- **Commission tracking**: Associate sales reps (Ruby, Kirsty, Admin) with rate defaults and stored commission amounts.
- **Shipping/courier**: Courier + tracking numbers saved per order.
- **Imports/exports**: CSV import/export for products.
- **Invoices**: Download PDF or Excel invoices per order.
- **Role-based controls**: Simple role header (`X-Role`) gate keeps admin-only product updates/import/export.
- **Dashboard**: Revenue, total orders, pre-orders, and safety stock alerts.
- **Bilingual UI**: English + 繁體中文 text toggle on the frontend.

## Project layout
```
backend/
  app.py           # Flask API routes and business logic
  database.py      # SQLAlchemy setup
  models.py        # ORM models for users, customers, products, orders, commissions
frontend/
  index.html       # Main UI
  styles.css       # Professional dashboard styling
  app.js           # API calls, translations, and interactions
requirements.txt   # Python dependencies
```

## Running locally
1. **Install dependencies** (Python 3.11+ recommended):
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Start the API**:
   ```bash
   python backend/app.py
   ```
   The server listens on http://localhost:5000 and auto-creates `orders.db` with demo data.
3. **Open the frontend**:
   Serve `frontend/` via any static host (or simply open `frontend/index.html` in a browser). The JS expects the API at `http://localhost:5000`.

## Key API endpoints
- `GET /api/dashboard` – KPI counters (orders, revenue, low stock, preorders)
- `GET/POST /api/customers`
- `GET/POST /api/products`, `PUT /api/products/<id>` (admin), `POST /api/products/import` (admin), `GET /api/products/export` (admin)
- `GET/POST /api/orders`, `GET /api/orders/<id>`, `POST /api/orders/<id>/fulfill`
- `GET /api/orders/<id>/invoice/pdf` and `/invoice/excel`

Send `X-Role: admin` on requests that manage products/import/export.

## CSV import/export
- **Export**: Download from `/api/products/export`.
- **Import**: POST raw CSV text to `/api/products/import` with headers `name,sku,price,stock,safety_stock,preorder`.

## Tests
Run the API smoke tests:
```bash
python -m pytest
```
