# restic-backup

Python CLI for restic backups, restores, and cleanup, structured with ports and adapters.

## Install

```bash
uv sync --extra dev
```

## Usage

```bash
restic-backup backup --config config.yaml
restic-backup restore --before "2026-06-01T00:00:00Z" --config config.yaml
restic-backup cleanup --keep-daily 7 --keep-weekly 4 --config config.yaml
```

Restic repository configuration is expected to be provided via environment variables, for example `RESTIC_REPOSITORY` and `RESTIC_PASSWORD`.

## Tests

```bash
uv run --extra dev pytest
```

Docker Compose integration tests are opt-in because they build the app image and start Postgres/MySQL containers:

```bash
RESTIC_BACKUP_RUN_INTEGRATION=1 uv run --extra dev pytest tests/integration
```

## Configuration

See [config.example.yaml](config.example.yaml).

Configuration can also be provided with environment variables. Environment values override YAML values, and the
config file may be omitted when everything is supplied through the environment.

Supported variables:

- `RESTIC_BACKUP_DATA_DIR`
- `RESTIC_BACKUP_DB_DUMP_FILE`
- `RESTIC_BACKUP_DATABASE_TYPE`
- `RESTIC_BACKUP_DATABASE_HOST`
- `RESTIC_BACKUP_DATABASE_PORT`
- `RESTIC_BACKUP_DATABASE_USERNAME`
- `RESTIC_BACKUP_DATABASE_PASSWORD`
- `RESTIC_BACKUP_DATABASE_NAME`
- `RESTIC_BACKUP_DATABASE_EXTRA_ARGS`
- `RESTIC_BACKUP_NOTIFICATIONS_MODE`
- `RESTIC_BACKUP_TELEGRAM_BOT_TOKEN`
- `RESTIC_BACKUP_TELEGRAM_CHAT_ID`
