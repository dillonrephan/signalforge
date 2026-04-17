# Deploy

This repo does not currently model a database or full infrastructure stack.

What exists in reality today:

- a small Alpine box
- a Python virtual environment
- a Cloudflare tunnel started manually
- `main.py` started manually after the tunnel and venv are ready

This directory is for deployment notes and lightweight host runbooks only.

Included helpers:

- `start.sh`
  Starts the tunnel and Gunicorn for the copied Alpaca app on the Alpine host.
- `push-logs.sh`
  Bundles the local runtime logs and ships them to a remote host such as `leviathan`.
- `leviathan-sftp-match.conf`
  Example `sshd_config` match block for a dedicated SFTP-only reader account.
