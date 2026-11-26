# HTTP API reference

Base URL for local development: `http://localhost:8000`. Responses use JSON. Mutations use `Content-Type: application/json`, the configured `Origin` header and, after authentication, a unique `Idempotency-Key` of 8–100 characters (except logout). The session cookie is issued during registration or login. IDs must belong to the active organization. Monetary amounts use integer BRL cents; dates use `YYYY-MM-DD`. The interface and API validation messages are in Brazilian Portuguese.

| Method and path | Purpose |
| --- | --- |
| `POST /api/register` | Create local account and organization (`email`, `password`, `name`, `organization`) |
| `POST /api/login` | Start session (`email`, `password`) |
| `POST /api/logout` | End session |
| `GET /api/state` | Fetch scoped application snapshot |
| `POST /api/properties` | Create/update property (`name`, optional `id`, `address`, `kind`, `occupancy`) |
| `POST /api/items` | Save inventory record |
| `POST /api/issues` | Create operational issue |
| `POST /api/issues/status` | Change issue status with note |
| `POST /api/purchases` | Create purchase request |
| `POST /api/purchases/approve` | Approve request |
| `POST /api/purchases/receive` | Register receipt |
| `POST /api/purchases/pay` | Register payment |
| `POST /api/finance` | Record revenue or expense |
| `POST /api/reservations/save` | Create reservation (`property_id`, `guest`, `arrival`, `departure`, optional `notes`) |
| `POST /api/reservations/status` | Complete or cancel (`id`, `status`) |
| `POST /api/receivables/save` | Create receivable (`property_id`, `title`, `payer`, `amount`, `due`) |
| `POST /api/receivables/status` | Settle or cancel (`id`, `status`, optional `date`) |
| `POST /api/extra/save` | Save operational module record |
| `POST /api/stock/save` | Save stock item |
| `POST /api/stock/move` | Move stock |

For complete validation rules and payloads see the corresponding functions in `app.py`, `operations.py`, `commercial.py` and the HTTP tests.

## Example (local account)

```bash
curl -c cookies.txt -H 'Origin: http://localhost:8000' \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@example.test","password":"example-local-password","name":"Demo User","organization":"Demo Company"}' \
  http://localhost:8000/api/register

curl -b cookies.txt -H 'Origin: http://localhost:8000' \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: example-create-001' \
  -d '{"name":"Demo Apartment"}' http://localhost:8000/api/properties

curl -b cookies.txt http://localhost:8000/api/state
```

The sample account is fictional. Keep generated session files out of version control. Invalid requests return JSON with an `error` field; unauthenticated requests return 401, unknown scoped records 404 and unexpected failures 500.
