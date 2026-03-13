from typer.testing import CliRunner

from cyberclaw.cli.commands import app

runner = CliRunner()


def test_cron_add_rejects_invalid_timezone(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("cyberclaw.config.paths.get_cron_dir", lambda: tmp_path / "cron")

    result = runner.invoke(
        app,
        [
            "cron",
            "add",
            "--name",
            "demo",
            "--message",
            "hello",
            "--cron",
            "0 9 * * *",
            "--tz",
            "America/Vancovuer",
        ],
    )

    assert result.exit_code != 0
    assert "Error: unknown timezone 'America/Vancovuer'" in result.stdout
    assert not (tmp_path / "cron" / "jobs.json").exists()
