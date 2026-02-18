"""Tests for search CLI — command registration and help text."""

import pytest
from click.testing import CliRunner

from search.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


class TestSearchCLI:
    def test_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "search" in result.output.lower()

    def test_env_help(self, runner):
        result = runner.invoke(cli, ["env", "--help"])
        assert result.exit_code == 0

    def test_env_shows_status(self, runner):
        result = runner.invoke(cli, ["env"])
        assert result.exit_code == 0
        assert "SERPER_API_KEY" in result.output
        assert "S2_API_KEY" in result.output
        assert "JINA_API_KEY" in result.output

    def test_env_set_help(self, runner):
        result = runner.invoke(cli, ["env", "set", "--help"])
        assert result.exit_code == 0
        assert "KEY" in result.output
        assert "VALUE" in result.output

    def test_env_set_invalid_key(self, runner):
        result = runner.invoke(cli, ["env", "set", "INVALID_KEY", "value"])
        assert result.exit_code == 1
        assert "Unknown key" in result.output

    def test_env_set_saves_key(self, runner, tmp_path, monkeypatch):
        # Redirect PAPERS_DIR to tmp
        import search.config as config
        monkeypatch.setattr(config, "PAPERS_DIR", tmp_path)
        monkeypatch.setattr(config, "PERSISTENT_ENV", tmp_path / ".env")

        result = runner.invoke(cli, ["env", "set", "SERPER_API_KEY", "test-123"])
        assert result.exit_code == 0
        assert "Saved" in result.output

        env_content = (tmp_path / ".env").read_text()
        assert "SERPER_API_KEY=test-123" in env_content


class TestGoogleCLI:
    def test_google_help(self, runner):
        result = runner.invoke(cli, ["google", "--help"])
        assert result.exit_code == 0
        assert "web" in result.output
        assert "scholar" in result.output

    def test_google_web_help(self, runner):
        result = runner.invoke(cli, ["google", "web", "--help"])
        assert result.exit_code == 0
        assert "QUERY" in result.output
        assert "--num" in result.output

    def test_google_scholar_help(self, runner):
        result = runner.invoke(cli, ["google", "scholar", "--help"])
        assert result.exit_code == 0
        assert "QUERY" in result.output

    def test_google_web_missing_key(self, runner, monkeypatch):
        monkeypatch.delenv("SERPER_API_KEY", raising=False)
        result = runner.invoke(cli, ["google", "web", "test query"])
        assert result.exit_code == 1
        assert "SERPER_API_KEY" in result.output


class TestSemanticScholarCLI:
    def test_semanticscholar_help(self, runner):
        result = runner.invoke(cli, ["semanticscholar", "--help"])
        assert result.exit_code == 0
        assert "papers" in result.output
        assert "snippets" in result.output
        assert "citations" in result.output
        assert "references" in result.output
        assert "details" in result.output

    def test_papers_help(self, runner):
        result = runner.invoke(cli, ["semanticscholar", "papers", "--help"])
        assert result.exit_code == 0
        assert "--year" in result.output
        assert "--min-citations" in result.output
        assert "--venue" in result.output
        assert "--sort" in result.output

    def test_snippets_help(self, runner):
        result = runner.invoke(cli, ["semanticscholar", "snippets", "--help"])
        assert result.exit_code == 0
        assert "--paper-ids" in result.output

    def test_citations_help(self, runner):
        result = runner.invoke(cli, ["semanticscholar", "citations", "--help"])
        assert result.exit_code == 0
        assert "PAPER_ID" in result.output

    def test_references_help(self, runner):
        result = runner.invoke(cli, ["semanticscholar", "references", "--help"])
        assert result.exit_code == 0
        assert "PAPER_ID" in result.output

    def test_details_help(self, runner):
        result = runner.invoke(cli, ["semanticscholar", "details", "--help"])
        assert result.exit_code == 0
        assert "PAPER_ID" in result.output


class TestPubMedCLI:
    def test_pubmed_help(self, runner):
        result = runner.invoke(cli, ["pubmed", "--help"])
        assert result.exit_code == 0
        assert "QUERY" in result.output
        assert "--limit" in result.output
        assert "--offset" in result.output


class TestBrowseCLI:
    def test_browse_help(self, runner):
        result = runner.invoke(cli, ["browse", "--help"])
        assert result.exit_code == 0
        assert "URL" in result.output
        assert "--backend" in result.output
        assert "jina" in result.output
        assert "serper" in result.output

    def test_browse_missing_key(self, runner, monkeypatch):
        monkeypatch.delenv("JINA_API_KEY", raising=False)
        result = runner.invoke(cli, ["browse", "https://example.com"])
        assert result.exit_code == 1
        assert "JINA_API_KEY" in result.output
