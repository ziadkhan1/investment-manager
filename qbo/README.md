# qbo — QuickBooks Online script

A single-file Python script for the QuickBooks Online (QBO) API. Handles OAuth 2.0
(authorization-code flow with a local loopback callback), token caching + automatic
refresh, and basic querying. Built on `requests` + the standard library.

## Setup

1. **Create an Intuit app** at <https://developer.intuit.com> → *My Apps* →
   *Keys & credentials*. Note the **Client ID** and **Client Secret**.
2. Under the app's **Redirect URIs**, add exactly:
   `http://localhost:8000/callback`
3. Install the one dependency:
   ```sh
   pip install requests
   ```
4. Open `qbo.py` and fill in `CLIENT_ID` / `CLIENT_SECRET` near the top
   (or set them as `QBO_CLIENT_ID` / `QBO_CLIENT_SECRET` environment variables).

## Run

```sh
python qbo.py
```

First run opens a browser to authorize; the access/refresh tokens + realmId are
saved to `token.json` and refreshed automatically on later runs. It prints the
company info and the 5 most recent invoices as an example.

## Using it in your own code

```python
from qbo import QBOClient

qbo = QBOClient()
customers = qbo.query("SELECT * FROM Customer WHERE Active = true MAXRESULTS 100")
one       = qbo.get("Invoice", "123")
```

## Notes

- **Sandbox vs production**: set `QBO_ENVIRONMENT` (or edit the constant). A fresh
  sandbox company has no records until you add sample data in the Intuit portal.
- `token.json` holds your tokens — keep it private.
- Querying uses QBO's SQL-like syntax, e.g.
  `SELECT * FROM Customer WHERE Active = true MAXRESULTS 100`.
