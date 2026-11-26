# Imovance

**Project owner and maintainer:** [João Victor da Silva (JustJao1)](https://github.com/JustJao1).

Property operations management for small rental businesses, property managers and short-stay operators. The application connects property records, inventory, purchasing, maintenance, reservations and financial tracking in a single workspace.

**[Open the interactive demo](https://imovel-em-dia-portfolio.vercel.app)** · [Portuguese technical documentation](docs/README.pt-BR.md) · [Architecture](docs/architecture.md) · [API reference](docs/api.md)

Portfolio release 7.2. The interface is in Brazilian Portuguese; documentation is in English. The public demo uses fictional, browser-local records; it requires no account, makes no real payments and does not send information to an AI provider. Use the reset button to restore the sample data. The independent Python backend provides persistent storage and authenticated workflows when run locally.

## Features

- Property-level workspaces and operational dashboards.
- Room-by-room inventory, automatic shortage tracking and purchase requests, approval, receipt and expense registration.
- Reservation calendar with overlapping-period validation and check-in/check-out boundaries.
- Receivables, overdue records and transactional settlement into the financial ledger.
- Maintenance, cleaning, inspections, suppliers, stock transfers, contracts, reports and audit history.
- Organization-scoped records, password authentication and idempotent HTTP mutations.
- Rule-based operational assistant in the demo; optional, separately configured AI and Asaas integrations in the backend.

## Run locally

Requires Python 3.11+ (standard library only); no database server, paid API or npm installation is needed.

```bash
python app.py
```

Open `http://localhost:8000/demo` for the prepopulated interactive demo or `http://localhost:8000` to register a local account and use the SQLite-backed application. The initial account supports one active property. On Windows, `Iniciar-Windows.bat` is an optional shortcut. The server binds to loopback by default. See `.env.example` for optional environment variables; the application does not automatically load `.env`.

## Testing

```bash
python -m unittest discover -s tests -v
node --check static/app.js
python scripts/build_demo.py
```

The backend tests cover organization isolation, authentication, inventory and purchasing workflows, overlap detection, exactly-once receivable settlement, and mocked external integrations. CI runs the test suite and static JavaScript syntax check. The demo build produces a static HTML file with embedded application assets (Google Fonts are optional; system fallbacks work offline) in `dist/` for hosting.

## Architecture

The browser communicates with a Python HTTP API in server mode, or a local in-browser adapter in demo mode. SQLite stores organization-scoped operational records; amounts are stored as integer cents. Write operations use transactions, scoped queries and idempotency keys. Sessions use hashed tokens and HttpOnly, SameSite cookies; passwords use scrypt.

See [architecture and trade-offs](docs/architecture.md) and the [API reference](docs/api.md).

## Scope and limitations

This is a functional portfolio project, not a production-ready property management service. The demo does not use the Python API and browser data is not shared across devices. Real payment and AI integrations require separate configuration and validation; the automated tests use mocks. External customer portals, real-time collaboration, file uploads, granular staff permissions, automated billing and WhatsApp delivery are outside the current scope. Do not expose the development server to the public internet or enter real personal or financial data into the demo. A production deployment requires additional security, backups, privacy and operational controls.

Source distribution does not imply an open-source license or grant rights to the name or branding; no general reuse license has been selected.
