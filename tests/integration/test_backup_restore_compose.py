from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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

APP_SERVICE = "restic-backup"
COMPOSE_FILE = Path(__file__).with_name("docker-compose.yaml")
PROJECT_ROOT = COMPOSE_FILE.parents[2]
S3_REPOSITORY = "s3:http://minio:9000/restic-backup-it"


@dataclass(frozen=True)
class RepositoryCase:
    name: str
    repository: str
    needs_minio: bool = False


LOCAL_REPOSITORY = RepositoryCase("local", "/backup")
S3_REPOSITORY_CASE = RepositoryCase("s3", S3_REPOSITORY, needs_minio=True)
REPOSITORIES = [LOCAL_REPOSITORY, S3_REPOSITORY_CASE]


@pytest.fixture(autouse=True)
def log_test_separator(request: pytest.FixtureRequest):
    separator = "=" * 96
    print(f"\n{separator}", flush=True)
    print(f"[integration-test-start] {request.node.nodeid}", flush=True)
    print(separator, flush=True)
    try:
        yield
    finally:
        print(separator, flush=True)
        print(f"[integration-test-end] {request.node.nodeid}", flush=True)
        print(separator, flush=True)


@pytest.fixture()
def compose_env(tmp_path: Path) -> dict[str, str]:
    log_step("checking docker compose availability")
    docker_compose_version = subprocess.run(
        ["docker", "compose", "version"],
        check=False,
        text=True,
        capture_output=True,
    )
    if docker_compose_version.returncode != 0:
        pytest.skip(f"Docker Compose is not available: {docker_compose_version.stderr.strip()}")

    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    config_dir.chmod(0o755)
    log_step("created integration config directory", config_dir=config_dir)

    env = os.environ.copy()
    env.update(
        {
            "RESTIC_BACKUP_IT_CONFIG_DIR": str(config_dir),
            "RESTIC_REPOSITORY": "/backup",
        }
    )
    return env


@pytest.fixture()
def compose_project(compose_env: dict[str, str]):
    name = f"restic-backup-it-{uuid.uuid4().hex[:12]}"
    log_step("created compose project", project=name)
    try:
        yield name
    finally:
        log_step("tearing down compose project", project=name)
        compose(
            compose_project=name,
            env=compose_env,
            args=["down", "--volumes", "--remove-orphans"],
            check=False,
        )


@pytest.mark.parametrize("repository", REPOSITORIES, ids=lambda case: case.name)
def test_backup_data(compose_project: str, compose_env: dict[str, str], repository: RepositoryCase) -> None:
    log_step("starting data backup test", repository=repository.name)
    prepare_repository(compose_project, compose_env, repository)
    write_data_config(compose_env)
    write_data_file(compose_project, compose_env, "/data/hello.txt", f"{repository.name} data backup\n")
    debug_data_dir(compose_project, compose_env, "before data backup")

    log_step("running data backup", repository=repository.name)
    run_app(compose_project, compose_env, "--config", "/configs/data.yaml", "backup")
    debug_restic_snapshots(compose_project, compose_env, "after data backup")
    log_step("finished data backup", repository=repository.name)


@pytest.mark.parametrize("repository", REPOSITORIES, ids=lambda case: case.name)
def test_backup_data_and_database(
    compose_project: str,
    compose_env: dict[str, str],
    repository: RepositoryCase,
) -> None:
    log_step("starting data and database backup test", repository=repository.name)
    prepare_repository(compose_project, compose_env, repository)
    write_postgres_config(compose_env)
    write_data_file(compose_project, compose_env, "/data/payload.txt", f"{repository.name} database backup\n")
    debug_data_dir(compose_project, compose_env, "before database backup")

    log_step("starting postgres service")
    compose(compose_project, compose_env, ["up", "-d", "postgres"])
    wait_for_postgres(compose_project, compose_env)
    log_step("creating postgres test data")
    postgres_exec(compose_project, compose_env, "CREATE TABLE notes (body text); INSERT INTO notes VALUES ('backed up');")
    debug_postgres_query(compose_project, compose_env, "SELECT body FROM notes;", "after postgres fixture setup")

    log_step("running data and database backup", repository=repository.name)
    run_app(compose_project, compose_env, "--config", "/configs/postgres.yaml", "backup")
    debug_data_dir(compose_project, compose_env, "after database backup")
    debug_restic_snapshots(compose_project, compose_env, "after database backup")
    log_step("finished data and database backup", repository=repository.name)


@pytest.mark.parametrize("repository", REPOSITORIES, ids=lambda case: case.name)
def test_restore_latest_backup(compose_project: str, compose_env: dict[str, str], repository: RepositoryCase) -> None:
    log_step("starting latest restore test", repository=repository.name)
    prepare_repository(compose_project, compose_env, repository)
    write_data_config(compose_env)
    write_data_file(compose_project, compose_env, "/data/hello.txt", f"{repository.name} latest restore\n")
    debug_data_dir(compose_project, compose_env, "before latest restore source backup")
    log_step("creating source backup for latest restore", repository=repository.name)
    run_app(compose_project, compose_env, "--config", "/configs/data.yaml", "backup")
    debug_restic_snapshots(compose_project, compose_env, "after latest restore source backup")

    clear_data_dir(compose_project, compose_env)
    debug_data_dir(compose_project, compose_env, "after clearing data before latest restore")
    log_step("running latest restore", repository=repository.name)
    run_app(compose_project, compose_env, "--config", "/configs/data.yaml", "restore")
    debug_data_dir(compose_project, compose_env, "after latest restore")

    assert read_data_file(compose_project, compose_env, "/data/hello.txt") == f"{repository.name} latest restore\n"
    log_step("verified latest restore", repository=repository.name)


@pytest.mark.parametrize("repository", REPOSITORIES, ids=lambda case: case.name)
def test_restore_latest_backup_with_database(
    compose_project: str,
    compose_env: dict[str, str],
    repository: RepositoryCase,
) -> None:
    log_step("starting latest restore with database test", repository=repository.name)
    prepare_repository(compose_project, compose_env, repository)
    write_postgres_config(compose_env)
    write_data_file(compose_project, compose_env, "/data/payload.txt", f"{repository.name} database restore\n")
    debug_data_dir(compose_project, compose_env, "before database restore source backup")

    log_step("starting postgres service")
    compose(compose_project, compose_env, ["up", "-d", "postgres"])
    wait_for_postgres(compose_project, compose_env)
    log_step("creating postgres restore fixture")
    postgres_exec(compose_project, compose_env, "CREATE TABLE notes (body text); INSERT INTO notes VALUES ('pg restored');")
    debug_postgres_query(compose_project, compose_env, "SELECT body FROM notes;", "after postgres restore fixture setup")
    log_step("creating source backup for database restore", repository=repository.name)
    run_app(compose_project, compose_env, "--config", "/configs/postgres.yaml", "backup")
    debug_data_dir(compose_project, compose_env, "after database restore source backup")
    debug_restic_snapshots(compose_project, compose_env, "after database restore source backup")

    clear_data_dir(compose_project, compose_env)
    debug_data_dir(compose_project, compose_env, "after clearing data before database restore")
    log_step("dropping postgres test table before restore")
    postgres_exec(compose_project, compose_env, "DROP TABLE notes;")
    debug_postgres_query(compose_project, compose_env, "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'notes';", "after dropping notes table")
    log_step("running latest restore with database", repository=repository.name)
    run_app(compose_project, compose_env, "--config", "/configs/postgres.yaml", "restore")
    debug_data_dir(compose_project, compose_env, "after database restore")
    debug_postgres_query(compose_project, compose_env, "SELECT body FROM notes;", "after database restore")

    assert read_data_file(compose_project, compose_env, "/data/payload.txt") == f"{repository.name} database restore\n"
    assert postgres_query(compose_project, compose_env, "SELECT body FROM notes;") == "pg restored"
    log_step("verified latest restore with database", repository=repository.name)


@pytest.mark.parametrize("repository", REPOSITORIES, ids=lambda case: case.name)
def test_restore_backup_one_day_ago_fails(
    compose_project: str,
    compose_env: dict[str, str],
    repository: RepositoryCase,
) -> None:
    log_step("starting restore one day ago failure test", repository=repository.name)
    prepare_repository(compose_project, compose_env, repository)
    write_data_config(compose_env)
    write_data_file(compose_project, compose_env, "/data/hello.txt", f"{repository.name} no old backup\n")
    debug_data_dir(compose_project, compose_env, "before one-day-ago source backup")
    log_step("creating current backup before one-day-ago restore", repository=repository.name)
    run_app(compose_project, compose_env, "--config", "/configs/data.yaml", "backup")
    debug_restic_snapshots(compose_project, compose_env, "after one-day-ago source backup")

    clear_data_dir(compose_project, compose_env)
    debug_data_dir(compose_project, compose_env, "after clearing data before one-day-ago restore")
    one_day_ago = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    log_step("running expected-failure restore", repository=repository.name, before=one_day_ago)
    completed = run_app(
        compose_project,
        compose_env,
        "--config",
        "/configs/data.yaml",
        "restore",
        "--before",
        one_day_ago,
        check=False,
    )

    assert completed.returncode != 0
    debug_command_output("expected-failure restore command", completed)
    log_step("verified one-day-ago restore failed", repository=repository.name, returncode=completed.returncode)


@pytest.mark.parametrize("repository", REPOSITORIES, ids=lambda case: case.name)
def test_cleanup(
    compose_project: str,
    compose_env: dict[str, str],
    repository: RepositoryCase,
) -> None:
    log_step("starting cleanup test", repository=repository.name)
    prepare_repository(compose_project, compose_env, repository)
    write_data_config(compose_env)
    write_data_file(compose_project, compose_env, "/data/cleanup.txt", f"{repository.name} cleanup\n")
    debug_data_dir(compose_project, compose_env, "before cleanup source backup")
    log_step("creating source backup before cleanup", repository=repository.name)
    run_app(compose_project, compose_env, "--config", "/configs/data.yaml", "backup")
    debug_restic_snapshots(compose_project, compose_env, "before cleanup")

    log_step("running cleanup", repository=repository.name)
    run_app(
        compose_project,
        compose_env,
        "--config",
        "/configs/data.yaml",
        "cleanup",
        "--keep-daily",
        "1",
        "--keep-weekly",
        "1",
        "--keep-monthly",
        "1",
        "--keep-yearly",
        "1",
    )
    debug_restic_snapshots(compose_project, compose_env, "after cleanup")
    log_step("finished cleanup", repository=repository.name)


def prepare_repository(compose_project: str, env: dict[str, str], repository: RepositoryCase) -> None:
    env["RESTIC_REPOSITORY"] = repository.repository
    log_step("preparing repository", repository=repository.name, restic_repository=repository.repository)
    if repository.needs_minio:
        log_step("starting minio", repository=repository.name)
        compose(compose_project, env, ["up", "-d", "minio"])
        log_step("creating minio bucket", repository=repository.name)
        compose(compose_project, env, ["run", "--rm", "minio-init"])
    restic_init(compose_project, env)
    log_step("initialized restic repository", repository=repository.name)


def write_data_config(env: dict[str, str]) -> None:
    config_dir = Path(env["RESTIC_BACKUP_IT_CONFIG_DIR"])
    log_step("writing data config", path=config_dir / "data.yaml")
    write_test_file(config_dir / "data.yaml", "data_dir: /data\n")


def write_postgres_config(env: dict[str, str]) -> None:
    config_dir = Path(env["RESTIC_BACKUP_IT_CONFIG_DIR"])
    log_step("writing postgres config", path=config_dir / "postgres.yaml")
    write_test_file(
        config_dir / "postgres.yaml",
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
    )


def write_test_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o755)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o644)


def write_data_file(compose_project: str, env: dict[str, str], path: str, content: str) -> None:
    log_step("writing data file in container volume", path=path, bytes=len(content.encode("utf-8")))
    escaped_content = shell_single_quote(content)
    escaped_path = shell_single_quote(path)
    compose(
        compose_project,
        env,
        [
            "run",
            "--rm",
            "--entrypoint",
            "sh",
            APP_SERVICE,
            "-c",
            f"mkdir -p $(dirname {escaped_path}) && printf %s {escaped_content} > {escaped_path}",
        ],
    )


def read_data_file(compose_project: str, env: dict[str, str], path: str) -> str:
    log_step("reading data file from container volume", path=path)
    completed = compose(
        compose_project,
        env,
        ["run", "--rm", "--entrypoint", "cat", APP_SERVICE, path],
    )
    log_step("read data file from container volume", path=path, bytes=len(completed.stdout.encode("utf-8")))
    return completed.stdout


def clear_data_dir(compose_project: str, env: dict[str, str]) -> None:
    log_step("clearing data directory in container volume")
    compose(
        compose_project,
        env,
        ["run", "--rm", "--entrypoint", "sh", APP_SERVICE, "-c", "find /data -mindepth 1 -maxdepth 1 -exec rm -rf {} +"],
    )


def debug_data_dir(compose_project: str, env: dict[str, str], label: str) -> None:
    completed = compose(
        compose_project,
        env,
        ["run", "--rm", "--entrypoint", "sh", APP_SERVICE, "-c", "pwd; ls -lah /data; find /data -maxdepth 3 -type f -print"],
        check=False,
    )
    debug_command_output(f"data directory {label}", completed)


def debug_restic_snapshots(compose_project: str, env: dict[str, str], label: str) -> None:
    completed = compose(
        compose_project,
        env,
        ["run", "--rm", "--entrypoint", "restic", APP_SERVICE, "snapshots"],
        check=False,
    )
    debug_command_output(f"restic snapshots {label}", completed)


def debug_postgres_query(compose_project: str, env: dict[str, str], sql: str, label: str) -> None:
    completed = compose(
        compose_project,
        env,
        ["exec", "-T", "postgres", "psql", "-U", "app", "-d", "app", "-tA", "-c", sql],
        check=False,
    )
    debug_command_output(f"postgres query {label}", completed)


def debug_command_output(label: str, completed: subprocess.CompletedProcess[str]) -> None:
    print(f"[integration-debug] {label} returncode={completed.returncode}", flush=True)
    if completed.stdout.strip():
        print(f"[integration-debug] {label} stdout:\n{completed.stdout.rstrip()}", flush=True)
    if completed.stderr.strip():
        print(f"[integration-debug] {label} stderr:\n{completed.stderr.rstrip()}", flush=True)


def shell_single_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def compose(
    compose_project: str,
    env: dict[str, str],
    args: list[str],
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    command = ["docker", "compose", "-f", str(COMPOSE_FILE), "-p", compose_project, *args]
    log_step("running compose command", command=shlex.join(command))
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )
    log_step(
        "finished compose command",
        returncode=completed.returncode,
        stdout_bytes=len(completed.stdout.encode("utf-8")),
        stderr_bytes=len(completed.stderr.encode("utf-8")),
    )
    if check and completed.returncode != 0:
        command_text = shlex.join(command)
        pytest.fail(
            "\n".join(
                [
                    f"Command failed with exit code {completed.returncode}: {command_text}",
                    f"stdout:\n{completed.stdout.strip()}",
                    f"stderr:\n{completed.stderr.strip()}",
                ]
            )
        )
    return completed


def restic_init(compose_project: str, env: dict[str, str]) -> None:
    log_step("running restic init", restic_repository=env["RESTIC_REPOSITORY"])
    compose(compose_project, env, ["run", "--rm", "--entrypoint", "restic", APP_SERVICE, "init"])


def run_app(
    compose_project: str,
    env: dict[str, str],
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    log_step("running app command", args=shlex.join([*args]), check=check)
    return compose(compose_project, env, ["run", "--rm", APP_SERVICE, *args], check=check)


def wait_for_postgres(compose_project: str, env: dict[str, str]) -> None:
    log_step("waiting for postgres")
    compose(
        compose_project,
        env,
        [
            "run",
            "--rm",
            "--entrypoint",
            "sh",
            APP_SERVICE,
            "-c",
            "until PGPASSWORD=secret pg_isready -h postgres -U app -d app; do sleep 1; done",
        ],
    )
    log_step("postgres is ready")


def postgres_exec(compose_project: str, env: dict[str, str], sql: str) -> None:
    log_step("executing postgres sql", sql=sql)
    compose(compose_project, env, ["exec", "-T", "postgres", "psql", "-U", "app", "-d", "app", "-c", sql])


def postgres_query(compose_project: str, env: dict[str, str], sql: str) -> str:
    log_step("querying postgres", sql=sql)
    completed = compose(
        compose_project,
        env,
        ["exec", "-T", "postgres", "psql", "-U", "app", "-d", "app", "-tA", "-c", sql],
    )
    log_step("queried postgres", rows=completed.stdout.strip())
    return completed.stdout.strip()


def log_step(message: str, **details: object) -> None:
    if details:
        detail_text = " ".join(f"{key}={value!r}" for key, value in sorted(details.items()))
        print(f"[integration] {message} {detail_text}", flush=True)
    else:
        print(f"[integration] {message}", flush=True)
