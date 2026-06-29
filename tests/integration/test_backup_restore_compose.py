from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RESTIC_BACKUP_RUN_INTEGRATION") != "1",
        reason="set RESTIC_BACKUP_RUN_INTEGRATION=1 to run Docker Compose integration tests",
    ),
    pytest.mark.skipif(shutil.which("docker") is None, reason="Docker is not installed"),
]

COMPOSE_FILE = Path(__file__).with_name("docker-compose.yaml")
PROJECT_ROOT = COMPOSE_FILE.parents[2]


@pytest.fixture()
def compose_env(tmp_path: Path) -> dict[str, str]:
    docker_compose_version = subprocess.run(
        ["docker", "compose", "version"],
        check=False,
        text=True,
        capture_output=True,
    )
    if docker_compose_version.returncode != 0:
        pytest.skip(f"Docker Compose is not available: {docker_compose_version.stderr.strip()}")

    config_dir = tmp_path / "configs"
    data_dir = tmp_path / "data"
    repo_dir = tmp_path / "repo"
    config_dir.mkdir()
    data_dir.mkdir()
    repo_dir.mkdir()

    env = os.environ.copy()
    env.update(
        {
            "RESTIC_BACKUP_IT_CONFIG_DIR": str(config_dir),
            "RESTIC_BACKUP_IT_DATA_DIR": str(data_dir),
            "RESTIC_BACKUP_IT_REPO_DIR": str(repo_dir),
        }
    )
    return env


@pytest.fixture()
def compose_project(compose_env: dict[str, str]):
    name = f"restic-backup-it-{uuid.uuid4().hex[:12]}"
    try:
        yield name
    finally:
        compose(
            compose_project=name,
            env=compose_env,
            args=["down", "--volumes", "--remove-orphans"],
            check=False,
        )


def test_data_backup_and_restore(compose_project: str, compose_env: dict[str, str]) -> None:
    config_dir = Path(compose_env["RESTIC_BACKUP_IT_CONFIG_DIR"])
    data_dir = Path(compose_env["RESTIC_BACKUP_IT_DATA_DIR"])
    (config_dir / "data.yaml").write_text("data_dir: /data\n", encoding="utf-8")
    (data_dir / "hello.txt").write_text("before backup\n", encoding="utf-8")

    restic_init(compose_project, compose_env)
    run_app(compose_project, compose_env, "backup", "--config", "/configs/data.yaml")
    clear_dir(data_dir)
    run_app(compose_project, compose_env, "restore", "--config", "/configs/data.yaml")

    assert (data_dir / "hello.txt").read_text(encoding="utf-8") == "before backup\n"


def test_postgres_backup_and_restore(compose_project: str, compose_env: dict[str, str]) -> None:
    config_dir = Path(compose_env["RESTIC_BACKUP_IT_CONFIG_DIR"])
    data_dir = Path(compose_env["RESTIC_BACKUP_IT_DATA_DIR"])
    (config_dir / "postgres.yaml").write_text(
        """
data_dir: /data
db_dump_file: database/dump.sql
database:
  type: postgres
  host: postgres
  port: 5432
  username: app
  password: secret
  database: app
""",
        encoding="utf-8",
    )
    (data_dir / "payload.txt").write_text("postgres payload\n", encoding="utf-8")

    compose(compose_project, compose_env, ["up", "-d", "postgres"])
    wait_for_postgres(compose_project, compose_env)
    postgres_exec(compose_project, compose_env, "CREATE TABLE notes (body text); INSERT INTO notes VALUES ('pg restored');")

    restic_init(compose_project, compose_env)
    run_app(compose_project, compose_env, "backup", "--config", "/configs/postgres.yaml")
    clear_dir(data_dir)
    postgres_exec(compose_project, compose_env, "DROP TABLE notes;")

    run_app(compose_project, compose_env, "restore", "--config", "/configs/postgres.yaml")

    assert (data_dir / "payload.txt").read_text(encoding="utf-8") == "postgres payload\n"
    assert postgres_query(compose_project, compose_env, "SELECT body FROM notes;") == "pg restored"


def test_mysql_backup_and_restore(compose_project: str, compose_env: dict[str, str]) -> None:
    config_dir = Path(compose_env["RESTIC_BACKUP_IT_CONFIG_DIR"])
    data_dir = Path(compose_env["RESTIC_BACKUP_IT_DATA_DIR"])
    (config_dir / "mysql.yaml").write_text(
        """
data_dir: /data
db_dump_file: database/dump.sql
database:
  type: mysql
  host: mysql
  port: 3306
  username: app
  password: secret
  database: app
""",
        encoding="utf-8",
    )
    (data_dir / "payload.txt").write_text("mysql payload\n", encoding="utf-8")

    compose(compose_project, compose_env, ["up", "-d", "mysql"])
    wait_for_mysql(compose_project, compose_env)
    mysql_exec(compose_project, compose_env, "CREATE TABLE notes (body varchar(255)); INSERT INTO notes VALUES ('mysql restored');")

    restic_init(compose_project, compose_env)
    run_app(compose_project, compose_env, "backup", "--config", "/configs/mysql.yaml")
    clear_dir(data_dir)
    mysql_exec(compose_project, compose_env, "DROP TABLE notes;")

    run_app(compose_project, compose_env, "restore", "--config", "/configs/mysql.yaml")

    assert (data_dir / "payload.txt").read_text(encoding="utf-8") == "mysql payload\n"
    assert mysql_query(compose_project, compose_env, "SELECT body FROM notes;") == "mysql restored"


def compose(
    compose_project: str,
    env: dict[str, str],
    args: list[str],
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "-p", compose_project, *args],
        cwd=PROJECT_ROOT,
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )
    if check and completed.returncode != 0:
        command = " ".join(["docker", "compose", "-f", str(COMPOSE_FILE), "-p", compose_project, *args])
        pytest.fail(
            "\n".join(
                [
                    f"Command failed with exit code {completed.returncode}: {command}",
                    f"stdout:\n{completed.stdout.strip()}",
                    f"stderr:\n{completed.stderr.strip()}",
                ]
            )
        )
    return completed


def restic_init(compose_project: str, env: dict[str, str]) -> None:
    compose(compose_project, env, ["run", "--rm", "--entrypoint", "restic", "app", "init"])


def run_app(compose_project: str, env: dict[str, str], *args: str) -> None:
    compose(compose_project, env, ["run", "--rm", "app", *args])


def wait_for_postgres(compose_project: str, env: dict[str, str]) -> None:
    compose(
        compose_project,
        env,
        [
            "run",
            "--rm",
            "--entrypoint",
            "sh",
            "app",
            "-c",
            "until PGPASSWORD=secret pg_isready -h postgres -U app -d app; do sleep 1; done",
        ],
    )


def wait_for_mysql(compose_project: str, env: dict[str, str]) -> None:
    compose(
        compose_project,
        env,
        [
            "run",
            "--rm",
            "--entrypoint",
            "sh",
            "app",
            "-c",
            "until MYSQL_PWD=secret mysqladmin ping -h mysql -u app --silent; do sleep 1; done",
        ],
    )


def postgres_exec(compose_project: str, env: dict[str, str], sql: str) -> None:
    compose(compose_project, env, ["exec", "-T", "postgres", "psql", "-U", "app", "-d", "app", "-c", sql])


def postgres_query(compose_project: str, env: dict[str, str], sql: str) -> str:
    completed = compose(
        compose_project,
        env,
        ["exec", "-T", "postgres", "psql", "-U", "app", "-d", "app", "-tA", "-c", sql],
    )
    return completed.stdout.strip()


def mysql_exec(compose_project: str, env: dict[str, str], sql: str) -> None:
    compose(
        compose_project,
        env,
        ["exec", "-T", "mysql", "mysql", "-uapp", "-psecret", "app", "--execute", sql],
    )


def mysql_query(compose_project: str, env: dict[str, str], sql: str) -> str:
    completed = compose(
        compose_project,
        env,
        ["exec", "-T", "mysql", "mysql", "-uapp", "-psecret", "app", "--batch", "--skip-column-names", "--execute", sql],
    )
    return completed.stdout.strip()


def clear_dir(path: Path) -> None:
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
