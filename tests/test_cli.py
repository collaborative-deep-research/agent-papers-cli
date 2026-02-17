"""Tests for paper.cli — CLI command smoke tests."""

import pytest
from click.testing import CliRunner

from paper.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


class TestCLI:
    def test_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "paper" in result.output.lower()

    def test_outline_help(self, runner):
        result = runner.invoke(cli, ["outline", "--help"])
        assert result.exit_code == 0
        assert "REFERENCE" in result.output

    def test_read_help(self, runner):
        result = runner.invoke(cli, ["read", "--help"])
        assert result.exit_code == 0
        assert "REFERENCE" in result.output

    def test_skim_help(self, runner):
        result = runner.invoke(cli, ["skim", "--help"])
        assert result.exit_code == 0
        assert "--lines" in result.output

    def test_search_help(self, runner):
        result = runner.invoke(cli, ["search", "--help"])
        assert result.exit_code == 0
        assert "QUERY" in result.output

    def test_info_help(self, runner):
        result = runner.invoke(cli, ["info", "--help"])
        assert result.exit_code == 0

    def test_goto_help(self, runner):
        result = runner.invoke(cli, ["goto", "--help"])
        assert result.exit_code == 0
        assert "REF_ID" in result.output

    def test_no_refs_flag(self, runner):
        """All commands that accept --no-refs should show it in help."""
        for cmd in ["read", "outline", "skim", "search", "info"]:
            result = runner.invoke(cli, [cmd, "--help"])
            assert "--no-refs" in result.output, f"--no-refs missing from {cmd}"

    def test_invalid_reference(self, runner):
        result = runner.invoke(cli, ["outline", "not-a-paper"])
        assert result.exit_code != 0
