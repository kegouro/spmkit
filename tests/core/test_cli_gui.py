from typer.testing import CliRunner

from spmkit.cli.app import app

runner = CliRunner()


def test_gui_help_no_anuncia_legacy() -> None:
    result = runner.invoke(app, ["gui", "--help"])

    assert result.exit_code == 0, result.output
    assert "--legacy" not in result.output
