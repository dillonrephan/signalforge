# signalforge

`signalforge` is a clean-source repo for a broker webhook service.

It is intentionally narrow:

- `app/service`
  Flask webhook router and broker-specific execution scripts.
- `deploy`
  Deployment notes and host-specific run steps for the remote Alpine box.
- `docs`
  Runbooks and repo notes.

This repo is meant to be source, not a mirror of a live host. Local secrets, logs, keys, and runtime state are excluded on purpose.

## Service Shape

Primary entry point:

- [`app/service/main.py`](/home/ice/codex/signalforge/app/service/main.py:1)

Routes:

- `GET /health`
- `GET /config`
- `POST /webhook`

Broker scripts:

- [`app/service/alpaca`](/home/ice/codex/signalforge/app/service/alpaca:1)
- [`app/service/kraken`](/home/ice/codex/signalforge/app/service/kraken:1)

## Environment

The service expects a local `.env` file at:

- `app/service/.env`

Start from:

- [app/service/.env.example](/home/ice/codex/signalforge/app/service/.env.example:1)

Important variables:

- `BROKER_PROFILE`
- `ALLOW_LIVE`
- `PRICE_TOLERANCE`
- `PORT`
- `LOG_LEVEL`
- `ALPACA_PAPER_KEY_ID`
- `ALPACA_PAPER_SECRET_KEY`
- `ALPACA_LIVE_KEY_ID`
- `ALPACA_LIVE_SECRET_KEY`
- `KRAKEN_API_KEY`
- `KRAKEN_API_SECRET`

## Install

1. Create and activate a Python environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create `app/service/.env` from `.env.example`.
4. Run the service:

```bash
cd app/service
python main.py
```

## Remote Startup

Current real-world startup flow on the Alpine box is:

1. start the Cloudflare tunnel
2. activate the Python virtual environment
3. run `main.py`

This repo should reflect that flow rather than inventing infrastructure that does not exist.

## Notes

- Alpaca is the strategic direction for the project.
- Kraken is the working legacy path and still needs development.
- The current default profile is `alpaca_paper`.
- `alpaca_live` is gated behind `ALLOW_LIVE=true`.
- This repo does not include local secrets, runtime logs, or database state.
- The intended log-export pattern is `dispatcher -> leviathan -> shared SFTP folder`, not direct public exposure of the runtime box.
