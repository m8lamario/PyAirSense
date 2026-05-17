"""Simulatore dati AirSense con invio su Pusher."""

from __future__ import annotations

import random
import time
from collections import deque
from typing import Any, Callable, Deque, Dict, Tuple
import os

import collections
from collections.abc import Sized as _Sized

if not hasattr(collections, "Sized"):
    collections.Sized = _Sized

import pusher
from dotenv import load_dotenv

DEFAULT_WARMUP = 10
DEFAULT_AVG_WINDOW = 5

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


def _compute_status(temp: float, gas: float) -> str:
    if temp > 35 or gas > 600:
        return "CRITICO"
    if temp >= 28 or gas >= 400:
        return "ATTENZIONE"
    if 15 <= temp < 28 and gas < 400:
        return "BUONO"
    return "ATTENZIONE"


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


def _random_temp(step: int) -> float:
    base = min(38.0, 20.0 + step * 0.08)
    return round(random.uniform(base - 1.0, base + 1.0), 1)


def _random_hum(step: int) -> float:
    base = max(30.0, 60.0 - step * 0.05)
    return round(random.uniform(base - 3.0, base + 3.0), 1)


def _random_gas(step: int) -> int:
    base = min(700.0, 300.0 + step * 6.0)
    return int(round(random.uniform(base - 15.0, base + 15.0)))


def run_simulation(
    on_data: Callable[[Dict[str, Any]], None],
    interval: float = 2.0,
    warmup: int = DEFAULT_WARMUP,
    avg_window: int = DEFAULT_AVG_WINDOW,
) -> None:
    """Genera dati realistici con peggioramento graduale e li passa al callback."""
    ts = 0
    step = 0
    gas_values: Deque[float] = deque(maxlen=avg_window)
    valid_count = 0

    while True:
        step += 1
        ts += int(interval * 1000)
        data = {
            "temp": _random_temp(step),
            "hum": _random_hum(step),
            "gas": _random_gas(step),
            "ts": ts,
        }

        _update_gas_avg(gas_values, data)
        valid_count += 1

        if valid_count <= warmup:
            _log("[WARMUP]", f"Campione {valid_count}/{warmup}: {data}", COLOR_YELLOW)
            time.sleep(interval)
            continue

        temp = float(data.get("temp", 0))
        gas = float(data.get("gas_avg", data.get("gas", 0)))
        status = _compute_status(temp, gas)
        data["stato"] = status

        if status == "BUONO":
            _log("[OK]", f"Dati inviati: {data}", COLOR_GREEN)
        else:
            _log("[WARN]", f"Qualita aria {status}: {data}", COLOR_RED)

        on_data(data)
        time.sleep(interval)


def main() -> None:
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

    run_simulation(on_data=_send_to_pusher)


if __name__ == "__main__":
    main()
