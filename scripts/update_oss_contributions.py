"""
Update the Open Source Contributions section of the README.

Queries the GitHub Search API for merged PRs authored by USERNAME,
groups them by repo, and rewrites the section between the markers:

  <!-- OSS:START -->
  ...generated content...
  <!-- OSS:END -->

Runs in a GitHub Action with GITHUB_TOKEN; no external dependencies
beyond `requests`.
"""

from __future__ import annotations

import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import requests

USERNAME = "AshutoshDevpura"
README_PATH = Path("README.md")
START = "<!-- OSS:START -->"
END = "<!-- OSS:END -->"

# Repos to feature at the top of the table, in this order.
# Anything else is listed after, alphabetically.
FEATURED_REPOS = [
    "scikit-learn/scikit-learn",
    "optuna/optuna",
    "shap/shap",
    "pandas-dev/pandas",
    "numpy/numpy",
    "statsmodels/statsmodels",
]

API_URL = "https://api.github.com/search/issues"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

token = os.environ.get("GITHUB_TOKEN")
if token:
    HEADERS["Authorization"] = f"Bearer {token}"


def fetch_merged_prs() -> list[dict]:
    """Page through the search API and return every merged PR."""
    query = f"author:{USERNAME} is:pr is:merged"
    results: list[dict] = []
    page = 1
    while True:
        resp = requests.get(
            API_URL,
            headers=HEADERS,
            params={"q": query, "per_page": 100, "page": page, "sort": "created", "order": "desc"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        if not items:
            break
        results.extend(items)
        if len(items) < 100:
            break
        page += 1
        if page > 10:  # safety cap
            break
    return results


def repo_from_url(pr_url: str) -> str:
    """Extract 'owner/repo' from an API URL like
    https://api.github.com/repos/optuna/optuna (no trailing slash on
    `repository_url`) or https://api.github.com/repos/optuna/optuna/issues/1."""
    m = re.search(r"/repos/([^/]+/[^/]+?)(?:/|$)", pr_url)
    return m.group(1) if m else "unknown/unknown"


def sort_key(repo: str) -> tuple[int, str]:
    """Featured repos sort first in listed order; others alphabetically."""
    if repo in FEATURED_REPOS:
        return (0, f"{FEATURED_REPOS.index(repo):03d}")
    return (1, repo.lower())


def build_section(prs: list[dict]) -> str:
    if not prs:
        return (
            "\n_No merged PRs found yet — the workflow will populate this "
            "section automatically once merges roll in._\n"
        )

    # Group by repo
    by_repo: dict[str, list[dict]] = defaultdict(list)
    for pr in prs:
        by_repo[repo_from_url(pr["repository_url"])].append(pr)

    total = len(prs)
    repo_count = len(by_repo)

    lines: list[str] = []
    lines.append("")
    lines.append(
        f"![Merged PRs](https://img.shields.io/badge/Merged_PRs-{total}-2ea44f?style=flat-square) "
        f"![Repos](https://img.shields.io/badge/Repos-{repo_count}-blue?style=flat-square)"
    )
    lines.append("")

    for repo in sorted(by_repo.keys(), key=sort_key):
        repo_prs = sorted(by_repo[repo], key=lambda p: p["number"], reverse=True)
        lines.append(f"**[`{repo}`](https://github.com/{repo})**")
        lines.append("")
        for pr in repo_prs:
            num = pr["number"]
            title = pr["title"].replace("|", "\\|").strip()
            url = pr["html_url"]
            lines.append(f"- [#{num}]({url}) — {title}")
        lines.append("")

    lines.append(
        f"<sub>Auto-generated from the GitHub API · "
        f"[see all merged PRs →](https://github.com/pulls?q=is%3Apr+author%3A{USERNAME}+is%3Amerged)</sub>"
    )
    lines.append("")
    return "\n".join(lines)


def splice(readme: str, new_body: str) -> str:
    pattern = re.compile(
        re.escape(START) + r".*?" + re.escape(END),
        re.DOTALL,
    )
    replacement = f"{START}{new_body}{END}"
    if not pattern.search(readme):
        raise SystemExit(
            f"Markers not found in README. Add `{START}` and `{END}` "
            f"where the Open Source Contributions section should go."
        )
    return pattern.sub(replacement, readme)


def main() -> int:
    prs = fetch_merged_prs()
    print(f"Found {len(prs)} merged PRs.", file=sys.stderr)

    readme = README_PATH.read_text(encoding="utf-8")
    new_readme = splice(readme, build_section(prs))

    if new_readme == readme:
        print("No changes to README.", file=sys.stderr)
        return 0

    README_PATH.write_text(new_readme, encoding="utf-8")
    print("README updated.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())