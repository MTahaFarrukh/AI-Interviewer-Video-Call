"""GitHub REST client with disk cache. Never invents repos, files, or commits."""

from __future__ import annotations

import base64
import json
import logging
import re
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from config import load_prep_settings
from prep.paths import GITHUB_CACHE_DIR, ensure_output_dirs

logger = logging.getLogger("firstround.prep.github")

GITHUB_HOST = "github.com"
API = "https://api.github.com"
USERNAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")


class GitHubError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def parse_github_username(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        raise GitHubError("GitHub URL is empty")
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower()
    if host not in {GITHUB_HOST, f"www.{GITHUB_HOST}"}:
        raise GitHubError(f"Not a GitHub URL: {url}")
    parts = [p for p in (parsed.path or "").split("/") if p]
    if not parts:
        raise GitHubError(f"GitHub URL has no username: {url}")
    username = parts[0]
    if username.lower() in {"orgs", "settings", "marketplace", "topics", "login"}:
        raise GitHubError(f"GitHub URL is not a user or organization: {url}")
    if not USERNAME_RE.match(username):
        raise GitHubError(f"Invalid GitHub username in URL: {url}")
    return username


def github_get(path: str, *, cache_key: str | None = None) -> Any:
    ensure_output_dirs()
    cache_path = GITHUB_CACHE_DIR / f"{_safe_cache_name(cache_key or path)}.json"
    if cache_path.is_file():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            if cached.get("ok"):
                return cached["data"]
        except (OSError, json.JSONDecodeError, KeyError):
            pass

    settings = load_prep_settings()
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "firstround-interview-prep",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    request = Request(API + path, headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 403 and "rate limit" in body.lower():
            raise GitHubError("GitHub API rate limit reached. Set GITHUB_TOKEN and retry.", status=403) from exc
        if exc.code == 404:
            raise GitHubError(f"GitHub resource not found: {path}", status=404) from exc
        raise GitHubError(f"GitHub API error {exc.code} for {path}", status=exc.code) from exc
    except URLError as exc:
        raise GitHubError(f"GitHub API network failure: {type(exc).__name__}") from exc

    cache_path.write_text(json.dumps({"ok": True, "data": payload}, indent=2), encoding="utf-8")
    time.sleep(0.15)
    return payload


def list_repos(username: str, *, per_page: int = 50, max_pages: int = 2) -> list[dict[str, Any]]:
    repos: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        data = github_get(
            f"/users/{username}/repos?per_page={per_page}&page={page}&sort=updated&type=all",
            cache_key=f"repos-{username}-{per_page}-p{page}",
        )
        if not isinstance(data, list):
            raise GitHubError(f"Unexpected repos payload for {username}")
        repos.extend(data)
        if len(data) < per_page:
            break
    return repos


def get_readme(owner: str, repo: str) -> dict[str, str]:
    try:
        data = github_get(f"/repos/{owner}/{repo}/readme", cache_key=f"readme-{owner}-{repo}")
    except GitHubError as exc:
        if exc.status == 404:
            return {"path": "", "text": "", "missing": "true"}
        raise
    content = data.get("content") or ""
    encoding = data.get("encoding") or "base64"
    text = ""
    if encoding == "base64" and content:
        text = base64.b64decode(content.replace("\n", "")).decode("utf-8", errors="replace")
    return {
        "path": str(data.get("path") or "README.md"),
        "text": text[:4000],
        "missing": "false",
    }


def get_commits(owner: str, repo: str, *, count: int = 5, path: str = "") -> list[dict[str, str]]:
    query = f"/repos/{owner}/{repo}/commits?per_page={count}"
    cache_key = f"commits-{owner}-{repo}-{count}"
    if path:
        query += f"&path={quote(path, safe='/')}"
        cache_key = f"commits-path-{owner}-{repo}-{path}-{count}"
    try:
        data = github_get(query, cache_key=cache_key)
    except GitHubError as exc:
        if exc.status in {404, 409}:
            return []
        raise
    commits: list[dict[str, str]] = []
    if not isinstance(data, list):
        return commits
    for item in data:
        sha = str(item.get("sha") or "")
        message = str((item.get("commit") or {}).get("message") or "").splitlines()[0]
        if sha:
            commits.append({"sha": sha, "message": message[:200]})
    return commits


def get_commits_for_path(owner: str, repo: str, path: str, *, count: int = 5) -> list[dict[str, str]]:
    if not path:
        return []
    return get_commits(owner, repo, count=count, path=path)


def commit_touches_file(owner: str, repo: str, path: str, sha: str) -> bool:
    if not owner or not repo or not path or not sha:
        return False
    wanted = sha.lower()
    for item in get_commits_for_path(owner, repo, path):
        found = str(item.get("sha") or "").lower()
        if found == wanted or found.startswith(wanted) or wanted.startswith(found[:7]):
            return True
    return False


def parse_owner_repo(repository_url: str) -> tuple[str, str]:
    raw = (repository_url or "").strip()
    if "://" not in raw:
        raw = "https://" + raw
    parts = [p for p in urlparse(raw).path.split("/") if p]
    if len(parts) < 2:
        return "", ""
    return parts[0], parts[1].removesuffix(".git")


def list_source_files(owner: str, repo: str, default_branch: str) -> list[str]:
    branch = default_branch or "main"
    try:
        data = github_get(
            f"/repos/{owner}/{repo}/git/trees/{branch}?recursive=1",
            cache_key=f"tree-{owner}-{repo}-{branch}",
        )
    except GitHubError:
        return []
    files: list[str] = []
    for item in data.get("tree") or []:
        if item.get("type") != "blob":
            continue
        path = str(item.get("path") or "")
        if _interesting_file(path):
            files.append(path)
        if len(files) >= 80:
            break
    return files


def get_file(owner: str, repo: str, path: str) -> dict[str, str]:
    try:
        data = github_get(
            f"/repos/{owner}/{repo}/contents/{path}",
            cache_key=f"file-{owner}-{repo}-{path}",
        )
    except GitHubError as exc:
        if exc.status == 404:
            return {"path": path, "text": "", "missing": "true"}
        raise
    if isinstance(data, list):
        return {"path": path, "text": "", "missing": "true"}
    content = data.get("content") or ""
    text = ""
    if data.get("encoding") == "base64" and content:
        text = base64.b64decode(content.replace("\n", "")).decode("utf-8", errors="replace")
    return {"path": path, "text": text[:2500], "missing": "false"}


def _interesting_file(path: str) -> bool:
    lowered = path.lower()
    skip_bits = (
        "node_modules/",
        "vendor/",
        "dist/",
        "build/",
        ".github/",
        "conformance",
        ".min.",
        "package-lock",
        "pnpm-lock",
        "yarn.lock",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".ico",
        ".pdf",
        ".woff",
        ".mp4",
    )
    if any(bit in lowered for bit in skip_bits):
        return False
    suffixes = (".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".java", ".md", ".yml", ".yaml")
    return lowered.endswith(suffixes)


def _safe_cache_name(key: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", key)[:180]


def cache_dir() -> Path:
    ensure_output_dirs()
    return GITHUB_CACHE_DIR
