"""Simulatore dati AirSense per sviluppo senza Arduino."""

from __future__ import annotations

import random
import time
from typing import Any, Callable, Dict


def _random_temp() -> float:
    return round(random.uniform(18.0, 38.0), 1)


def _random_hum() -> float:
    return round(random.uniform(35.0, 70.0), 1)


def _random_gas() -> int:
    base = random.uniform(300.0, 700.0)
    return int(round(base))


def run_simulation(on_data: Callable[[Dict[str, Any]], None], interval: float = 2.0) -> None:
    """Genera dati realistici e li passa al callback."""
    ts = 0
    while True:
        ts += int(interval * 1000)
        data = {
            "temp": _random_temp(),
            "hum": _random_hum(),
            "gas": _random_gas(),
            "ts": ts,
        }
        on_data(data)
        time.sleep(interval)


def main() -> None:
    def _printer(data: Dict[str, Any]) -> None:
        print(data)

    run_simulation(on_data=_printer)


if __name__ == "__main__":
    main()

