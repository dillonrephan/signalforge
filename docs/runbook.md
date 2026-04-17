# Runbook

## Local Startup

1. Create a Python environment for this repo.
2. Install `requirements.txt`.
3. Create `app/service/.env` from `app/service/.env.example`.
4. Start the app from `app/service` with `python main.py`.
5. Verify `GET /health`.
6. Only after local verification, expose the service through the remote-box tunnel or deployment path you actually use.

## Deployment Boundary

This repo is source-first.

- application code lives in `app/service`
- host-specific secrets, certificates, and tunnel config stay off-repo
- the live runtime today is a small Alpine box with a virtualenv and a Cloudflare tunnel

## Known Constraints

- Alpaca scripts are mode-aware through `ALPACA_MODE`.
- Kraken scripts now follow the JSON/CLI contract expected by the router, but they still assume supported Kraken pairs only.
- The remote historical trees include `development`, `deployment`, and `stable`, but the actually used architecture is the simple Flask-plus-logfile branch rather than the older database-heavy branch.
- Current remote startup order is: Cloudflare tunnel, virtualenv activation, then `main.py`.
