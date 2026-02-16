"""Tests for paper.fetcher — arxiv URL resolution and PDF fetching."""

import pytest

from paper.fetcher import resolve_arxiv_id


class TestResolveArxivId:
    def test_bare_id(self):
        assert resolve_arxiv_id("2302.13971") == "2302.13971"

    def test_bare_id_with_version(self):
        assert resolve_arxiv_id("2302.13971v2") == "2302.13971v2"

    def test_abs_url(self):
        assert resolve_arxiv_id("https://arxiv.org/abs/2302.13971") == "2302.13971"

    def test_pdf_url(self):
        assert resolve_arxiv_id("https://arxiv.org/pdf/2302.13971") == "2302.13971"

    def test_abs_url_with_version(self):
        assert resolve_arxiv_id("https://arxiv.org/abs/2302.13971v1") == "2302.13971v1"

    def test_trailing_slash(self):
        assert resolve_arxiv_id("https://arxiv.org/abs/2302.13971/") == "2302.13971"

    def test_whitespace(self):
        assert resolve_arxiv_id("  2302.13971  ") == "2302.13971"

    def test_invalid_returns_none(self):
        assert resolve_arxiv_id("not-a-paper") is None

    def test_empty_returns_none(self):
        assert resolve_arxiv_id("") is None

    def test_five_digit_id(self):
        assert resolve_arxiv_id("2510.25744") == "2510.25744"
