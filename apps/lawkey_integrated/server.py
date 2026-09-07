from __future__ import annotations

from integrations.external_products import load_external_app


PRODUCT_KEY = "lawkey"
PORT = 4281
app = load_external_app(PRODUCT_KEY)

