#!/usr/bin/env python3
"""Does every source_url in the brief still resolve? Deterministic, no agent.

WHY THIS IS A SCRIPT AND NOT THE STAGE'S OWN SHELL
--------------------------------------------------
The research director asks for a `source_url` on every data point, and the
fact gate resolves claims against them, so a dead link is a claim that
cannot be defended. The 2026-11-11 research stage went looking for a way to
check them and reached for the shell:

    for u in "https://en.wikipedia.org/..." ...
    curl -s -L -o /dev/null --max-time 25 -w '%{http_code} %{url_effective}'

Both were DENIED, because `curl` is not on the allow-list and should not be:
an allow-listed `curl` is an allow-listed arbitrary fetch, and a stage with
one is a stage that can reach anything. Those two denials cost the stage
turns on a cap with one turn of margin.

Checking a list of URLs is deterministic work with no judgement in it, which
is exactly the kind of work that belongs in a script rather than in an
agent's turns.

HEAD FIRST, THEN GET. A HEAD is a few hundred bytes and tells you
everything; but plenty of servers answer 405 or 501 to it, and some answer
403 to a HEAD while serving the GET fine, so a HEAD that fails in a way that
is ABOUT THE METHOD is retried as a GET before the URL is called broken. A
redirect is followed and the final URL reported, because a source that now
redirects to a parked domain is a dead source that answers 200.

    .venv/bin/python scripts/check_urls.py --project king-tut
    .venv/bin/python scripts/check_urls.py --url https://example.org/a
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]

#: The same generic client name the other fetchers use. It names the project,
#: never the person running it.
UA = ("wak3upsociety-documentary/1.0 "
      "(https://github.com/ToolbeltiOS/OpenMontage; source-url check) "
      "python-urllib")

TIMEOUT = 20
#: A HEAD rejected for being a HEAD, rather than for the URL being wrong.
METHOD_PROBLEM = (403, 405, 501, 400)


class Result:
    __slots__ = ("url", "status", "final", "method", "error")

    def __init__(self, url: str, status: int | None, final: str | None,
                 method: str, error: str | None = None) -> None:
        self.url, self.status, self.final = url, status, final
        self.method, self.error = method, error

    @property
    def ok(self) -> bool:
        return self.status is not None and 200 <= self.status < 400

    @property
    def redirected(self) -> bool:
        return bool(self.final and self.final.rstrip("/") !=
                    self.url.rstrip("/"))

    def line(self) -> str:
        mark = "ok " if self.ok else "BAD"
        status = self.status if self.status is not None else "---"
        out = f"  {mark} {status:>3}  {self.method:4s} {self.url}"
        if self.redirected:
            out += f"\n          -> {self.final}"
        if self.error:
            out += f"\n          {self.error}"
        return out


def _open(url: str, method: str, timeout: int) -> tuple[int, str]:
    request = urllib.request.Request(url, method=method,
                                     headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.geturl()


def fetch(url: str, timeout: int = TIMEOUT) -> Result:
    """One URL, HEAD then GET. Never raises."""
    for method in ("HEAD", "GET"):
        try:
            status, final = _open(url, method, timeout)
            return Result(url, status, final, method)
        except urllib.error.HTTPError as exc:
            if method == "HEAD" and exc.code in METHOD_PROBLEM:
                continue                      # ask again properly
            return Result(url, exc.code, None, method, f"HTTP {exc.reason}")
        except urllib.error.URLError as exc:
            return Result(url, None, None, method, f"{exc.reason}")
        except Exception as exc:                               # noqa: BLE001
            return Result(url, None, None, method,
                          f"{type(exc).__name__}: {exc}")
    return Result(url, None, None, "GET", "unreachable")


def urls_in(brief: dict) -> list[str]:
    """Every URL the brief offers as evidence, deduplicated, in order."""
    seen: dict[str, None] = {}
    for point in brief.get("data_points") or []:
        url = (point.get("source_url") or "").strip()
        if url.startswith("http"):
            seen.setdefault(url, None)
    for source in brief.get("sources") or []:
        url = (source.get("url") or "").strip() if isinstance(source, dict) \
            else ""
        if url.startswith("http"):
            seen.setdefault(url, None)
    for group in ("landscape", "visual_references"):
        blob = brief.get(group)
        for entry in (blob.get("existing_content") if isinstance(blob, dict)
                      else blob) or []:
            if isinstance(entry, dict):
                url = (entry.get("url") or "").strip()
                if url.startswith("http"):
                    seen.setdefault(url, None)
    return list(seen)


def check(urls: Iterable[str], fetcher: Callable[[str], Result] = fetch
          ) -> list[Result]:
    return [fetcher(u) for u in urls]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default=None)
    ap.add_argument("--brief", default=None)
    ap.add_argument("--url", action="append", default=[])
    ap.add_argument("--timeout", type=int, default=TIMEOUT)
    args = ap.parse_args()

    if args.url:
        urls = args.url
    else:
        if not (args.project or args.brief):
            print("give --project, --brief or --url", file=sys.stderr)
            return 2
        path = (Path(args.brief) if args.brief else
                ROOT / "projects" / args.project / "artifacts" /
                "research_brief.json")
        if not path.exists():
            print(f"no research brief at {path}", file=sys.stderr)
            return 2
        urls = urls_in(json.loads(path.read_text()))

    if not urls:
        print("no source_url in the brief to check")
        return 0

    print(f"checking {len(urls)} url(s), {args.timeout}s timeout")
    results = check(urls, lambda u: fetch(u, args.timeout))
    for r in results:
        print(r.line(), flush=True)

    bad = [r for r in results if not r.ok]
    moved = [r for r in results if r.ok and r.redirected]
    print(f"\n{len(results) - len(bad)}/{len(results)} resolve"
          f"{f', {len(moved)} redirect' if moved else ''}"
          f"{f', {len(bad)} BAD' if bad else ''}")
    if bad:
        print("\nA dead source_url is a claim that cannot be defended. "
              "Replace the source or cut the data point — do not leave the "
              "id in the ledger for the script stage to cite.")
        for r in bad:
            print(f"  {r.url}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
