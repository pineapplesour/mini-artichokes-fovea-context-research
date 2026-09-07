from __future__ import annotations

from apps.product_app import create_product_app, product_port


PRODUCT_KEY = "islam"
PORT = product_port(PRODUCT_KEY)
app = create_product_app(PRODUCT_KEY)
