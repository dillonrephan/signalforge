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

## Log Offload

Recommended shape:

- `dispatcher` writes local runtime logs only.
- `dispatcher` pushes timestamped log bundles to `leviathan`.
- `leviathan` exposes only the shared log folder to the data guy.

Avoid exposing SMB or the full workstation directly to the internet. The narrow option is a dedicated SFTP-only account on `leviathan`.

Suggested directories on `leviathan`:

- `/srv/marketdrop`
  Root-owned chroot base.
- `/srv/marketdrop/shared`
  Readable area for the external data user.
- `/srv/marketdrop/incoming/dispatcher`
  Write target for log uploads from `dispatcher`.

Suggested users on `leviathan`:

- `logdrop`
  SSH key from `dispatcher`, write access only to `/srv/marketdrop/incoming/dispatcher`.
- `marketreader`
  SSH key from the data guy, SFTP-only access to `/srv/marketdrop/shared`.

`deploy/leviathan-sftp-match.conf` contains the `sshd_config` match block for the `marketreader` account. The chroot base must be owned by `root:root` and not be group-writable.

`deploy/push-logs.sh` is meant to run on `dispatcher`. It packages:

- `app/logs/broker.log*`
- `runtime/alpaca-gunicorn.log*`
- `runtime/cloudflared.log*`

Example cron entry on `dispatcher`:

```cron
*/15 * * * * /root/projects/codex/push-logs.sh >> /root/projects/codex/runtime/logpush.log 2>&1
```

Example environment for `push-logs.sh`:

```sh
REMOTE_HOST=leviathan
REMOTE_USER=logdrop
REMOTE_BASE_DIR=/srv/marketdrop/incoming/dispatcher
SSH_KEY=/root/.ssh/id_ed25519
```

If the data guy should see unpacked files instead of archives, unpack the uploaded tarballs into `/srv/marketdrop/shared/dispatcher` on `leviathan` with a local timer or cron job there.
