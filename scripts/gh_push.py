#!/usr/bin/env python3
"""推送本地提交到 GitHub。git 走不通时自动改走 Git Data API。

为什么需要这个：某些网络环境下 github.com:443 直连超时，git push 必然失败；
而 api.github.com 往往还能通。本脚本先用 git，失败就换 API，两条路都能把提交送上去。

前置：本地已经 commit 过（工作区必须干净）。

用法：
    python gh_push.py                     # 当前目录，推当前分支
    python gh_push.py --repo <路径>
    python gh_push.py --force             # 覆盖远程（危险，先确认）
    python gh_push.py --api-only          # 跳过 git，直接走 API
    python gh_push.py --dry-run           # 只报告，不推送
"""
from __future__ import annotations

import argparse
import base64
import os
import subprocess
import sys

from _gh import api, get_token, git, repo_info, say


def try_git_push(repo: str, branch: str, force: bool) -> tuple[bool, str]:
    args = ["push", "-u", "origin", branch]
    if force:
        args.insert(1, "--force-with-lease")
    p = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=180)
    msg = ((p.stdout or "") + (p.stderr or "")).strip()
    return p.returncode == 0, msg


def remote_ref(token: str, owner: str, repo: str, branch: str):
    code, body = api(f"/repos/{owner}/{repo}/git/refs/heads/{branch}", token)
    if code == 200:
        return body["object"]["sha"]
    if code == 404:
        return None
    raise RuntimeError(f"读取远程分支失败 HTTP {code}: {body}")


def push_via_api(repo: str, token: str, owner: str, repo_name: str,
                 branch: str, message: str, force: bool) -> dict:
    """用 Git Data API 造一个 commit 并更新分支引用。"""
    files = git("ls-files", cwd=repo).split("\n")
    files = [f for f in files if f.strip()]
    if not files:
        raise RuntimeError("没有已跟踪的文件，先 git add 并 commit")

    parent = remote_ref(token, owner, repo_name, branch)

    items = []
    for f in files:
        raw = open(os.path.join(repo, f), "rb").read()
        code, blob = api(f"/repos/{owner}/{repo_name}/git/blobs", token, "POST",
                         {"content": base64.b64encode(raw).decode(), "encoding": "base64"})
        if code != 201:
            raise RuntimeError(f"创建 blob 失败 {f}: HTTP {code} {blob}")
        items.append({"path": f, "mode": "100644", "type": "blob", "sha": blob["sha"]})

    code, tree = api(f"/repos/{owner}/{repo_name}/git/trees", token, "POST", {"tree": items})
    if code != 201:
        raise RuntimeError(f"创建 tree 失败: HTTP {code} {tree}")

    payload = {"message": message, "tree": tree["sha"]}
    if parent:
        payload["parents"] = [parent]
    code, commit = api(f"/repos/{owner}/{repo_name}/git/commits", token, "POST", payload)
    if code != 201:
        raise RuntimeError(f"创建 commit 失败: HTTP {code} {commit}")

    if parent:
        code, ref = api(f"/repos/{owner}/{repo_name}/git/refs/heads/{branch}", token, "PATCH",
                        {"sha": commit["sha"], "force": bool(force)})
    else:
        code, ref = api(f"/repos/{owner}/{repo_name}/git/refs", token, "POST",
                        {"ref": f"refs/heads/{branch}", "sha": commit["sha"]})
    if code not in (200, 201):
        raise RuntimeError(f"更新分支失败: HTTP {code} {ref}")

    return {"commit": commit["sha"], "parent": parent, "files": len(items)}


def main(argv=None):
    ap = argparse.ArgumentParser(description="推送提交到 GitHub，git 不通时走 API")
    ap.add_argument("--repo", default=".", help="仓库路径")
    ap.add_argument("--branch", help="分支名，默认当前分支")
    ap.add_argument("--message", help="API 提交用的信息，默认取本地 HEAD 的标题")
    ap.add_argument("--force", action="store_true", help="覆盖远程分支")
    ap.add_argument("--api-only", action="store_true", help="跳过 git 直接走 API")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    info = repo_info(a.repo)
    if not info["root"]:
        say("不是 git 仓库"); return 1
    if info["dirty"]:
        say("工作区有未提交改动，先 commit 再推。"); return 1
    if not info["owner"]:
        say(f"remote 不是 GitHub 地址：{info['remote'] or '(未配置)'}"); return 1

    branch = a.branch or info["branch"]
    if not branch or branch == "HEAD":
        say("处于 detached HEAD，用 --branch 指定分支"); return 1

    head_msg = git("log", "-1", "--pretty=%s", cwd=a.repo) or "update"
    message = a.message or head_msg

    say(f"仓库   {info['owner']}/{info['repo']}")
    say(f"分支   {branch}")
    say(f"HEAD   {info['head'][:10]}  {head_msg}")

    if a.dry_run:
        say("\n--dry-run，未执行推送")
        return 0

    if not a.api_only:
        say("\n尝试 git push ...")
        ok, msg = try_git_push(a.repo, branch, a.force)
        if ok:
            say("推送成功（git）")
            for line in msg.splitlines()[-3:]:
                say("  " + line)
            return 0
        say("git 推送失败，原因：")
        for line in msg.splitlines()[-4:]:
            say("  " + line)
        if "rejected" in msg and not a.force:
            say("\n远程有你本地没有的提交。确认可以覆盖后再加 --force，")
            say("或者先 git fetch && git rebase origin/" + branch)
            return 1
        say("\n改用 API 推送 ...")

    tok = get_token()
    if not tok:
        say("取不到凭据，无法走 API"); return 1

    try:
        r = push_via_api(a.repo, tok, info["owner"], info["repo"], branch, message, a.force)
    except Exception as e:
        say(f"API 推送失败：{e}"); return 1

    say("推送成功（API）")
    say(f"  commit {r['commit'][:10]}  parent {r['parent'][:10] if r['parent'] else '(空仓库)'}")
    say(f"  {r['files']} 个文件")
    say("")
    say("注意：本地 HEAD 与远程 commit 的 hash 不同（API 建的 commit 元数据不一样）。")
    say("网络恢复后执行一次 git fetch && git reset --hard origin/" + branch + " 对齐。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
