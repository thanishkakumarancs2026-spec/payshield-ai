"""PayShield AI: explainable fraud monitoring with a PayPal Sandbox checkout."""
from __future__ import annotations

import base64
import math
import random
from sklearn.ensemble import IsolationForest
import json
import os
import secrets
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from threading import Lock

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "local-demo-change-me")
lock = Lock()

PRODUCTS = {
    "headphones": {"name": "Wireless headphones", "price": "89.00"},
    "watch": {"name": "Smart watch", "price": "149.00"},
    "camera": {"name": "Instant camera", "price": "119.00"},
}

def transaction_features(tx):
    return [
        math.log1p(max(0.0, float(tx.get("amount", 0)))),
        int(bool(tx.get("new_device"))),
        int(bool(tx.get("country_mismatch"))),
        min(5, max(0, int(tx.get("failed_attempts", 0)))),
        int(bool(tx.get("rapid_repeat"))),
    ]


def train_anomaly_model():
    rng = random.Random(42)
    normal_examples = []

    for _ in range(500):
        example = {
            "amount": rng.lognormvariate(4.0, 0.55),
            "new_device": rng.random() < 0.08,
            "country_mismatch": rng.random() < 0.01,
            "failed_attempts": rng.choices(
                [0, 1, 2, 3], weights=[84, 11, 4, 1], k=1
            )[0],
            "rapid_repeat": rng.random() < 0.04,
        }
        normal_examples.append(transaction_features(example))

    model = IsolationForest(
        n_estimators=150,
        contamination=0.03,
        random_state=42,
    )
    model.fit(normal_examples)
    return model


anomaly_model = train_anomaly_model()


def score_transaction(tx: dict) -> dict:
    rule_score, reasons = 0, []
    amount = float(tx.get("amount", 0))

    if amount >= 500:
        rule_score += 35
        reasons.append("High purchase amount (≥ $500)")
    elif amount >= 250:
        rule_score += 20
        reasons.append("Elevated purchase amount (≥ $250)")
    if tx.get("country_mismatch"):
        rule_score += 30
        reasons.append("Billing and device locations differ")
    if tx.get("new_device"):
        rule_score += 20
        reasons.append("First purchase from this device")
    if tx.get("failed_attempts", 0) >= 3:
        rule_score += 25
        reasons.append("Three or more recent failed attempts")
    if tx.get("rapid_repeat"):
        rule_score += 20
        reasons.append("Several purchases in a short time")

    decision = float(
        anomaly_model.decision_function([transaction_features(tx)])[0]
    )
    ai_score = max(0, min(100, round(50 - 300 * decision)))
    score = min(100, max(rule_score, ai_score))

    if ai_score >= 60:
        reasons.append("AI model flagged an unusual transaction pattern")
    elif ai_score >= 30:
        reasons.append("AI model found a somewhat unusual pattern")
    elif not reasons:
        reasons.append("No unusual signals detected")

    level = "High" if score >= 60 else "Medium" if score >= 30 else "Low"
    return {
        "risk_score": score,
        "ai_score": ai_score,
        "risk_level": level,
        "reasons": reasons,
    }

def make_transaction(customer, amount, status="Approved", **signals):
    tx = {"id": f"TX-{secrets.token_hex(3).upper()}", "customer": customer,
          "amount": float(amount), "currency": "USD", "status": status,
          "time": datetime.now(timezone.utc).isoformat(), **signals}
    tx.update(score_transaction(tx))
    return tx

transactions = [
    make_transaction("Maya Patel", 89.00, "Approved"),
    make_transaction("Jordan Lee", 129.50, "Approved", new_device=True),
    make_transaction("Alex Morgan", 640.00, "Review", country_mismatch=True),
    make_transaction("Sam Rivera", 34.99, "Approved"),
    make_transaction("Taylor Chen", 310.00, "Blocked", failed_attempts=3),
    make_transaction("Casey Brooks", 78.25, "Approved", rapid_repeat=True),
]

def paypal_enabled():
    return bool(os.getenv("PAYPAL_CLIENT_ID") and os.getenv("PAYPAL_CLIENT_SECRET"))

def paypal_base():
    return "https://api-m.paypal.com" if os.getenv("PAYPAL_ENV") == "live" else "https://api-m.sandbox.paypal.com"

def paypal_request(path, payload=None, token=None):
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(paypal_base() + path, data=data, headers=headers,
                                 method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        raise ValueError(f"PayPal returned {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ValueError("Could not reach PayPal. Check your connection and Sandbox credentials.") from exc

def paypal_token():
    raw = f"{os.environ['PAYPAL_CLIENT_ID']}:{os.environ['PAYPAL_CLIENT_SECRET']}".encode()
    req = urllib.request.Request(paypal_base() + "/v1/oauth2/token", data=b"grant_type=client_credentials",
        headers={"Authorization": "Basic " + base64.b64encode(raw).decode(),
                 "Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read().decode())["access_token"]
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise ValueError("PayPal authentication failed. Check the Sandbox client ID and secret.") from exc

@app.get("/")
def dashboard():
    return render_template("dashboard.html", paypal_client_id=os.getenv("PAYPAL_CLIENT_ID", ""),
                           paypal_enabled=paypal_enabled())

@app.get("/api/transactions")
def list_transactions():
    with lock:
        return jsonify(list(reversed(transactions)))

@app.get("/api/config")
def config():
    return jsonify({"paypal_enabled": paypal_enabled(), "mode": "sandbox" if os.getenv("PAYPAL_ENV") != "live" else "live"})

@app.post("/api/transactions/simulate")
def simulate_transaction():
    data = request.get_json(silent=True) or {}
    customer = str(data.get("customer", "Demo customer")).strip()[:60] or "Demo customer"
    try:
        amount = float(Decimal(str(data.get("amount", "0"))))
        if not 1 <= amount <= 10000:
            raise ValueError()
    except (InvalidOperation, ValueError, TypeError):
        return jsonify({"error": "Enter an amount between $1 and $10,000."}), 400
    tx = make_transaction(customer, amount, "Review", new_device=bool(data.get("new_device")),
        country_mismatch=bool(data.get("country_mismatch")), failed_attempts=int(data.get("failed_attempts", 0)))
    with lock:
        transactions.append(tx)
    return jsonify(tx), 201

@app.post("/api/paypal/order")
def create_order():
    data = request.get_json(silent=True) or {}
    product = PRODUCTS.get(data.get("product"))
    if not product:
        return jsonify({"error": "Choose a listed demo product."}), 400
    if not paypal_enabled():
        return jsonify({"error": "Sandbox credentials are not set. Use the clearly labelled simulation checkout."}), 503
    try:
        result = paypal_request("/v2/checkout/orders", {"intent": "CAPTURE", "purchase_units": [{
            "reference_id": data.get("product"), "description": product["name"],
            "amount": {"currency_code": "USD", "value": product["price"]}}]}, paypal_token())
        return jsonify({"id": result["id"]})
    except (ValueError, KeyError) as exc:
        return jsonify({"error": str(exc)}), 502

@app.post("/api/paypal/capture")
def capture_order():
    data = request.get_json(silent=True) or {}
    order_id = str(data.get("orderID", ""))
    if not order_id or len(order_id) > 64 or not paypal_enabled():
        return jsonify({"error": "Invalid order or Sandbox credentials are missing."}), 400
    try:
        result = paypal_request(f"/v2/checkout/orders/{order_id}/capture", {}, paypal_token())
        capture = result["purchase_units"][0]["payments"]["captures"][0]
        amount = capture["amount"]["value"]
        tx = make_transaction("PayPal Sandbox buyer", amount, "Paid", new_device=True)
        tx["id"] = capture["id"]
        with lock:
            transactions.append(tx)
        return jsonify({"transaction": tx, "status": result.get("status")})
    except (ValueError, KeyError, IndexError) as exc:
        return jsonify({"error": str(exc)}), 502

@app.post("/api/paypal/demo")
def demo_payment():
    data = request.get_json(silent=True) or {}
    product = PRODUCTS.get(data.get("product"))
    if not product:
        return jsonify({"error": "Choose a listed demo product."}), 400
    tx = make_transaction("Sandbox demo buyer", product["price"], "Simulated", new_device=True)
    with lock:
        transactions.append(tx)
    return jsonify(tx), 201

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)
