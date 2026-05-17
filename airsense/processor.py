"""Processamento dati AirSense e persistenza su file."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

DATA_PATH = Path(__file__).resolve().parent.parent / "data.json"
MAX_RECORDS = 500

_LOCK = threading.Lock()


def _iso_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _compute_status(temp: float, gas: float) -> str:
    if temp > 35 or gas > 600:
        return "CRITICO"
    if temp >= 28 or gas >= 400:
        return "ATTENZIONE"
    if 15 <= temp < 28 and gas < 400:
        return "BUONO"
    return "ATTENZIONE"


def _load_records() -> List[Dict[str, Any]]:
    if not DATA_PATH.exists():
        return []
    try:
        raw = DATA_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        corrupt_path = DATA_PATH.with_suffix(".corrupt")
        try:
            DATA_PATH.replace(corrupt_path)
        except OSError:
            pass
    except OSError:
        pass
    return []


def _save_records(records: List[Dict[str, Any]]) -> None:
    try:
        DATA_PATH.write_text(json.dumps(records, ensure_ascii=True), encoding="utf-8")
    except OSError:
        print("Errore nel salvataggio di data.json")


def process(data: Dict[str, Any]) -> Dict[str, Any]:
    """Arricchisce i dati con stato e timestamp e salva su file."""
    temp = float(data.get("temp", 0))
    gas = float(data.get("gas", 0))

    enriched = dict(data)
    enriched["stato"] = _compute_status(temp, gas)
    enriched["timestamp"] = _iso_timestamp()

    with _LOCK:
        records = _load_records()
        records.append(enriched)
        if len(records) > MAX_RECORDS:
            records = records[-MAX_RECORDS:]
        _save_records(records)

    return enriched


def read_history(limit: int = 100) -> List[Dict[str, Any]]:
    """Legge gli ultimi record dal file."""
    with _LOCK:
        records = _load_records()
    if limit <= 0:
        return []
    return records[-limit:]

