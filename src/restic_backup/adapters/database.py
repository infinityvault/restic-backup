from __future__ import annotations

from pathlib import Path

from restic_backup.adapters.process import ProcessRunner
from restic_backup.domain.models import DatabaseConfig, DatabaseType


def create_database_adapter(config: DatabaseConfig, runner: ProcessRunner):
    if config.type == DatabaseType.POSTGRES:
        return PostgresCliAdapter(config, runner)
    if config.type == DatabaseType.MYSQL:
        return MysqlCliAdapter(config, runner)
    raise ValueError(f"Unsupported database type: {config.type}")


class PostgresCliAdapter:
    def __init__(self, config: DatabaseConfig, runner: ProcessRunner) -> None:
        self._config = config
        self._runner = runner

    def dump(self, destination: Path) -> None:
        args = ["pg_dump", *self._connection_args(), *self._config.extra_args, "--file", str(destination)]
        self._runner.run(args, env=self._env())

    def is_empty(self) -> bool:
        args = [
            "psql",
            *self._connection_args(),
            "--tuples-only",
            "--no-align",
            "--command",
            (
                "SELECT CASE WHEN EXISTS ("
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema NOT IN ('pg_catalog', 'information_schema')"
                ") THEN 'false' ELSE 'true' END;"
            ),
        ]
        return _query_bool(args, self._runner, self._env())

    def restore(self, source: Path) -> None:
        self._runner.run(["psql", *self._connection_args(), "--file", str(source)], env=self._env())

    def _connection_args(self) -> list[str]:
        args = []
        if self._config.host:
            args.extend(["--host", self._config.host])
        if self._config.port:
            args.extend(["--port", str(self._config.port)])
        if self._config.username:
            args.extend(["--username", self._config.username])
        if self._config.database:
            args.extend(["--dbname", self._config.database])
        return args

    def _env(self) -> dict[str, str]:
        return {"PGPASSWORD": self._config.password} if self._config.password else {}


class MysqlCliAdapter:
    def __init__(self, config: DatabaseConfig, runner: ProcessRunner) -> None:
        self._config = config
        self._runner = runner

    def dump(self, destination: Path) -> None:
        args = ["mysqldump", *self._connection_args(), *self._config.extra_args, self._required_database()]
        _run_to_file(args, destination, self._runner, self._env())

    def is_empty(self) -> bool:
        query = (
            "SELECT CASE WHEN COUNT(*) = 0 THEN 'true' ELSE 'false' END "
            "FROM information_schema.tables WHERE table_schema = DATABASE();"
        )
        args = ["mysql", *self._connection_args(), "--batch", "--skip-column-names", "--execute", query]
        return _query_bool(args, self._runner, self._env())

    def restore(self, source: Path) -> None:
        _run_from_file(["mysql", *self._connection_args(), self._required_database()], source, self._runner, self._env())

    def _connection_args(self) -> list[str]:
        args = []
        if self._config.host:
            args.extend(["--host", self._config.host])
        if self._config.port:
            args.extend(["--port", str(self._config.port)])
        if self._config.username:
            args.extend(["--user", self._config.username])
        return args

    def _required_database(self) -> str:
        if not self._config.database:
            raise ValueError("MySQL configuration requires database")
        return self._config.database

    def _env(self) -> dict[str, str]:
        return {"MYSQL_PWD": self._config.password} if self._config.password else {}


def _query_bool(args: list[str], runner: ProcessRunner, env: dict[str, str]) -> bool:
    return runner.run_capture(args, env=env).strip().lower() == "true"


def _run_to_file(args: list[str], destination: Path, runner: ProcessRunner, env: dict[str, str]) -> None:
    runner.run_to_file(args, destination, env=env)


def _run_from_file(args: list[str], source: Path, runner: ProcessRunner, env: dict[str, str]) -> None:
    runner.run_from_file(args, source, env=env)
