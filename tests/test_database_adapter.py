from __future__ import annotations

from restic_backup.adapters.database import MysqlCliAdapter, PostgresCliAdapter
from restic_backup.domain.models import DatabaseConfig, DatabaseType


class CaptureRunnerSpy:
    def __init__(self, output: str) -> None:
        self.calls: list[list[str]] = []
        self._output = output

    def run_capture(self, args: list[str], env: dict[str, str] | None = None) -> str:
        self.calls.append(args)
        return self._output


def _mysql(output: str) -> tuple[MysqlCliAdapter, CaptureRunnerSpy]:
    runner = CaptureRunnerSpy(output)
    config = DatabaseConfig(type=DatabaseType.MYSQL, host="mysql", port=3306, username="kimai", database="kimai")
    return MysqlCliAdapter(config, runner), runner


def test_mysql_is_empty_queries_the_configured_database() -> None:
    adapter, runner = _mysql("true\n")

    assert adapter.is_empty() is True
    # Without the database argument, DATABASE() is NULL and every database looks empty.
    assert runner.calls[0][-1] == "kimai"


def test_mysql_is_not_empty_when_tables_exist() -> None:
    adapter, _ = _mysql("false\n")

    assert adapter.is_empty() is False


def test_postgres_is_empty_queries_the_configured_database() -> None:
    runner = CaptureRunnerSpy("false\n")
    config = DatabaseConfig(type=DatabaseType.POSTGRES, host="postgres", username="app", database="app")

    assert PostgresCliAdapter(config, runner).is_empty() is False
    assert runner.calls[0][runner.calls[0].index("--dbname") + 1] == "app"
