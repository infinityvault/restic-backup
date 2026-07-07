from __future__ import annotations

from pathlib import Path

from restic_backup.adapters.config_yaml import YamlConfigAdapter
from restic_backup.domain.models import DatabaseType, NotificationMode


def test_loads_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("{}", encoding="utf-8")

    config = YamlConfigAdapter().load(config_path)

    assert config.data_dir == Path("/data")
    assert config.db_dump_file == Path("db_dump.sql")
    assert config.database is None
    assert config.notifications.mode == NotificationMode.ON_FAILURE


def test_loads_database_and_telegram(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
data_dir: /srv/data
db_dump_file: database/dump.sql
database:
  type: mysql
  host: mysql
  port: 3306
  username: app
  password: secret
  database: app
notifications:
  mode: always
  telegram:
    bot_token: token
    chat_id: 1234
""",
        encoding="utf-8",
    )

    config = YamlConfigAdapter().load(config_path)

    assert config.data_dir == Path("/srv/data")
    assert config.db_dump_path == Path("/srv/data/database/dump.sql")
    assert config.database
    assert config.database.type == DatabaseType.MYSQL
    assert config.notifications.mode == NotificationMode.ALWAYS
    assert config.notifications.telegram
    assert config.notifications.telegram.chat_id == "1234"


def test_loads_configuration_from_environment_without_yaml(tmp_path: Path) -> None:
    config = YamlConfigAdapter().load(
        tmp_path / "missing.yaml",
        env={
            "RESTIC_BACKUP_DATA_DIR": "/env/data",
            "RESTIC_BACKUP_DB_DUMP_FILE": "dumps/app.sql",
            "RESTIC_BACKUP_DATABASE_TYPE": "postgres",
            "RESTIC_BACKUP_DATABASE_HOST": "postgres",
            "RESTIC_BACKUP_DATABASE_PORT": "5432",
            "RESTIC_BACKUP_DATABASE_USERNAME": "app",
            "RESTIC_BACKUP_DATABASE_PASSWORD": "secret",
            "RESTIC_BACKUP_DATABASE_NAME": "app",
            "RESTIC_BACKUP_DATABASE_EXTRA_ARGS": "--schema public --clean",
            "RESTIC_BACKUP_NOTIFICATIONS_MODE": "always",
            "RESTIC_BACKUP_TELEGRAM_BOT_TOKEN": "token",
            "RESTIC_BACKUP_TELEGRAM_CHAT_ID": "1234",
        },
    )

    assert config.data_dir == Path("/env/data")
    assert config.db_dump_path == Path("/env/data/dumps/app.sql")
    assert config.database
    assert config.database.type == DatabaseType.POSTGRES
    assert config.database.host == "postgres"
    assert config.database.port == 5432
    assert config.database.username == "app"
    assert config.database.password == "secret"
    assert config.database.database == "app"
    assert config.database.extra_args == ("--schema", "public", "--clean")
    assert config.notifications.mode == NotificationMode.ALWAYS
    assert config.notifications.telegram
    assert config.notifications.telegram.bot_token == "token"
    assert config.notifications.telegram.chat_id == "1234"


def test_environment_overrides_yaml_values(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
data_dir: /yaml/data
db_dump_file: yaml.sql
database:
  type: mysql
  host: mysql
  port: 3306
  username: yaml
  password: yaml-secret
  database: yaml
notifications:
  mode: on_failure
  telegram:
    bot_token: yaml-token
    chat_id: yaml-chat
""",
        encoding="utf-8",
    )

    config = YamlConfigAdapter().load(
        config_path,
        env={
            "RESTIC_BACKUP_DATA_DIR": "/env/data",
            "RESTIC_BACKUP_DATABASE_TYPE": "postgres",
            "RESTIC_BACKUP_DATABASE_PORT": "5432",
            "RESTIC_BACKUP_TELEGRAM_CHAT_ID": "env-chat",
        },
    )

    assert config.data_dir == Path("/env/data")
    assert config.db_dump_file == Path("yaml.sql")
    assert config.database
    assert config.database.type == DatabaseType.POSTGRES
    assert config.database.host == "mysql"
    assert config.database.port == 5432
    assert config.database.username == "yaml"
    assert config.notifications.mode == NotificationMode.ON_FAILURE
    assert config.notifications.telegram
    assert config.notifications.telegram.bot_token == "yaml-token"
    assert config.notifications.telegram.chat_id == "env-chat"


def test_load_reads_process_environment_by_default(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("RESTIC_BACKUP_DATA_DIR", "/process/env/data")

    config = YamlConfigAdapter().load(tmp_path / "missing.yaml")

    assert config.data_dir == Path("/process/env/data")
