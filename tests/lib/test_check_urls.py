"""Checking source_urls is deterministic work, so it is not an agent's job.

The 2026-11-11 research stage tried to verify its own links with a shell
`for` loop and `curl -s -L -o /dev/null -w '%{http_code} %{url_effective}'`.
Both were DENIED — `curl` is not on the allow-list and should not be, since
an allow-listed curl is an allow-listed arbitrary fetch — and the two
denials cost turns on a cap that finished with one turn to spare.

NOTHING HERE TOUCHES THE NETWORK. The session guard blocks outbound
connections, and it should: a test suite that reaches the internet fails
differently every day. The fetcher is injected.
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_urls as C  # noqa: E402


def result(url="https://a.test/x", status=200, final=None, method="HEAD",
           error=None) -> C.Result:
    return C.Result(url, status, final if final is not None else url, method,
                    error)


class TestWhatCountsAsOk:
    @pytest.mark.parametrize("status", [200, 201, 204, 301, 302, 399])
    def test_two_and_three_hundreds_resolve(self, status):
        assert result(status=status).ok

    @pytest.mark.parametrize("status", [400, 403, 404, 410, 500, 503])
    def test_four_and_five_hundreds_do_not(self, status):
        assert not result(status=status).ok

    def test_no_status_at_all_is_not_ok(self):
        assert not C.Result("https://a.test/x", None, None, "GET", "timed out").ok


class TestRedirects:
    def test_a_different_final_url_is_a_redirect(self):
        r = result(url="https://a.test/old", final="https://b.test/new")
        assert r.redirected
        assert "-> https://b.test/new" in r.line()

    def test_a_trailing_slash_is_not_a_redirect(self):
        """Or every URL would be reported as moved."""
        assert not result(url="https://a.test/x",
                          final="https://a.test/x/").redirected

    def test_the_same_url_is_not_a_redirect(self):
        assert not result().redirected


class TestHeadThenGet:
    """A HEAD rejected for being a HEAD is retried properly."""

    @pytest.mark.parametrize("code", C.METHOD_PROBLEM)
    def test_a_method_problem_falls_back_to_get(self, code, monkeypatch):
        calls = []

        def fake_open(url, method, timeout):
            calls.append(method)
            if method == "HEAD":
                raise urllib.error.HTTPError(url, code, "nope", {}, None)
            return 200, url

        monkeypatch.setattr(C, "_open", fake_open)
        r = C.fetch("https://a.test/x")
        assert calls == ["HEAD", "GET"]
        assert r.ok and r.method == "GET"

    def test_a_real_404_is_not_retried(self, monkeypatch):
        """404 says the URL is wrong, not that HEAD was. Retrying wastes a
        request on every dead link in the brief."""
        calls = []

        def fake_open(url, method, timeout):
            calls.append(method)
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

        monkeypatch.setattr(C, "_open", fake_open)
        r = C.fetch("https://a.test/x")
        assert calls == ["HEAD"]
        assert not r.ok and r.status == 404

    def test_a_head_that_works_makes_no_second_request(self, monkeypatch):
        calls = []
        monkeypatch.setattr(C, "_open",
                            lambda u, m, t: (calls.append(m), (200, u))[1])
        assert C.fetch("https://a.test/x").ok
        assert calls == ["HEAD"]

    def test_it_never_raises(self, monkeypatch):
        """A checker that throws on the first bad link checks one link."""
        def boom(url, method, timeout):
            raise RuntimeError("socket exploded")

        monkeypatch.setattr(C, "_open", boom)
        r = C.fetch("https://a.test/x")
        assert not r.ok
        assert "socket exploded" in r.error

    def test_a_url_error_is_reported_not_raised(self, monkeypatch):
        def refuse(url, method, timeout):
            raise urllib.error.URLError("timed out")

        monkeypatch.setattr(C, "_open", refuse)
        assert "timed out" in C.fetch("https://a.test/x").error


class TestWhichUrlsItFinds:
    BRIEF = {
        "data_points": [
            {"id": "c01", "source_url": "https://a.test/one"},
            {"id": "c02", "source_url": "https://a.test/two"},
            {"id": "c03", "source_url": "https://a.test/one"},   # duplicate
            {"id": "c04", "source_url": ""},                      # empty
            {"id": "c05"},                                        # absent
            {"id": "c06", "source_url": "not-a-url"},             # not http
        ],
        "sources": [{"url": "https://a.test/three"}, {"title": "no url"}],
        "landscape": {"existing_content": [{"url": "https://a.test/four"}]},
    }

    def test_it_takes_every_source_url(self):
        found = C.urls_in(self.BRIEF)
        assert "https://a.test/one" in found
        assert "https://a.test/two" in found

    def test_it_deduplicates(self):
        assert C.urls_in(self.BRIEF).count("https://a.test/one") == 1

    def test_it_skips_empty_and_non_http(self):
        found = C.urls_in(self.BRIEF)
        assert "" not in found
        assert "not-a-url" not in found

    def test_it_also_takes_the_sources_and_the_landscape(self):
        found = C.urls_in(self.BRIEF)
        assert "https://a.test/three" in found
        assert "https://a.test/four" in found

    def test_order_is_stable(self):
        assert C.urls_in(self.BRIEF) == C.urls_in(self.BRIEF)

    def test_an_empty_brief_yields_nothing(self):
        assert C.urls_in({}) == []

    def test_it_reads_a_real_brief(self):
        for film in ("king-tut", "noah", "easter-island"):
            p = ROOT / "projects" / film / "artifacts" / "research_brief.json"
            if p.exists():
                assert len(C.urls_in(json.loads(p.read_text()))) > 5
                return
        pytest.skip("no real brief in this worktree")


class TestTheExitCode:
    def test_all_good_exits_zero(self, tmp_path, monkeypatch):
        brief = tmp_path / "b.json"
        brief.write_text(json.dumps(
            {"data_points": [{"source_url": "https://a.test/x"}]}))
        monkeypatch.setattr(C, "_open", lambda u, m, t: (200, u))
        monkeypatch.setattr(sys, "argv",
                            ["check_urls.py", "--brief", str(brief)])
        assert C.main() == 0

    def test_one_dead_link_exits_one(self, tmp_path, monkeypatch, capsys):
        brief = tmp_path / "b.json"
        brief.write_text(json.dumps(
            {"data_points": [{"source_url": "https://a.test/gone"}]}))

        def dead(url, method, timeout):
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

        monkeypatch.setattr(C, "_open", dead)
        monkeypatch.setattr(sys, "argv",
                            ["check_urls.py", "--brief", str(brief)])
        assert C.main() == 1
        out = capsys.readouterr().out
        assert "cannot be defended" in out
        assert "https://a.test/gone" in out

    def test_no_urls_is_not_a_failure(self, tmp_path, monkeypatch):
        brief = tmp_path / "b.json"
        brief.write_text(json.dumps({"data_points": []}))
        monkeypatch.setattr(sys, "argv",
                            ["check_urls.py", "--brief", str(brief)])
        assert C.main() == 0

    def test_a_missing_brief_exits_two(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["check_urls.py", "--brief",
                                          str(tmp_path / "nope.json")])
        assert C.main() == 2

    def test_no_arguments_at_all_exits_two(self, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["check_urls.py"])
        assert C.main() == 2


class TestItIsNamedWhereTheStageWillSeeIt:
    @property
    def director(self) -> str:
        return " ".join((ROOT / "skills" / "pipelines" /
                         "narrated-documentary" /
                         "research-director.md").read_text().split())

    def test_the_research_director_names_the_command(self):
        assert "scripts/check_urls.py --project <slug>" in self.director

    def test_it_is_in_the_quality_gate(self):
        assert "Every `source_url` resolves" in self.director

    def test_it_says_not_to_use_curl_and_why(self):
        assert "Do not check them with the shell" in self.director
        assert "allow-listed arbitrary fetch" in self.director

    def test_curl_is_not_on_the_allow_list(self):
        allow = json.loads(
            (ROOT / ".claude" / "settings.json").read_text()
        )["permissions"]["allow"]
        assert not any("curl" in a for a in allow)

    def test_the_user_agent_names_the_project_not_a_person(self):
        """A fetcher must not put the operator's identity on the wire."""
        assert "wak3upsociety-documentary" in C.UA
        for leak in ("mac", "@", "Users"):
            assert leak not in C.UA.replace("ToolbeltiOS", "")
