import os

from locust import HttpUser, between, task


class ApiPerfUser(HttpUser):
    wait_time = between(0.1, 0.6)

    def on_start(self):
        token = os.getenv("LOCUST_BEARER_TOKEN", "").strip()
        self.auth_headers = {"Authorization": f"Bearer {token}"} if token else None

    @task(5)
    def home(self):
        self.client.get("/api/home/", name="GET /api/home/")

    @task(3)
    def combos(self):
        self.client.get("/api/combos/", name="GET /api/combos/")

    @task(2)
    def check_version(self):
        self.client.get("/api/check-app-version/?version=1.0.0&platform=android", name="GET /api/check-app-version/")

    @task(2)
    def me(self):
        if not self.auth_headers:
            return
        self.client.get("/api/me/", headers=self.auth_headers, name="GET /api/me/ (auth)")

    @task(2)
    def cart(self):
        if not self.auth_headers:
            return
        self.client.get("/api/cart/", headers=self.auth_headers, name="GET /api/cart/ (auth)")

    @task(2)
    def orders(self):
        if not self.auth_headers:
            return
        self.client.get("/api/orders/", headers=self.auth_headers, name="GET /api/orders/ (auth)")

    @task(1)
    def active_order(self):
        if not self.auth_headers:
            return
        self.client.get("/api/orders/active/", headers=self.auth_headers, name="GET /api/orders/active/ (auth)")

    @task(1)
    def addresses(self):
        if not self.auth_headers:
            return
        self.client.get("/api/addresses/", headers=self.auth_headers, name="GET /api/addresses/ (auth)")

    @task(1)
    def coupons(self):
        if not self.auth_headers:
            return
        self.client.get("/api/coupons/", headers=self.auth_headers, name="GET /api/coupons/ (auth)")
