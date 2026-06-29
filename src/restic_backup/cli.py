from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

import click

from restic_backup.adapters.config_yaml import YamlConfigAdapter
from restic_backup.application.use_cases import BackupUseCase, CleanupUseCase, RestoreUseCase
from restic_backup.container import Container
from restic_backup.domain.models import NotificationMode
from restic_backup.logging_config import configure_logging

logger = logging.getLogger(__name__)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--config", "config_path", type=click.Path(path_type=Path), default=Path("config.yaml"), show_default=True)
@click.option("--verbose", is_flag=True, help="Enable debug logging.")
@click.pass_context
def cli(ctx: click.Context, config_path: Path, verbose: bool) -> None:
    configure_logging(verbose)
    config = YamlConfigAdapter().load(config_path)
    ctx.obj = Container(config)


@cli.command()
@click.pass_obj
def backup(container: Container) -> None:
    _run_with_notifications(
        container,
        "Backup",
        lambda: BackupUseCase(container.restic, container.database).execute(
            container.config.data_dir,
            container.config.db_dump_path,
        ),
    )


@cli.command()
@click.option("--before", type=str, default=None, help='Restore latest snapshot before "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM:SSZ".')
@click.pass_obj
def restore(container: Container, before: str | None) -> None:
    _run_with_notifications(
        container,
        "Restore",
        lambda: RestoreUseCase(container.restic, container.filesystem, container.database).execute(
            container.config.data_dir,
            container.config.db_dump_path,
            before=before,
        ),
    )


@cli.command()
@click.option("--keep-daily", type=int)
@click.option("--keep-weekly", type=int)
@click.option("--keep-monthly", type=int)
@click.option("--keep-yearly", type=int)
@click.pass_obj
def cleanup(
    container: Container,
    keep_daily: int | None,
    keep_weekly: int | None,
    keep_monthly: int | None,
    keep_yearly: int | None,
) -> None:
    retention_args = _retention_args(
        keep_daily=keep_daily,
        keep_weekly=keep_weekly,
        keep_monthly=keep_monthly,
        keep_yearly=keep_yearly,
    )
    _run_with_notifications(
        container,
        "Cleanup",
        lambda: CleanupUseCase(container.restic).execute(retention_args),
    )


def _retention_args(**values: int | None) -> list[str]:
    args: list[str] = []
    for name, value in values.items():
        if value is not None:
            args.extend([f"--{name.replace('_', '-')}", str(value)])
    return args


def _run_with_notifications(container: Container, title: str, action: Callable[[], None]) -> None:
    try:
        action()
    except Exception as exc:
        logger.exception("%s failed", title)
        _notify(container, title, str(exc), success=False)
        raise click.ClickException(str(exc)) from exc

    logger.info("%s completed", title)
    _notify(container, title, "Completed successfully", success=True)


def _notify(container: Container, title: str, message: str, success: bool) -> None:
    notifier = container.notifier
    if not notifier:
        return
    mode = container.config.notifications.mode
    if success and mode != NotificationMode.ALWAYS:
        return

    try:
        notifier.notify(title, message, success=success)
    except Exception:
        logger.exception("Notification failed")
