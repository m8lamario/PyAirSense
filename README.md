# AirSense

Software layer per un sistema di monitoraggio ambientale con Arduino.

## Requisiti
- Python 3.10+
- Dipendenze in `airsense/requirements.txt`

## Avvio rapido
1. Crea un venv e installa le dipendenze:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   python -m pip install -r airsense/requirements.txt
   ```
2. Imposta la porta seriale (se usi Arduino reale):
   ```bash
   set AIRSENSE_PORT=COM3
   ```
3. Avvia il server:
   ```bash
   python main.py
   ```

## Simulatore
Per usare il simulatore interno:
```bash
set AIRSENSE_SIMULATE=1
python main.py
```

## API
- `GET /api/history` restituisce gli ultimi 100 record.
- WebSocket emette `new_data` ad ogni lettura.

