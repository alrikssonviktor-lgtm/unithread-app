"""
Unithread App — External API Integrations.

Adapters for Shopify, Gelato, TikTok Ads, Meta Ads, Snapchat Ads, Google Ads.
Each adapter pulls data and maps it to internal expense/revenue format.
"""

import json
import time
import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime, date, timedelta
from typing import Any

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Base adapter
# ---------------------------------------------------------------------------

class IntegrationAdapter(ABC):
    """Base class for all external API integrations."""

    # Subclass must set these
    PLATFORM = ""
    DISPLAY_NAME = ""
    ICON = ""
    REQUIRED_FIELDS = []  # list of {"key": "...", "label": "...", "type": "text|password"}
    DESCRIPTION = ""

    def __init__(self, config: dict):
        """
        config: dict with credentials + settings from the integrations sheet.
        """
        self.config = config
        self.bolag = config.get("bolag", "Unithread")
        self.errors: list[str] = []

    @abstractmethod
    def test_connection(self) -> dict:
        """Test if the credentials are valid. Returns {"ok": True/False, "message": "..."}"""
        ...

    @abstractmethod
    def sync_data(self, since_date: str | None = None) -> dict:
        """
        Pull data from the external API since the given date.
        Returns {
            "expenses": [{"datum", "kategori", "beskrivning", "belopp", "moms_sats"}],
            "revenue":  [{"datum", "kategori", "beskrivning", "belopp", "kund"}],
            "raw_data": {...},  # optional debug info
        }
        """
        ...

    def _request(self, method, url, **kwargs):
        """HTTP request with retry logic and error handling."""
        timeout = kwargs.pop("timeout", 30)
        for attempt in range(3):
            try:
                resp = requests.request(method, url, timeout=timeout, **kwargs)
                if resp.status_code in (429, 500, 502, 503, 504):
                    time.sleep(2 ** attempt)
                    continue
                resp.raise_for_status()
                return resp
            except requests.exceptions.Timeout:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise
            except requests.exceptions.HTTPError as e:
                self.errors.append(f"HTTP {resp.status_code}: {resp.text[:200]}")
                raise
            except requests.exceptions.ConnectionError as e:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                self.errors.append(f"Connection error: {str(e)[:200]}")
                raise
        return None


# ---------------------------------------------------------------------------
# Shopify
# ---------------------------------------------------------------------------

class ShopifyAdapter(IntegrationAdapter):
    PLATFORM = "shopify"
    DISPLAY_NAME = "Shopify"
    ICON = "🛒"
    DESCRIPTION = "Hämtar ordrar, intäkter och transaktionsavgifter automatiskt."
    REQUIRED_FIELDS = [
        {"key": "shop_domain", "label": "Butikens domän (ex: min-butik.myshopify.com)", "type": "text"},
        {"key": "access_token", "label": "Admin API Access Token", "type": "password"},
    ]

    def __init__(self, config):
        super().__init__(config)
        self.shop = config.get("shop_domain", "").strip().rstrip("/")
        self.token = config.get("access_token", "")
        if not self.shop.endswith(".myshopify.com"):
            self.shop = f"{self.shop}.myshopify.com"
        self.base_url = f"https://{self.shop}/admin/api/2024-01"
        self.headers = {
            "X-Shopify-Access-Token": self.token,
            "Content-Type": "application/json",
        }

    def test_connection(self):
        try:
            resp = self._request("GET", f"{self.base_url}/shop.json", headers=self.headers)
            shop_data = resp.json().get("shop", {})
            return {"ok": True, "message": f"Ansluten till {shop_data.get('name', self.shop)}"}
        except Exception as e:
            return {"ok": False, "message": f"Kunde inte ansluta: {str(e)[:150]}"}

    def sync_data(self, since_date=None):
        if not since_date:
            since_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        expenses = []
        revenue = []

        try:
            # Fetch paid orders
            params = {
                "status": "any",
                "financial_status": "paid",
                "created_at_min": f"{since_date}T00:00:00Z",
                "limit": 250,
                "fields": "id,name,created_at,total_price,subtotal_price,total_tax,"
                          "total_discounts,financial_status,currency,line_items,"
                          "customer,total_shipping_price_set",
            }
            resp = self._request("GET", f"{self.base_url}/orders.json",
                                 headers=self.headers, params=params)
            orders = resp.json().get("orders", [])

            for order in orders:
                order_date = order.get("created_at", "")[:10]
                order_name = order.get("name", f"#{order.get('id', '?')}")
                total = float(order.get("total_price", 0))
                customer = order.get("customer", {})
                customer_name = ""
                if customer:
                    first = customer.get("first_name", "")
                    last = customer.get("last_name", "")
                    customer_name = f"{first} {last}".strip()

                # Revenue entry per order
                revenue.append({
                    "datum": order_date,
                    "kategori": "Produktförsäljning",
                    "beskrivning": f"Shopify order {order_name}",
                    "belopp": total,
                    "kund": customer_name or "Shopify-kund",
                    "source": "shopify",
                    "source_id": str(order.get("id", "")),
                })

            # Estimate Shopify payment processing fees (~2.4% + 0.25 SEK)
            total_revenue = sum(r["belopp"] for r in revenue)
            if total_revenue > 0:
                fee_estimate = round(total_revenue * 0.024 + len(revenue) * 0.25, 2)
                expenses.append({
                    "datum": date.today().isoformat(),
                    "kategori": "Bank & Avgifter",
                    "beskrivning": f"Shopify transaktionsavgifter ({len(revenue)} ordrar, {since_date} →)",
                    "belopp": fee_estimate,
                    "moms_sats": 0,
                    "source": "shopify",
                    "source_id": f"fees_{since_date}",
                })

        except Exception as e:
            logger.error(f"Shopify sync error: {e}")
            self.errors.append(str(e)[:200])

        return {"expenses": expenses, "revenue": revenue, "raw_data": {"orders_count": len(revenue)}}


# ---------------------------------------------------------------------------
# Gelato
# ---------------------------------------------------------------------------

class GelatoAdapter(IntegrationAdapter):
    PLATFORM = "gelato"
    DISPLAY_NAME = "Gelato"
    ICON = "🎨"
    DESCRIPTION = "Hämtar produktionskostnader och fraktkostnader från Gelato."
    REQUIRED_FIELDS = [
        {"key": "api_key", "label": "Gelato API Key", "type": "password"},
    ]

    BASE_URL = "https://order.gelatoapis.com/v4"

    def __init__(self, config):
        super().__init__(config)
        self.api_key = config.get("api_key", "")
        self.headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }

    def test_connection(self):
        try:
            # List orders to test auth
            resp = self._request("GET", f"{self.BASE_URL}/orders",
                                 headers=self.headers, params={"limit": 1})
            return {"ok": True, "message": "Ansluten till Gelato"}
        except Exception as e:
            return {"ok": False, "message": f"Kunde inte ansluta: {str(e)[:150]}"}

    def sync_data(self, since_date=None):
        if not since_date:
            since_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

        expenses = []
        try:
            params = {"limit": 100, "offset": 0}
            resp = self._request("GET", f"{self.BASE_URL}/orders",
                                 headers=self.headers, params=params)
            data = resp.json()
            orders = data.get("orders", [])

            for order in orders:
                created = order.get("createdAt", "")[:10]
                if created < since_date:
                    continue

                order_id = order.get("id", "?")
                # Financial summary
                financial = order.get("financialSummary", {})
                production_cost = float(financial.get("productionCost", {}).get("amount", 0))
                shipping_cost = float(financial.get("shippingCost", {}).get("amount", 0))
                total_cost = production_cost + shipping_cost

                if total_cost > 0:
                    expenses.append({
                        "datum": created,
                        "kategori": "Design & Produktion",
                        "beskrivning": f"Gelato order {order_id[:12]} (prod: {production_cost}, frakt: {shipping_cost})",
                        "belopp": total_cost,
                        "moms_sats": 0,
                        "source": "gelato",
                        "source_id": str(order_id),
                    })

        except Exception as e:
            logger.error(f"Gelato sync error: {e}")
            self.errors.append(str(e)[:200])

        return {"expenses": expenses, "revenue": [], "raw_data": {"orders_count": len(expenses)}}


# ---------------------------------------------------------------------------
# TikTok Ads
# ---------------------------------------------------------------------------

class TikTokAdsAdapter(IntegrationAdapter):
    PLATFORM = "tiktok_ads"
    DISPLAY_NAME = "TikTok Ads"
    ICON = "🎵"
    DESCRIPTION = "Hämtar annonskostnader, visningar och klick från TikTok Ads."
    REQUIRED_FIELDS = [
        {"key": "access_token", "label": "Access Token", "type": "password"},
        {"key": "advertiser_id", "label": "Advertiser ID", "type": "text"},
    ]

    BASE_URL = "https://business-api.tiktok.com/open_api/v1.3"

    def __init__(self, config):
        super().__init__(config)
        self.token = config.get("access_token", "")
        self.adv_id = config.get("advertiser_id", "")
        self.headers = {
            "Access-Token": self.token,
            "Content-Type": "application/json",
        }

    def test_connection(self):
        try:
            params = {"advertiser_ids": json.dumps([self.adv_id])}
            resp = self._request("GET", f"{self.BASE_URL}/advertiser/info/",
                                 headers=self.headers, params=params)
            data = resp.json()
            if data.get("code") == 0:
                advs = data.get("data", {}).get("list", [])
                name = advs[0].get("advertiser_name", self.adv_id) if advs else self.adv_id
                return {"ok": True, "message": f"Ansluten till TikTok Ads — {name}"}
            return {"ok": False, "message": data.get("message", "Okänt fel")}
        except Exception as e:
            return {"ok": False, "message": f"Kunde inte ansluta: {str(e)[:150]}"}

    def sync_data(self, since_date=None):
        if not since_date:
            since_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        end_date = date.today().isoformat()

        expenses = []
        try:
            body = {
                "advertiser_id": self.adv_id,
                "report_type": "BASIC",
                "data_level": "AUCTION_CAMPAIGN",
                "dimensions": ["campaign_id", "stat_time_day"],
                "metrics": ["spend", "impressions", "clicks", "ctr", "cpc", "cpm",
                            "conversion", "cost_per_conversion"],
                "start_date": since_date,
                "end_date": end_date,
                "page_size": 500,
            }
            resp = self._request("POST", f"{self.BASE_URL}/report/integrated/get/",
                                 headers=self.headers, json=body)
            data = resp.json()

            if data.get("code") == 0:
                rows = data.get("data", {}).get("list", [])
                # Aggregate by day
                daily_spend = {}
                daily_metrics = {}
                for row in rows:
                    dims = row.get("dimensions", {})
                    metrics = row.get("metrics", {})
                    day = dims.get("stat_time_day", "")[:10]
                    spend = float(metrics.get("spend", 0))
                    impr = int(metrics.get("impressions", 0))
                    clicks = int(metrics.get("clicks", 0))

                    daily_spend[day] = daily_spend.get(day, 0) + spend
                    if day not in daily_metrics:
                        daily_metrics[day] = {"impressions": 0, "clicks": 0}
                    daily_metrics[day]["impressions"] += impr
                    daily_metrics[day]["clicks"] += clicks

                for day, spend in sorted(daily_spend.items()):
                    if spend <= 0:
                        continue
                    m = daily_metrics.get(day, {})
                    expenses.append({
                        "datum": day,
                        "kategori": "Marknadsföring",
                        "beskrivning": f"TikTok Ads ({m.get('impressions', 0)} visn, {m.get('clicks', 0)} klick)",
                        "belopp": round(spend, 2),
                        "moms_sats": 0,
                        "source": "tiktok_ads",
                        "source_id": f"tiktok_{day}",
                    })

        except Exception as e:
            logger.error(f"TikTok Ads sync error: {e}")
            self.errors.append(str(e)[:200])

        return {"expenses": expenses, "revenue": [], "raw_data": {"days": len(expenses)}}


# ---------------------------------------------------------------------------
# Meta Ads (Facebook / Instagram)
# ---------------------------------------------------------------------------

class MetaAdsAdapter(IntegrationAdapter):
    PLATFORM = "meta_ads"
    DISPLAY_NAME = "Meta Ads"
    ICON = "📘"
    DESCRIPTION = "Hämtar annonskostnader från Facebook & Instagram Ads."
    REQUIRED_FIELDS = [
        {"key": "access_token", "label": "Facebook Access Token (långlivad)", "type": "password"},
        {"key": "ad_account_id", "label": "Ad Account ID (act_XXXXXXX)", "type": "text"},
    ]

    BASE_URL = "https://graph.facebook.com/v19.0"

    def __init__(self, config):
        super().__init__(config)
        self.token = config.get("access_token", "")
        self.ad_account = config.get("ad_account_id", "")
        if not self.ad_account.startswith("act_"):
            self.ad_account = f"act_{self.ad_account}"

    def test_connection(self):
        try:
            resp = self._request("GET", f"{self.BASE_URL}/{self.ad_account}",
                                 params={"access_token": self.token, "fields": "name,currency,account_status"})
            data = resp.json()
            if "error" in data:
                return {"ok": False, "message": data["error"].get("message", "Okänt fel")}
            return {"ok": True, "message": f"Ansluten till Meta Ads — {data.get('name', self.ad_account)}"}
        except Exception as e:
            return {"ok": False, "message": f"Kunde inte ansluta: {str(e)[:150]}"}

    def sync_data(self, since_date=None):
        if not since_date:
            since_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        end_date = date.today().isoformat()

        expenses = []
        try:
            params = {
                "access_token": self.token,
                "level": "account",
                "fields": "spend,impressions,clicks,ctr,cpc,cpm,actions",
                "time_range": json.dumps({"since": since_date, "until": end_date}),
                "time_increment": 1,  # daily breakdown
                "limit": 500,
            }
            resp = self._request("GET", f"{self.BASE_URL}/{self.ad_account}/insights", params=params)
            data = resp.json()

            for row in data.get("data", []):
                day = row.get("date_start", "")[:10]
                spend = float(row.get("spend", 0))
                impressions = int(row.get("impressions", 0))
                clicks = int(row.get("clicks", 0))

                if spend <= 0:
                    continue

                expenses.append({
                    "datum": day,
                    "kategori": "Marknadsföring",
                    "beskrivning": f"Meta Ads ({impressions} visn, {clicks} klick)",
                    "belopp": round(spend, 2),
                    "moms_sats": 0,
                    "source": "meta_ads",
                    "source_id": f"meta_{day}",
                })

        except Exception as e:
            logger.error(f"Meta Ads sync error: {e}")
            self.errors.append(str(e)[:200])

        return {"expenses": expenses, "revenue": [], "raw_data": {"days": len(expenses)}}


# ---------------------------------------------------------------------------
# Snapchat Ads
# ---------------------------------------------------------------------------

class SnapchatAdsAdapter(IntegrationAdapter):
    PLATFORM = "snapchat_ads"
    DISPLAY_NAME = "Snapchat Ads"
    ICON = "👻"
    DESCRIPTION = "Hämtar annonskostnader från Snapchat Ads Manager."
    REQUIRED_FIELDS = [
        {"key": "access_token", "label": "Snapchat OAuth Access Token", "type": "password"},
        {"key": "ad_account_id", "label": "Ad Account ID", "type": "text"},
    ]

    BASE_URL = "https://adsapi.snapchat.com/v1"

    def __init__(self, config):
        super().__init__(config)
        self.token = config.get("access_token", "")
        self.ad_account = config.get("ad_account_id", "")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def test_connection(self):
        try:
            resp = self._request("GET", f"{self.BASE_URL}/adaccounts/{self.ad_account}",
                                 headers=self.headers)
            data = resp.json()
            accs = data.get("adaccounts", [])
            if accs:
                acc = accs[0].get("adaccount", {})
                return {"ok": True, "message": f"Ansluten till Snapchat Ads — {acc.get('name', self.ad_account)}"}
            return {"ok": True, "message": "Ansluten till Snapchat Ads"}
        except Exception as e:
            return {"ok": False, "message": f"Kunde inte ansluta: {str(e)[:150]}"}

    def sync_data(self, since_date=None):
        if not since_date:
            since_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        end_date = date.today().isoformat()

        expenses = []
        try:
            # Get campaigns first
            resp = self._request("GET", f"{self.BASE_URL}/adaccounts/{self.ad_account}/campaigns",
                                 headers=self.headers)
            campaigns = resp.json().get("campaigns", [])

            for camp_wrapper in campaigns:
                camp = camp_wrapper.get("campaign", {})
                camp_id = camp.get("id", "")
                camp_name = camp.get("name", "")

                # Get stats for this campaign
                params = {
                    "granularity": "DAY",
                    "start_time": f"{since_date}T00:00:00.000-00:00",
                    "end_time": f"{end_date}T23:59:59.000-00:00",
                    "fields": "spend,impressions,swipes",
                }
                try:
                    stats_resp = self._request(
                        "GET",
                        f"{self.BASE_URL}/campaigns/{camp_id}/stats",
                        headers=self.headers, params=params
                    )
                    stats_data = stats_resp.json()

                    timeseries = stats_data.get("timeseries_stats", [])
                    for ts_wrapper in timeseries:
                        ts = ts_wrapper.get("timeseries_stat", {})
                        for series in ts.get("timeseries", []):
                            day = series.get("start_time", "")[:10]
                            stats = series.get("stats", {})
                            # Snapchat spend is in micro-currency (1/1,000,000)
                            spend_micro = float(stats.get("spend", 0))
                            spend = spend_micro / 1_000_000
                            impressions = int(stats.get("impressions", 0))
                            swipes = int(stats.get("swipes", 0))

                            if spend <= 0:
                                continue

                            expenses.append({
                                "datum": day,
                                "kategori": "Marknadsföring",
                                "beskrivning": f"Snapchat Ads — {camp_name} ({impressions} visn, {swipes} swipes)",
                                "belopp": round(spend, 2),
                                "moms_sats": 0,
                                "source": "snapchat_ads",
                                "source_id": f"snap_{camp_id}_{day}",
                            })
                except Exception:
                    continue  # Skip individual campaign errors

        except Exception as e:
            logger.error(f"Snapchat Ads sync error: {e}")
            self.errors.append(str(e)[:200])

        return {"expenses": expenses, "revenue": [], "raw_data": {"days": len(expenses)}}


# ---------------------------------------------------------------------------
# Google Ads
# ---------------------------------------------------------------------------

class GoogleAdsAdapter(IntegrationAdapter):
    PLATFORM = "google_ads"
    DISPLAY_NAME = "Google Ads"
    ICON = "📊"
    DESCRIPTION = "Hämtar annonskostnader, visningar och klick från Google Ads."
    REQUIRED_FIELDS = [
        {"key": "developer_token", "label": "Developer Token", "type": "password"},
        {"key": "client_id", "label": "OAuth Client ID", "type": "text"},
        {"key": "client_secret", "label": "OAuth Client Secret", "type": "password"},
        {"key": "refresh_token", "label": "OAuth Refresh Token", "type": "password"},
        {"key": "customer_id", "label": "Customer ID (utan bindestreck)", "type": "text"},
    ]

    TOKEN_URL = "https://oauth2.googleapis.com/token"
    ADS_URL = "https://googleads.googleapis.com/v16"

    def __init__(self, config):
        super().__init__(config)
        self.developer_token = config.get("developer_token", "")
        self.client_id = config.get("client_id", "")
        self.client_secret = config.get("client_secret", "")
        self.refresh_token = config.get("refresh_token", "")
        self.customer_id = config.get("customer_id", "").replace("-", "")
        self._access_token = None

    def _get_access_token(self):
        """Exchange refresh token for access token."""
        if self._access_token:
            return self._access_token
        resp = requests.post(self.TOKEN_URL, data={
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
        }, timeout=15)
        resp.raise_for_status()
        self._access_token = resp.json().get("access_token")
        return self._access_token

    def test_connection(self):
        try:
            token = self._get_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "developer-token": self.developer_token,
                "Content-Type": "application/json",
            }
            # Simple query to test auth
            query = "SELECT customer.descriptive_name FROM customer LIMIT 1"
            resp = self._request(
                "POST",
                f"{self.ADS_URL}/customers/{self.customer_id}/googleAds:searchStream",
                headers=headers,
                json={"query": query}
            )
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                results = data[0].get("results", [])
                name = results[0]["customer"]["descriptiveName"] if results else self.customer_id
                return {"ok": True, "message": f"Ansluten till Google Ads — {name}"}
            return {"ok": True, "message": "Ansluten till Google Ads"}
        except Exception as e:
            return {"ok": False, "message": f"Kunde inte ansluta: {str(e)[:150]}"}

    def sync_data(self, since_date=None):
        if not since_date:
            since_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        end_date = date.today().isoformat()

        expenses = []
        try:
            token = self._get_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "developer-token": self.developer_token,
                "Content-Type": "application/json",
            }

            # GAQL query for daily campaign spend
            query = f"""
                SELECT
                    segments.date,
                    campaign.name,
                    metrics.cost_micros,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.conversions
                FROM campaign
                WHERE segments.date BETWEEN '{since_date}' AND '{end_date}'
                ORDER BY segments.date
            """
            resp = self._request(
                "POST",
                f"{self.ADS_URL}/customers/{self.customer_id}/googleAds:searchStream",
                headers=headers,
                json={"query": query}
            )
            data = resp.json()

            # Aggregate by day
            daily_spend = {}
            daily_metrics = {}
            for batch in data if isinstance(data, list) else [data]:
                for result in batch.get("results", []):
                    day = result.get("segments", {}).get("date", "")
                    cost_micros = int(result.get("metrics", {}).get("costMicros", 0))
                    cost = cost_micros / 1_000_000
                    impressions = int(result.get("metrics", {}).get("impressions", 0))
                    clicks = int(result.get("metrics", {}).get("clicks", 0))

                    daily_spend[day] = daily_spend.get(day, 0) + cost
                    if day not in daily_metrics:
                        daily_metrics[day] = {"impressions": 0, "clicks": 0}
                    daily_metrics[day]["impressions"] += impressions
                    daily_metrics[day]["clicks"] += clicks

            for day, spend in sorted(daily_spend.items()):
                if spend <= 0:
                    continue
                m = daily_metrics.get(day, {})
                expenses.append({
                    "datum": day,
                    "kategori": "Marknadsföring",
                    "beskrivning": f"Google Ads ({m.get('impressions', 0)} visn, {m.get('clicks', 0)} klick)",
                    "belopp": round(spend, 2),
                    "moms_sats": 0,
                    "source": "google_ads",
                    "source_id": f"gads_{day}",
                })

        except Exception as e:
            logger.error(f"Google Ads sync error: {e}")
            self.errors.append(str(e)[:200])

        return {"expenses": expenses, "revenue": [], "raw_data": {"days": len(expenses)}}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ADAPTERS = {
    "shopify": ShopifyAdapter,
    "gelato": GelatoAdapter,
    "tiktok_ads": TikTokAdsAdapter,
    "meta_ads": MetaAdsAdapter,
    "snapchat_ads": SnapchatAdsAdapter,
    "google_ads": GoogleAdsAdapter,
}


def get_adapter_class(platform: str):
    """Get adapter class by platform key."""
    return ADAPTERS.get(platform)


def get_all_platforms() -> list[dict]:
    """Return metadata about all available integrations."""
    result = []
    for key, cls in ADAPTERS.items():
        result.append({
            "platform": cls.PLATFORM,
            "display_name": cls.DISPLAY_NAME,
            "icon": cls.ICON,
            "description": cls.DESCRIPTION,
            "required_fields": cls.REQUIRED_FIELDS,
        })
    return result


def create_adapter(platform: str, config: dict) -> IntegrationAdapter | None:
    """Factory: create an adapter instance for the given platform."""
    cls = ADAPTERS.get(platform)
    if not cls:
        return None
    return cls(config)
