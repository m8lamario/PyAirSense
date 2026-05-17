"""Lettura seriale per AirSense con invio dati su Pusher."""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import deque
from typing import Any, Callable, Deque, Dict, Optional, Tuple

import collections
from collections.abc import Sized as _Sized

if not hasattr(collections, "Sized"):
    collections.Sized = _Sized

import pusher
import serial
from dotenv import load_dotenv

import simulate

DEFAULT_BAUD = 9600
DEFAULT_WARMUP = 10
DEFAULT_AVG_WINDOW = 5

ENV_PORT = "AIRSENSE_PORT"
ENV_PUSHER_APP_ID = "PUSHER_APP_ID"
ENV_PUSHER_KEY = "PUSHER_KEY"
ENV_PUSHER_SECRET = "PUSHER_SECRET"
ENV_PUSHER_CLUSTER = "PUSHER_CLUSTER"
ENV_PUSHER_CHANNEL = "PUSHER_CHANNEL"
ENV_PUSHER_EVENT = "PUSHER_EVENT"

COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"


def _log(tag: str, message: str, color: str) -> None:
    print(f"{color}{tag}{COLOR_RESET} {message}")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _compute_status(temp: float, gas: float) -> str:
    if temp > 35 or gas > 600:
        return "CRITICO"
    if temp >= 28 or gas >= 400:
        return "ATTENZIONE"
    if 15 <= temp < 28 and gas < 400:
        return "BUONO"
    return "ATTENZIONE"


def _get_port(cli_port: Optional[str]) -> Optional[str]:
    if cli_port:
        return cli_port
    return os.getenv(ENV_PORT)


def _safe_parse_json(line: str) -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(line)
        if isinstance(data, dict):
            return data
        return None
    except (json.JSONDecodeError, ValueError):
        return None


def _update_gas_avg(gas_values: Deque[float], data: Dict[str, Any]) -> None:
    gas = data.get("gas")
    try:
        gas_float = float(gas)
    except (TypeError, ValueError):
        return

    gas_values.append(gas_float)
    avg = sum(gas_values) / len(gas_values)
    data["gas_avg"] = round(avg, 2)


def _pusher_settings() -> Tuple[pusher.Pusher, str, str]:
    load_dotenv()
    app_id = os.getenv(ENV_PUSHER_APP_ID)
    key = os.getenv(ENV_PUSHER_KEY)
    secret = os.getenv(ENV_PUSHER_SECRET)
    cluster = os.getenv(ENV_PUSHER_CLUSTER)
    channel = os.getenv(ENV_PUSHER_CHANNEL, "airsense")
    event = os.getenv(ENV_PUSHER_EVENT, "new_data")

    missing = [name for name, value in {
        ENV_PUSHER_APP_ID: app_id,
        ENV_PUSHER_KEY: key,
        ENV_PUSHER_SECRET: secret,
        ENV_PUSHER_CLUSTER: cluster,
    }.items() if not value]

    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"Variabili Pusher mancanti: {missing_text}")

    client = pusher.Pusher(
        app_id,
        key,
        secret,
        cluster=cluster,
        ssl=True,
    )

    return client, channel, event


def read_serial(
    on_data: Callable[[Dict[str, Any]], None],
    port: Optional[str] = None,
    baud: int = DEFAULT_BAUD,
    warmup: int = DEFAULT_WARMUP,
    avg_window: int = DEFAULT_AVG_WINDOW,
) -> None:
    """Loop di lettura seriale con callback su dati validi."""

    gas_values: Deque[float] = deque(maxlen=avg_window)
    valid_count = 0
    resolved_port = _get_port(port)

    if not resolved_port:
        print("Porta seriale non configurata. Usa 'python serial_reader.py COM3'.")
        return

    while True:
        try:
            with serial.Serial(resolved_port, baudrate=baud, timeout=1) as ser:
                print(f"Connesso alla porta seriale {resolved_port} a {baud} baud.")
                while True:
                    try:
                        raw = ser.readline()
                    except serial.SerialException:
                        _log("[WARN]", "Errore di lettura dalla seriale. Riconnessione in corso...", COLOR_RED)
                        break

                    if not raw:
                        continue

                    try:
                        line = raw.decode("utf-8", errors="ignore").strip()
                    except UnicodeDecodeError:
                        continue

                    if not line:
                        continue

                    data = _safe_parse_json(line)
                    if data is None:
                        continue

                    _update_gas_avg(gas_values, data)

                    valid_count += 1
                    if valid_count <= warmup:
                        _log(
                            "[WARMUP]",
                            f"Campione {valid_count}/{warmup}: {data}",
                            COLOR_YELLOW,
                        )
                        continue

                    temp = _safe_float(data.get("temp"))
                    gas = _safe_float(data.get("gas_avg", data.get("gas")))
                    status = _compute_status(temp, gas)
                    data["stato"] = status

                    if status == "BUONO":
                        _log("[OK]", f"Dati inviati: {data}", COLOR_GREEN)
                    else:
                        _log("[WARN]", f"Qualita aria {status}: {data}", COLOR_RED)

                    on_data(data)
        except serial.SerialException:
            _log("[WARN]", "Porta seriale non disponibile. Riprovo tra 5 secondi...", COLOR_RED)
            time.sleep(5)
        except Exception as exc:
            _log("[WARN]", f"Errore inatteso nella seriale: {exc}. Riprovo tra 5 secondi...", COLOR_RED)
            time.sleep(5)


def main() -> None:
    parser = argparse.ArgumentParser(description="Lettore seriale AirSense")
    parser.add_argument("port", nargs="?", help="Porta seriale, es. COM3 o /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD, help="Baud rate (default 9600)")
    args = parser.parse_args()

    try:
        client, channel, event = _pusher_settings()
    except ValueError as exc:
        _log("[WARN]", str(exc), COLOR_RED)
        return

    def _send_to_pusher(data: Dict[str, Any]) -> None:
        try:
            client.trigger([channel], event, data)
        except Exception as exc:
            _log("[WARN]", f"Errore Pusher: {exc}", COLOR_RED)

    resolved_port = _get_port(args.port)
    if not resolved_port:
        _log("[WARN]", "Porta seriale non configurata: avvio simulazione.", COLOR_RED)
        simulate.run_simulation(on_data=_send_to_pusher)
        return

    try:
        with serial.Serial(resolved_port, baudrate=args.baud, timeout=1):
            pass
    except serial.SerialException:
        _log("[WARN]", f"Porta {resolved_port} non disponibile: avvio simulazione.", COLOR_RED)
        simulate.run_simulation(on_data=_send_to_pusher)
        return

    read_serial(on_data=_send_to_pusher, port=args.port, baud=args.baud)


if __name__ == "__main__":
    main()

