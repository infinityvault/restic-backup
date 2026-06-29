from __future__ import annotations

from restic_backup.adapters.process import ProcessCommandError


def test_process_command_error_includes_stdout_and_stderr() -> None:
    error = ProcessCommandError(
        returncode=3,
        cmd=["restic", "backup", "."],
        output="saved partial snapshot\n",
        stderr="read error\n",
    )

    message = str(error)

    assert "returned non-zero exit status 3" in message
    assert "stdout:\nsaved partial snapshot" in message
    assert "stderr:\nread error" in message
