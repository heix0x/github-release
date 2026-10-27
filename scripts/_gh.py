#!/usr/bin/env python3
"""GitHub 操作公共模块：取凭据、调 API、解析 remote。

只依赖标准库，Python 3.8+ 可运行。
"""
from __future__ import annotations

import json
import re
import subprocess
import urllib.error
import urllib.request

DEFAULT_ACCEPT = "application/vnd.github+json"


def get_token(host: str = "github.com"):
    """通过 git credential 取 token。

    跨平台：Windows 走 Git Credential Manager，macOS 走 osxkeychain，
    Linux 走 libsecret/store。不读也不写任何配置文件。
    取不到返回 None（通常是没登录过 GitHub）。
    """
    try:
        p = subprocess.run(
            ["git", "credential", "fill"],
            input=f"protocol=https\nhost={host}\n\n",
            capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=20,
        )
    except Exception:
        return None
    for line in (p.stdout or "").splitlines():
        if line.startswith("password="):
            v = line.split("=", 1)[1].strip()
            if v:
                return v
    return None


def api(target, token, method="GET", data=None, raw=None, ctype=None,
        accept=None, timeout=60):
    """调 GitHub API。

    target 可以是完整 URL（用于 uploads.github.com）或以 / 开头的路径。
    返回 (status, body)。status 为 0 表示网络层失败。
    """
    url = target if target.startswith("http") else "https://api.github.com" + target
    headers = {
        "Authorization": f"token {token}",
        "Accept": accept or DEFAULT_ACCEPT,
        "User-Agent": "github-release-skill",
    }
    if raw is not None:
        headers["Content-Type"] = ctype or "application/octet-stream"
    elif data is not None:
        headers["Content-Type"] = ctype or "application/json"

    body = raw if raw is not None else (json.dumps(data).encode() if data is not None else None)
    req = urllib.request.Request(url, method=method, headers=headers, data=body)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = r.read()
            if not payload.strip():
                return r.status, None
            if payload.lstrip()[:1] in (b"{", b"["):
                return r.status, json.loads(payload)
            return r.status, payload.decode("utf-8", "replace")[:500]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:500]
    except Exception as e:
        return 0, str(e)


RE_REMOTE = re.compile(r"github\.com[:/](?P<owner>[^/\s]+)/(?P<repo>[^/\s]+?)(?:\.git)?/*$")


def parse_remote(url: str):
    """从 https / ssh 形式的 remote 地址里取出 (owner, repo)。"""
    if not url:
        return None
    m = RE_REMOTE.search(url.strip())
    if not m:
        return None
    return m.group("owner"), m.group("repo")


def git(*args, cwd="."):
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return (p.stdout or "").strip()


def repo_info(cwd="."):
    url = git("remote", "get-url", "origin", cwd=cwd)
    parsed = parse_remote(url) if url else None
    return {
        "root": git("rev-parse", "--show-toplevel", cwd=cwd),
        "remote": url,
        "owner": parsed[0] if parsed else None,
        "repo": parsed[1] if parsed else None,
        "branch": git("rev-parse", "--abbrev-ref", "HEAD", cwd=cwd),
        "head": git("rev-parse", "HEAD", cwd=cwd),
        "dirty": bool(git("status", "--porcelain", cwd=cwd)),
        "remote_head": git("rev-parse", f"origin/{git('rev-parse', '--abbrev-ref', 'HEAD', cwd=cwd)}", cwd=cwd),
    }


def say(msg=""):
    print(msg, flush=True)
