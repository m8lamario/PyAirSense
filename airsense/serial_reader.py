"""Lettura seriale per AirSense."""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import deque
from typing import Any, Callable, Deque, Dict, Optional

import serial

DEFAULT_BAUD = 9600
DEFAULT_WARMUP = 10
DEFAULT_AVG_WINDOW = 5
ENV_PORT = "AIRSENSE_PORT"


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
        print("Porta seriale non configurata. Usa --port o AIRSENSE_PORT.")
        return

    while True:
        try:
            with serial.Serial(resolved_port, baudrate=baud, timeout=1) as ser:
                print(f"Connesso alla porta seriale {resolved_port} a {baud} baud.")
                while True:
                    try:
                        raw = ser.readline()
                    except serial.SerialException:
                        print("Errore di lettura dalla seriale. Riconnessione in corso...")
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
                        continue

                    on_data(data)
        except serial.SerialException:
            print("Porta seriale non disponibile. Riprovo tra 5 secondi...")
            time.sleep(5)
        except Exception as exc:
            print(f"Errore inatteso nella seriale: {exc}. Riprovo tra 5 secondi...")
            time.sleep(5)


def main() -> None:
    parser = argparse.ArgumentParser(description="Lettore seriale AirSense")
    parser.add_argument("--port", help="Porta seriale, es. COM3 o /dev/ttyUSB0")
    args = parser.parse_args()

    def _printer(data: Dict[str, Any]) -> None:
        print(data)

    read_serial(on_data=_printer, port=args.port)


if __name__ == "__main__":
    main()

