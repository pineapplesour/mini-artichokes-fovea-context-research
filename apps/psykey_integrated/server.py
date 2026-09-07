from __future__ import annotations

from integrations.external_products import load_external_app


PRODUCT_KEY = "psykey"
PORT = 4282
app = load_external_app(PRODUCT_KEY)
