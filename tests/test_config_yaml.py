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
