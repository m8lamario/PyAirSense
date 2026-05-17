"""Server Flask-SocketIO per AirSense."""

from __future__ import annotations

import os
import threading
from typing import Any, Dict

from flask import Flask, jsonify
from flask_socketio import SocketIO

from airsense import processor, serial_reader, simulate

APP_HOST = "0.0.0.0"
APP_PORT = 5000

app = Flask(__name__)
app.config["SECRET_KEY"] = "airsense-dev"

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.get("/api/history")
def api_history():
    history = processor.read_history(limit=100)
    return jsonify(history)


def _emit_data(data: Dict[str, Any]) -> None:
    enriched = processor.process(data)
    socketio.emit("new_data", enriched)


def _start_serial_thread() -> None:
    thread = threading.Thread(target=serial_reader.read_serial, args=(_emit_data,))
    thread.daemon = True
    thread.start()


def _start_simulation_thread() -> None:
    thread = threading.Thread(target=simulate.run_simulation, args=(_emit_data,))
    thread.daemon = True
    thread.start()


def main() -> None:
    #use_sim = os.getenv("AIRSENSE_SIMULATE", "0") == "1"
    use_sim = True
    if use_sim:
        _start_simulation_thread()
    else:
        _start_serial_thread()

    socketio.run(app, host=APP_HOST, port=APP_PORT)


if __name__ == "__main__":
    main()
