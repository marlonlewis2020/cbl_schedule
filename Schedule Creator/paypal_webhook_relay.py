"""Loopback-only, webhook-only relay for temporary PayPal sandbox HTTPS tunnels."""

import argparse

import requests
from flask import Flask, Response, jsonify, request

WEBHOOK_PATH = "/api/payments/paypal/webhook"
SIGNATURE_HEADERS = (
    "PAYPAL-AUTH-ALGO", "PAYPAL-CERT-URL", "PAYPAL-TRANSMISSION-ID",
    "PAYPAL-TRANSMISSION-SIG", "PAYPAL-TRANSMISSION-TIME",
)


def create_app(app_port=5001):
    if type(app_port) is not int or not 1 <= app_port <= 65535:
        raise ValueError("Choose a valid local application port.")
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024
    target = f"http://127.0.0.1:{app_port}{WEBHOOK_PATH}"

    @app.post(WEBHOOK_PATH, provide_automatic_options=False)
    def relay_webhook():
        if not request.is_json:
            return jsonify(error="Send an application/json webhook."), 415
        if any(not request.headers.get(name) for name in SIGNATURE_HEADERS):
            return jsonify(error="PayPal signature headers are required."), 400
        headers = {name: request.headers.get(name) for name in SIGNATURE_HEADERS}
        headers["Content-Type"] = request.content_type
        body = request.get_data()
        try:
            with requests.Session() as client:
                client.trust_env = False
                response = client.post(
                    target, data=body, headers=headers,
                    timeout=(3, 90), allow_redirects=False,
                )
        except requests.RequestException:
            return jsonify(error="The local webhook service is unavailable."), 502
        return Response(
            response.content, status=response.status_code,
            content_type=response.headers.get("Content-Type", "application/json"),
            headers={"Cache-Control": "no-store"},
        )

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-port", type=int, default=5001)
    parser.add_argument("--listen-port", type=int, default=5100)
    arguments = parser.parse_args()
    if not 1 <= arguments.listen_port <= 65535:
        parser.error("Choose a valid relay port.")
    create_app(arguments.app_port).run(
        host="127.0.0.1", port=arguments.listen_port,
        debug=False, use_reloader=False,
    )


if __name__ == "__main__":
    main()