from pathlib import Path

from flask import Flask, abort, send_from_directory


APP_DIRECTORY = Path(__file__).resolve().parent
STATIC_ASSETS = {
    "CBL-Scheduler2.css",
    "CBL-Scheduler2.config.js",
    "CBL-Scheduler2.js",
    "CBL-MicrosoftAuth.html",
}

app = Flask(__name__, static_folder=None)


@app.get("/")
def index():
    return send_from_directory(APP_DIRECTORY, "CBL-Scheduler2.html")


@app.get("/<path:asset_name>")
def serve_asset(asset_name):
    if asset_name not in STATIC_ASSETS:
        abort(404)
    return send_from_directory(APP_DIRECTORY, asset_name)


def main() -> None:
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
