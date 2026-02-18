"""Tests for search config and environment variable handling."""

import os

from search.config import check_env, get_jina_key, get_s2_key, get_serper_key, save_key

import pytest


class TestCheckEnv:
    def test_returns_all_vars(self):
        statuses = check_env()
        var_names = [name for name, _, _ in statuses]
        assert "SERPER_API_KEY" in var_names
        assert "S2_API_KEY" in var_names
        assert "JINA_API_KEY" in var_names

    def test_detects_set_var(self, monkeypatch):
        monkeypatch.setenv("SERPER_API_KEY", "test-key")
        statuses = check_env()
        serper = next(s for s in statuses if s[0] == "SERPER_API_KEY")
        assert serper[1] is True

    def test_detects_unset_var(self, monkeypatch):
        monkeypatch.delenv("SERPER_API_KEY", raising=False)
        statuses = check_env()
        serper = next(s for s in statuses if s[0] == "SERPER_API_KEY")
        assert serper[1] is False


class TestGetSerperKey:
    def test_returns_key(self, monkeypatch):
        monkeypatch.setenv("SERPER_API_KEY", "sk-test")
        assert get_serper_key() == "sk-test"

    def test_raises_when_missing(self, monkeypatch):
        monkeypatch.delenv("SERPER_API_KEY", raising=False)
        with pytest.raises(ValueError, match="SERPER_API_KEY"):
            get_serper_key()


class TestGetS2Key:
    def test_returns_key(self, monkeypatch):
        monkeypatch.setenv("S2_API_KEY", "s2-test")
        assert get_s2_key() == "s2-test"

    def test_returns_none_when_missing(self, monkeypatch):
        monkeypatch.delenv("S2_API_KEY", raising=False)
        assert get_s2_key() is None


class TestGetJinaKey:
    def test_returns_key(self, monkeypatch):
        monkeypatch.setenv("JINA_API_KEY", "jina-test")
        assert get_jina_key() == "jina-test"

    def test_raises_when_missing(self, monkeypatch):
        monkeypatch.delenv("JINA_API_KEY", raising=False)
        with pytest.raises(ValueError, match="JINA_API_KEY"):
            get_jina_key()


class TestSaveKey:
    def test_save_new_key(self, tmp_path, monkeypatch):
        import search.config as config
        monkeypatch.setattr(config, "PAPERS_DIR", tmp_path)
        monkeypatch.setattr(config, "PERSISTENT_ENV", tmp_path / ".env")

        path = save_key("SERPER_API_KEY", "sk-123")
        assert path == tmp_path / ".env"

        content = path.read_text()
        assert "SERPER_API_KEY=sk-123" in content

    def test_update_existing_key(self, tmp_path, monkeypatch):
        import search.config as config
        monkeypatch.setattr(config, "PAPERS_DIR", tmp_path)
        monkeypatch.setattr(config, "PERSISTENT_ENV", tmp_path / ".env")

        save_key("SERPER_API_KEY", "old-value")
        save_key("SERPER_API_KEY", "new-value")

        content = (tmp_path / ".env").read_text()
        assert "SERPER_API_KEY=new-value" in content
        assert "old-value" not in content

    def test_preserves_other_keys(self, tmp_path, monkeypatch):
        import search.config as config
        monkeypatch.setattr(config, "PAPERS_DIR", tmp_path)
        monkeypatch.setattr(config, "PERSISTENT_ENV", tmp_path / ".env")

        save_key("SERPER_API_KEY", "serper-val")
        save_key("JINA_API_KEY", "jina-val")

        content = (tmp_path / ".env").read_text()
        assert "SERPER_API_KEY=serper-val" in content
        assert "JINA_API_KEY=jina-val" in content

    def test_sets_in_current_process(self, tmp_path, monkeypatch):
        import search.config as config
        monkeypatch.setattr(config, "PAPERS_DIR", tmp_path)
        monkeypatch.setattr(config, "PERSISTENT_ENV", tmp_path / ".env")
        monkeypatch.delenv("S2_API_KEY", raising=False)

        save_key("S2_API_KEY", "s2-test")
        assert os.environ.get("S2_API_KEY") == "s2-test"
