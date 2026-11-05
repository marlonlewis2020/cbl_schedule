"""Sandbox-only hosted subscriptions and durable billing reconciliation."""

import calendar
import hashlib
import json
import os
import re
import secrets
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import quote, urlsplit

import requests
from flask import g, jsonify, request, session

SCHEMA = """
CREATE TABLE IF NOT EXISTS billing_configuration (
    id INTEGER PRIMARY KEY, payload TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS billing_accounts (
    tenant_id TEXT PRIMARY KEY, subscription_id TEXT UNIQUE, checkout_id TEXT NOT NULL,
    plan_id TEXT NOT NULL DEFAULT '',
    tier TEXT NOT NULL, period TEXT NOT NULL, auto_renew INTEGER NOT NULL,
    provider_status TEXT NOT NULL, access_state TEXT NOT NULL DEFAULT 'active',
    paid_until TEXT, retry_count INTEGER NOT NULL DEFAULT 0, next_retry INTEGER,
    retry_state TEXT NOT NULL DEFAULT 'idle', last_error TEXT,
    last_payment TEXT, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS billing_events (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, kind TEXT NOT NULL,
    detail TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS billing_webhook_receipts (
    id TEXT PRIMARY KEY, applied INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS billing_subscription_index (
    subscription_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS billing_worker_status (
    id INTEGER PRIMARY KEY, heartbeat INTEGER NOT NULL
);
"""


class PaymentError(Exception):
    def __init__(self, message, *, unknown=False):
        super().__init__(message)
        self.unknown = unknown


class PayPalSandbox:
    base_url = "https://api-m.sandbox.paypal.com"

    @staticmethod
    def configured():
        return bool(os.getenv("PAYPAL_SANDBOX_CLIENT_ID") and
                    os.getenv("PAYPAL_SANDBOX_CLIENT_SECRET") and
                    os.getenv("PAYPAL_SANDBOX_WEBHOOK_ID"))

    def api(self, method, path, payload=None, request_id=None):
        if not self.configured():
            raise PaymentError("PayPal sandbox credentials and webhook ID are not configured.")
        try:
            token = requests.post(
                self.base_url + "/v1/oauth2/token",
                auth=(os.environ["PAYPAL_SANDBOX_CLIENT_ID"], os.environ["PAYPAL_SANDBOX_CLIENT_SECRET"]),
                data={"grant_type": "client_credentials"}, timeout=30,
            )
            if not token.ok:
                raise PaymentError("PayPal sandbox authentication failed.")
            token_payload = token.json()
            if not isinstance(token_payload.get("access_token"), str):
                raise PaymentError("PayPal sandbox returned an invalid authentication response.")
            headers = {"Authorization": "Bearer " + token_payload["access_token"],
                       "Content-Type": "application/json"}
            if request_id:
                headers["PayPal-Request-Id"] = request_id
            result = requests.request(method, self.base_url + path, json=payload,
                                      headers=headers, timeout=30)
        except requests.RequestException as error:
            raise PaymentError("PayPal sandbox is unreachable; reconcile before retrying payment mutations.",
                               unknown=method != "GET") from error
        if not result.ok:
            raise PaymentError(f"PayPal sandbox rejected the request (HTTP {result.status_code}).",
                               unknown=result.status_code >= 500 and method != "GET")
        try:
            return result.json() if result.content else {}
        except ValueError as error:
            raise PaymentError("PayPal sandbox returned invalid JSON.",
                               unknown=method != "GET") from error

    def subscription(self, subscription_id):
        return self.api("GET", "/v1/billing/subscriptions/" + quote(subscription_id, safe=""))

    def verify_webhook(self, event, headers):
        required = ("PAYPAL-AUTH-ALGO", "PAYPAL-CERT-URL", "PAYPAL-TRANSMISSION-ID",
                    "PAYPAL-TRANSMISSION-SIG", "PAYPAL-TRANSMISSION-TIME")
        if any(not headers.get(key) for key in required):
            return False
        response = self.api("POST", "/v1/notifications/verify-webhook-signature", {
            "auth_algo": headers["PAYPAL-AUTH-ALGO"], "cert_url": headers["PAYPAL-CERT-URL"],
            "transmission_id": headers["PAYPAL-TRANSMISSION-ID"],
            "transmission_sig": headers["PAYPAL-TRANSMISSION-SIG"],
            "transmission_time": headers["PAYPAL-TRANSMISSION-TIME"],
            "webhook_id": os.environ["PAYPAL_SANDBOX_WEBHOOK_ID"], "webhook_event": event,
        })
        return response.get("verification_status") == "SUCCESS"


def config(c):
    row = c.execute("SELECT payload FROM billing_configuration WHERE id=1").fetchone()
    return json.loads(row[0]) if row else {"enabled": False, "prices": {}, "plans": {}, "features": {}}


def access_suspended(c, tenant):
    row = c.execute("SELECT access_state FROM billing_accounts WHERE tenant_id=?", (tenant,)).fetchone()
    return bool(row and row[0] == "suspended")


def features(c, tier, defaults):
    return dict(defaults, **config(c).get("features", {}).get(tier, {}))


def audit(c, tenant, kind, detail, event_id=None):
    c.execute(
        "INSERT INTO billing_events(id,tenant_id,kind,detail,created_at) VALUES(?,?,?,?,?)",
        (event_id or secrets.token_urlsafe(18), tenant, kind, detail,
         datetime.now(timezone.utc).isoformat(timespec="microseconds")),
    )


def paid_period_end(value, period):
    paid = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if paid.tzinfo is None:
        raise PaymentError("PayPal returned a payment time without a time zone.")
    month = paid.month + (12 if period == "annual" else 1)
    year = paid.year + (month - 1) // 12
    month = (month - 1) % 12 + 1
    return paid.replace(year=year, month=month,
                        day=min(paid.day, calendar.monthrange(year, month)[1])).isoformat()


def membership_action(c, tenant, provider, action):
    row = c.execute("SELECT subscription_id,auto_renew FROM billing_accounts WHERE tenant_id=?", (tenant,)).fetchone()
    if not row or not row[0]:
        return
    subscription = provider.subscription(row[0])
    status = subscription["status"]
    operations = {"pause": ("suspend", "SUSPENDED"), "resume": ("activate", "ACTIVE"),
                  "cancel": ("cancel", "CANCELLED")}
    if action not in operations:
        return
    operation, expected = operations[action]
    if status == expected or status in {"CANCELLED", "EXPIRED"}:
        return
    provider.api("POST", "/v1/billing/subscriptions/" + quote(row[0], safe="") + "/" + operation,
                 {"reason": "Main administrator membership action: " + action})
    verified = provider.subscription(row[0])
    if verified["status"] != expected:
        raise PaymentError("The sandbox membership action is not yet verified. Reconcile before retrying.",
                           unknown=True)
    c.execute("UPDATE billing_accounts SET provider_status=? WHERE tenant_id=?", (expected, tenant))
    if action == "cancel":
        c.execute("UPDATE billing_accounts SET retry_state='cancelled',next_retry=NULL WHERE tenant_id=?", (tenant,))
    audit(c, tenant, "membership-" + action, "Sandbox subscription action verified.")


def reconcile(c, tenant, provider, subscription):
    row = c.execute(
        "SELECT subscription_id,checkout_id,tier,period,provider_status,last_payment,retry_state,paid_until "
        "FROM billing_accounts WHERE tenant_id=?", (tenant,),
    ).fetchone()
    if not row or subscription.get("id") != row[0] or subscription.get("custom_id") != row[1]:
        raise PaymentError("The PayPal subscription does not match this business checkout.")
    info = subscription.get("billing_info", {})
    payment = info.get("last_payment", {}).get("time")
    balance = info.get("outstanding_balance", {})
    try:
        outstanding = Decimal(balance.get("value", "0"))
    except InvalidOperation as error:
        raise PaymentError("PayPal returned an invalid outstanding balance.") from error
    if not outstanding.is_finite() or outstanding < 0 or balance.get("currency_code", "USD") != "USD":
        raise PaymentError("PayPal returned an unsupported outstanding balance.")
    status = subscription.get("status")
    if status not in {"APPROVAL_PENDING", "APPROVED", "ACTIVE", "SUSPENDED", "CANCELLED", "EXPIRED"}:
        raise PaymentError("PayPal returned an unsupported subscription status.")
    if payment and outstanding == 0 and (payment != row[5] or row[6] in {"running", "unknown", "failed"}):
        until = paid_period_end(payment, row[3])
        if row[7] and datetime.fromisoformat(row[7]) > datetime.fromisoformat(until):
            until = row[7]
        c.execute(
            "UPDATE billing_accounts SET paid_until=?,last_payment=?,retry_count=0,next_retry=NULL,"
            "retry_state='idle',access_state='active',last_error=NULL WHERE tenant_id=?",
            (until, payment, tenant),
        )
        # A payment must not undo an administrator's pause, cancellation or business suspension.
        c.execute("UPDATE tenants SET membership_tier=? WHERE tenant_id=?", (row[2], tenant))
        audit(c, tenant, "payment-reconciled", "Verified sandbox payment; billing access restored.")
    if outstanding > 0 and row[6] == "idle":
        c.execute(
            "UPDATE billing_accounts SET retry_state='failed',next_retry=? WHERE tenant_id=?",
            (int(time.time()) + 86400, tenant),
        )
        audit(c, tenant, "payment-reminder", "Outstanding sandbox balance; retry scheduled in one day.")
    c.execute(
        "UPDATE billing_accounts SET provider_status=?,updated_at=CURRENT_TIMESTAMP WHERE tenant_id=?",
        (status, tenant),
    )
    return outstanding, balance, status


def register(app, s):
    provider = PayPalSandbox()

    @app.route("/api/hub/billing", methods=["GET", "PUT"])
    def owner_configuration():
        denied = s.platform_owner_guard()
        if denied:
            return denied
        with closing(s.database_connect()) as c, c:
            current = config(c)
            if request.method == "GET":
                worker = c.execute("SELECT heartbeat FROM billing_worker_status WHERE id=1").fetchone()
                return jsonify(configuration=current, provider="paypal-sandbox",
                               tierDefinitions=s.MEMBERSHIP_TIERS,
                               credentialsConfigured=provider.configured(),
                               workerHealthy=bool(worker and time.time() - worker[0] < 180))
            p = request.get_json(silent=True)
            if not isinstance(p, dict) or p.get("confirmed") is not True or type(p.get("enabled")) is not bool:
                return jsonify(error="Confirm the sandbox billing configuration."), 400
            if not isinstance(p.get("prices"), dict) or not isinstance(p.get("features", {}), dict):
                return jsonify(error="Prices and feature overrides must be objects."), 400
            prices = {}
            try:
                for tier in s.MEMBERSHIP_TIERS:
                    for period in ("monthly", "annual"):
                        key = tier + ":" + period
                        value = Decimal(str(p["prices"].get(key, "0")))
                        if not value.is_finite() or value < Decimal("0.01") or value > Decimal("99999.99") or value != value.quantize(Decimal("0.01")):
                            raise ValueError("Set all eight USD monthly/annual prices, with at most two decimal places.")
                        prices[key] = format(value, ".2f")
                for tier, overrides in p.get("features", {}).items():
                    if tier not in s.MEMBERSHIP_TIERS or not isinstance(overrides, dict) or any(
                        key not in s.MEMBERSHIP_TIERS[tier]["features"] or type(value) is not bool
                        for key, value in overrides.items()
                    ):
                        raise ValueError("Choose known tier feature names with true/false values.")
            except (ValueError, InvalidOperation) as error:
                return jsonify(error=str(error)), 400
            worker = c.execute("SELECT heartbeat FROM billing_worker_status WHERE id=1").fetchone()
            if p["enabled"] and (not provider.configured() or len(current.get("plans", {})) != 16 or current.get("prices") != prices or not worker or time.time() - worker[0] >= 180):
                return jsonify(error="Save prices with billing disabled, prepare all sandbox plans, configure credentials and start the dedicated worker before enabling."), 409
            plans = current.get("plans", {}) if current.get("prices") == prices else {}
            value = {"enabled": p["enabled"], "prices": prices, "plans": plans,
                     "features": p.get("features", {})}
            c.execute(
                "INSERT INTO billing_configuration(id,payload) VALUES(1,?) "
                "ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,updated_at=CURRENT_TIMESTAMP",
                (json.dumps(value),),
            )
            s.hub_audit(c, "billing-configuration", detail="Sandbox prices/features updated.",
                        actor_email=session.get("platform_owner_email"))
        return jsonify(configuration=value)

    @app.post("/api/hub/billing/prepare")
    def prepare_plans():
        denied = s.platform_owner_guard()
        if denied:
            return denied
        p = request.get_json(silent=True)
        if not isinstance(p, dict) or p.get("confirmed") is not True:
            return jsonify(error="Confirm creation of sandbox products and plans."), 400
        with closing(s.database_connect()) as c:
            settings = config(c)
        if len(settings["prices"]) != 8 or settings["enabled"]:
            return jsonify(error="Configure eight prices and disable billing before preparing plans."), 409
        fingerprint = hashlib.sha256(json.dumps(settings["prices"], sort_keys=True).encode()).hexdigest()[:24]
        try:
            product = provider.api("POST", "/v1/catalogs/products", {
                "name": "CBL Schedule Creator sandbox", "type": "SERVICE", "category": "SOFTWARE",
            }, "cbl-product-" + fingerprint)
            if not isinstance(product.get("id"), str):
                raise PaymentError("PayPal did not return a product ID.")
            plans = {}
            for key, amount in settings["prices"].items():
                for renew in (0, 1):
                    plan_key = key + ":" + str(renew)
                    plan = provider.api("POST", "/v1/billing/plans", {
                        "product_id": product["id"], "name": "CBL " + plan_key, "status": "ACTIVE",
                        "billing_cycles": [{
                            "frequency": {"interval_unit": "YEAR" if key.endswith("annual") else "MONTH", "interval_count": 1},
                            "tenure_type": "REGULAR", "sequence": 1, "total_cycles": 0 if renew else 1,
                            "pricing_scheme": {"fixed_price": {"value": amount, "currency_code": "USD"}},
                        }],
                        "payment_preferences": {"auto_bill_outstanding": False, "payment_failure_threshold": 1},
                    }, hashlib.sha256((fingerprint + plan_key).encode()).hexdigest()[:36])
                    if not re.fullmatch(r"P-[A-Z0-9]{24}", str(plan.get("id", ""))):
                        raise PaymentError("PayPal did not return a valid plan ID.")
                    plans[plan_key] = plan["id"]
        except PaymentError as error:
            return jsonify(error=str(error), outcome="unknown" if error.unknown else "failed"), 502
        with closing(s.database_connect()) as c, c:
            if config(c)["prices"] != settings["prices"]:
                return jsonify(error="Prices changed while preparing plans. Prepare again."), 409
            settings = config(c)
            settings["plans"] = plans
            c.execute("UPDATE billing_configuration SET payload=? WHERE id=1", (json.dumps(settings),))
            s.hub_audit(c, "billing-plans-prepared", detail="Sandbox subscription plans prepared.",
                        actor_email=session.get("platform_owner_email"))
        return jsonify(configuration=settings)

    @app.route("/api/business/billing", methods=["GET", "POST"])
    def business_billing():
        denied = s.primary_admin_guard()
        if denied:
            return denied
        if request.method == "POST" and not s.tenant_auth_csrf_valid():
            return jsonify(error="The request token is invalid."), 400
        tenant = s.active_tenant_id()
        with closing(s.database_connect()) as c, c:
            settings = config(c)
            row = c.execute(
                "SELECT subscription_id,tier,period,auto_renew,provider_status,access_state,"
                "paid_until,retry_count,retry_state,last_error FROM billing_accounts WHERE tenant_id=?",
                (tenant,),
            ).fetchone()
            if request.method == "GET":
                history = c.execute("SELECT kind,detail,created_at FROM billing_events WHERE tenant_id=? ORDER BY created_at DESC LIMIT 30", (tenant,)).fetchall()
                return jsonify(enabled=settings["enabled"] and provider.configured(),
                               prices=settings["prices"], account=dict(zip(
                                   ("subscriptionId", "tier", "period", "autoRenew", "providerStatus",
                                    "accessState", "paidUntil", "retryCount", "retryState", "lastError"), row
                               )) if row else None, reminders=[
                                   {"kind": r[0], "detail": r[1], "createdAt": r[2]} for r in history
                               ], provider="paypal-sandbox")
            p = request.get_json(silent=True)
            if not isinstance(p, dict) or p.get("confirmed") is not True:
                return jsonify(error="Confirm the hosted sandbox checkout."), 400
            tier, period = p.get("tier"), p.get("period")
            if tier not in s.MEMBERSHIP_TIERS or period not in {"monthly", "annual"} or type(p.get("autoRenew")) is not bool:
                return jsonify(error="Choose a tier, monthly/annual period and auto-renew preference."), 400
            if not settings["enabled"] or not provider.configured():
                return jsonify(error="Sandbox billing is disabled until the platform owner configures it."), 503
            if row and row[4] not in {"CANCELLED", "EXPIRED"}:
                return jsonify(error="A checkout already exists. Reconcile or cancel it before starting another."), 409
            plan = settings["plans"].get(f"{tier}:{period}:{int(p['autoRenew'])}")
            if not plan:
                return jsonify(error="No prepared sandbox plan exists for that selection."), 409
            checkout_id = secrets.token_urlsafe(24)
            c.execute(
                "INSERT INTO billing_accounts(tenant_id,checkout_id,plan_id,tier,period,auto_renew,provider_status,retry_state) "
                "VALUES(?,?,?,?,?,?,'CREATING','checkout') ON CONFLICT(tenant_id) DO UPDATE SET "
                "checkout_id=excluded.checkout_id,plan_id=excluded.plan_id,tier=excluded.tier,period=excluded.period,"
                "auto_renew=excluded.auto_renew,provider_status='CREATING',retry_state='checkout',"
                "subscription_id=NULL,last_payment=NULL,retry_count=0,next_retry=NULL,last_error=NULL",
                (tenant, checkout_id, plan, tier, period, int(p["autoRenew"])),
            )
        try:
            subscription = provider.api("POST", "/v1/billing/subscriptions", {
                "plan_id": plan, "custom_id": checkout_id,
                "application_context": {"brand_name": "CBL Schedule", "shipping_preference": "NO_SHIPPING",
                                        "user_action": "SUBSCRIBE_NOW"},
            }, checkout_id)
            sub_id = subscription.get("id")
            approval = next((link["href"] for link in subscription.get("links", [])
                             if link.get("rel") == "approve"), None)
            if not re.fullmatch(r"I-[A-Z0-9]+", str(sub_id)) or subscription.get("status") not in {"APPROVAL_PENDING", "APPROVED"} or not isinstance(approval, str) or urlsplit(approval).scheme != "https" or urlsplit(approval).hostname not in {"www.sandbox.paypal.com", "sandbox.paypal.com"}:
                raise PaymentError("PayPal returned an invalid sandbox checkout.", unknown=True)
        except PaymentError as error:
            with closing(s.database_connect()) as c, c:
                c.execute("UPDATE billing_accounts SET last_error=?,retry_state=? WHERE tenant_id=?",
                          (str(error), "unknown" if error.unknown else "checkout_failed", tenant))
                audit(c, tenant, "checkout-failed", str(error))
            return jsonify(error=str(error), outcome="unknown" if error.unknown else "failed"), 502
        with closing(s.database_connect()) as c, c:
            c.execute(
                "UPDATE billing_accounts SET subscription_id=?,provider_status=?,retry_state='idle' WHERE tenant_id=?",
                (sub_id, subscription["status"], tenant),
            )
            c.execute("INSERT INTO billing_subscription_index(subscription_id,tenant_id) VALUES(?,?)",
                      (sub_id, tenant))
            audit(c, tenant, "checkout-created", "Hosted sandbox checkout created; payment is not yet verified.")
        return jsonify(approvalUrl=approval, subscriptionId=sub_id), 201

    @app.post("/api/business/billing/reconcile")
    def reconcile_business():
        denied = s.primary_admin_guard()
        if denied:
            return denied
        if not s.tenant_auth_csrf_valid():
            return jsonify(error="The request token is invalid."), 400
        tenant = s.active_tenant_id()
        with closing(s.database_connect()) as c:
            row = c.execute("SELECT subscription_id FROM billing_accounts WHERE tenant_id=?", (tenant,)).fetchone()
        if not row or not row[0]:
            return jsonify(error="No subscription exists. Unknown checkout outcomes require platform-owner reconciliation."), 409
        try:
            subscription = provider.subscription(row[0])
            with closing(s.database_connect()) as c, c:
                reconcile(c, tenant, provider, subscription)
        except PaymentError as error:
            return jsonify(error=str(error)), 502
        return jsonify(reconciled=True)

    @app.post("/api/hub/billing/manual-payment")
    def manual_payment():
        denied = s.platform_owner_guard()
        if denied:
            return denied
        p = request.get_json(silent=True)
        if not isinstance(p, dict) or p.get("confirmed") is not True or not isinstance(p.get("reason"), str) or not 1 <= len(p["reason"].strip()) <= 500:
            return jsonify(error="Confirm the manual payment with an audit reason."), 400
        try:
            until = datetime.fromisoformat(str(p.get("paidUntil", "")).replace("Z", "+00:00"))
            if until.tzinfo is None or until <= datetime.now(timezone.utc):
                raise ValueError("Provide a future paid-until time including its time zone.")
        except ValueError as error:
            return jsonify(error=str(error)), 400
        tenant = p.get("tenantId")
        if not isinstance(tenant, str):
            return jsonify(error="Choose a business."), 400
        g.tenant_id = tenant
        with closing(s.database_connect()) as c, c:
            updated = c.execute(
                "UPDATE billing_accounts SET access_state='active',paid_until=?,retry_state='manual',"
                "next_retry=NULL,last_error=NULL WHERE tenant_id=?",
                (until.isoformat(), tenant),
            )
            if updated.rowcount != 1:
                return jsonify(error="No billing account exists for that business."), 404
            audit(c, tenant, "manual-payment", p["reason"].strip())
            s.hub_audit(c, "manual-payment", tenant, p["reason"].strip(),
                        session.get("platform_owner_email"))
        return jsonify(restored=True, warning="Manual credit does not cancel or settle PayPal charges. Automatic app retries are stopped; reconcile PayPal separately.")

    @app.post("/api/hub/billing/recover-checkout")
    def recover_checkout():
        denied = s.platform_owner_guard()
        if denied:
            return denied
        p = request.get_json(silent=True)
        if not isinstance(p, dict) or p.get("confirmed") is not True or not isinstance(p.get("tenantId"), str) or not re.fullmatch(r"I-[A-Z0-9]+", str(p.get("subscriptionId", ""))):
            return jsonify(error="Confirm the business and sandbox subscription ID found in PayPal."), 400
        tenant = p["tenantId"]
        g.tenant_id = tenant
        try:
            subscription = provider.subscription(p["subscriptionId"])
            with closing(s.database_connect()) as c, c:
                row = c.execute("SELECT checkout_id,plan_id,subscription_id FROM billing_accounts WHERE tenant_id=?", (tenant,)).fetchone()
                if not row or row[2] or subscription.get("custom_id") != row[0] or subscription.get("plan_id") != row[1]:
                    return jsonify(error="The subscription does not match this unresolved checkout."), 409
                c.execute("UPDATE billing_accounts SET subscription_id=?,provider_status=?,retry_state='idle',last_error=NULL WHERE tenant_id=?",
                          (subscription["id"], subscription["status"], tenant))
                c.execute("INSERT INTO billing_subscription_index VALUES(?,?)", (subscription["id"], tenant))
                reconcile(c, tenant, provider, subscription)
                audit(c, tenant, "checkout-recovered", "Verified sandbox subscription recovered by platform owner.")
                s.hub_audit(c, "checkout-recovered", tenant, "Verified unresolved sandbox checkout.",
                            session.get("platform_owner_email"))
        except PaymentError as error:
            return jsonify(error=str(error)), 502
        return jsonify(recovered=True)

    @app.post("/api/business/billing/cancel")
    def cancel_subscription():
        denied = s.primary_admin_guard()
        if denied:
            return denied
        p = request.get_json(silent=True)
        if not isinstance(p, dict) or p.get("confirmed") is not True:
            return jsonify(error="Confirm cancellation of the sandbox subscription."), 400
        tenant = s.active_tenant_id()
        with closing(s.database_connect()) as c:
            row = c.execute("SELECT subscription_id,retry_state FROM billing_accounts WHERE tenant_id=?", (tenant,)).fetchone()
        if not row:
            return jsonify(error="No checkout exists."), 404
        if not row[0] and row[1] != "checkout_failed":
            return jsonify(error="An unknown checkout must be recovered by the platform owner before cancellation."), 409
        try:
            if row[0]:
                subscription = provider.subscription(row[0])
                if subscription["status"] not in {"CANCELLED", "EXPIRED"}:
                    provider.api("POST", "/v1/billing/subscriptions/" + quote(row[0], safe="") + "/cancel",
                                 {"reason": "Main business administrator cancelled sandbox billing."})
                    subscription = provider.subscription(row[0])
                    if subscription["status"] != "CANCELLED":
                        raise PaymentError("Cancellation is not yet verified. Reconcile before creating another checkout.", unknown=True)
            with closing(s.database_connect()) as c, c:
                # Keep immutable billing events and the opaque webhook index.
                c.execute("UPDATE billing_accounts SET provider_status='CANCELLED',retry_state='cancelled',next_retry=NULL WHERE tenant_id=?", (tenant,))
                audit(c, tenant, "subscription-cancelled", "Sandbox cancellation verified. Existing app membership was not cancelled or refunded.")
        except PaymentError as error:
            return jsonify(error=str(error), outcome="unknown" if error.unknown else "failed"), 502
        return jsonify(cancelled=True, warning="Sandbox subscription cancelled; existing app membership is unchanged. No refund was issued.")

    @app.post("/api/payments/paypal/webhook")
    def paypal_webhook():
        if request.content_length and request.content_length > 1048576:
            return jsonify(error="Webhook exceeds the size limit."), 413
        event = request.get_json(silent=True)
        if not isinstance(event, dict) or not isinstance(event.get("id"), str) or len(event["id"]) > 200:
            return jsonify(error="Invalid webhook event."), 400
        try:
            if not provider.verify_webhook(event, request.headers):
                return jsonify(error="Webhook signature verification failed."), 400
            resource = event.get("resource", {})
            sub_id = resource.get("billing_agreement_id") or resource.get("id")
            with closing(s.database_connect()) as c:
                row = c.execute(
                    "SELECT tenant_id FROM billing_subscription_index WHERE subscription_id=?", (sub_id,),
                ).fetchone()
            if not row:
                return jsonify(error="The subscription is not registered."), 404
            g.tenant_id = row[0]
            with closing(s.database_connect()) as c:
                current = c.execute("SELECT subscription_id FROM billing_accounts WHERE tenant_id=?", (row[0],)).fetchone()
                if not current or current[0] != sub_id:
                    return jsonify(ignored=True, reason="Subscription is no longer current.")
            subscription = provider.subscription(sub_id)
            with closing(s.database_connect()) as c, c:
                applied = c.execute(
                    "INSERT INTO billing_webhook_receipts(id,applied) VALUES(?,0) ON CONFLICT(id) DO NOTHING",
                    (event["id"],),
                )
                if applied.rowcount == 0:
                    return jsonify(duplicate=True)
                reconcile(c, row[0], provider, subscription)
                audit(c, row[0], "webhook-verified", str(event.get("event_type", ""))[:200])
                c.execute("UPDATE billing_webhook_receipts SET applied=1 WHERE id=?", (event["id"],))
        except PaymentError as error:
            return jsonify(error=str(error)), 502
        return jsonify(verified=True)

    return provider


def run_once(s, provider):
    """Run a bounded sweep; only claimed, due, explicitly failed payments may be retried."""
    now = int(time.time())
    with closing(s.database_connect()) as c, c:
        c.execute("INSERT INTO billing_worker_status(id,heartbeat) VALUES(1,?) "
                  "ON CONFLICT(id) DO UPDATE SET heartbeat=excluded.heartbeat", (now,))
        if not config(c)["enabled"]:
            return
        tenants = [row[0] for row in c.execute("SELECT tenant_id FROM tenants WHERE status='active' AND membership_status='active'")]
    for tenant in tenants:
        g.tenant_id = tenant
        with closing(s.database_connect()) as c:
            polling = c.execute("SELECT subscription_id,retry_state,next_retry FROM billing_accounts WHERE tenant_id=?", (tenant,)).fetchone()
        if polling and polling[0] and polling[1] == "idle" and (not polling[2] or polling[2] <= now):
            try:
                subscription = provider.subscription(polling[0])
                with closing(s.database_connect()) as c, c:
                    reconcile(c, tenant, provider, subscription)
                    c.execute("UPDATE billing_accounts SET next_retry=? WHERE tenant_id=? AND retry_state='idle'", (now + 600, tenant))
            except PaymentError as error:
                with closing(s.database_connect()) as c, c:
                    c.execute("UPDATE billing_accounts SET last_error=?,next_retry=? WHERE tenant_id=?",
                              (str(error), now + 600, tenant))
                    audit(c, tenant, "reconciliation-failed", str(error))
        with closing(s.database_connect()) as c, c:
            row = c.execute(
                "SELECT subscription_id,retry_count,next_retry,retry_state,paid_until,auto_renew "
                "FROM billing_accounts WHERE tenant_id=?", (tenant,),
            ).fetchone()
            if not row or not row[0]:
                continue
            if row[4] and datetime.fromisoformat(row[4]) <= datetime.now(timezone.utc) and not (
                row[5] and row[3] in {"failed", "running"} and row[1] < 7
            ):
                c.execute("UPDATE billing_accounts SET access_state='suspended' WHERE tenant_id=?", (tenant,))
            if row[3] == "running" and row[2] and row[2] <= now:
                c.execute("UPDATE billing_accounts SET retry_state='unknown',last_error=? WHERE tenant_id=?",
                          ("Worker interrupted during payment attempt. Reconcile before retrying.", tenant))
                audit(c, tenant, "payment-unknown", "Interrupted payment needs reconciliation.")
                continue
            if row[3] != "failed" or not row[2] or row[2] > now or row[1] >= 7:
                continue
            claimed = c.execute(
                "UPDATE billing_accounts SET retry_state='running',next_retry=? "
                "WHERE tenant_id=? AND retry_state='failed' AND retry_count=? AND next_retry<=?",
                (now + 86400, tenant, row[1], now),
            )
            if claimed.rowcount != 1:
                continue
        attempted = False
        try:
            sub = provider.subscription(row[0])
            with closing(s.database_connect()) as c, c:
                outstanding, balance, status = reconcile(c, tenant, provider, sub)
            if outstanding == 0:
                with closing(s.database_connect()) as c, c:
                    c.execute("UPDATE billing_accounts SET retry_state='idle',next_retry=NULL WHERE tenant_id=?", (tenant,))
                continue
            attempted = True
            provider.api("POST", "/v1/billing/subscriptions/" + quote(row[0], safe="") + "/capture", {
                "note": "CBL sandbox membership outstanding payment",
                "capture_type": "OUTSTANDING_BALANCE", "amount": balance,
            }, hashlib.sha256((row[0] + ":" + str(row[1] + 1)).encode()).hexdigest()[:36])
            # Never restore access from the HTTP mutation response alone.
            sub = provider.subscription(row[0])
            with closing(s.database_connect()) as c, c:
                remaining, _, _ = reconcile(c, tenant, provider, sub)
                if remaining:
                    raise PaymentError("Capture accepted but balance is not settled; reconcile before retrying.", unknown=True)
                if status == "SUSPENDED" and row[5]:
                    provider.api("POST", "/v1/billing/subscriptions/" + quote(row[0], safe="") + "/activate",
                                 {"reason": "Verified outstanding sandbox balance paid."})
                audit(c, tenant, "retry-paid", "Verified sandbox retry payment.")
        except PaymentError as error:
            count = row[1] + int(attempted)
            with closing(s.database_connect()) as c, c:
                c.execute(
                    "UPDATE billing_accounts SET retry_count=?,retry_state=?,next_retry=?,last_error=?,"
                    "access_state=CASE WHEN ? THEN 'suspended' ELSE access_state END WHERE tenant_id=?",
                    (count, "unknown" if error.unknown else "exhausted" if count >= 7 else "failed",
                     None if error.unknown or count >= 7 else now + 86400, str(error), count >= 7, tenant),
                )
                audit(c, tenant, "retry-failed", str(error))
