#!/usr/bin/env python3
"""发布前的环境检查。先跑这个，再动仓库。

检查四件事：
1. git 提交身份配了吗
2. GitHub 凭据取得到吗、还有效吗
3. remote 指向哪个仓库
4. github.com:443 直连通不通（决定后面走 git 还是 API）

用法：
    python gh_auth.py            # 在当前目录检查
    python gh_auth.py --repo <路径>
"""
from __future__ import annotations

import argparse
import json
import socket
import sys

from _gh import api, get_token, git, repo_info, say


def net_ok(host="github.com", port=443, timeout=6) -> bool:
    try:
        socket.create_connection((host, port), timeout=timeout).close()
        return True
    except Exception:
        return False


def main(argv=None):
    ap = argparse.ArgumentParser(description="GitHub 发布前环境检查")
    ap.add_argument("--repo", default=".", help="仓库路径，默认当前目录")
    ap.add_argument("--json", action="store_true", help="只输出 JSON")
    a = ap.parse_args(argv)

    out = {"ok": True, "problems": [], "warnings": []}

    name = git("config", "user.name", cwd=a.repo)
    email = git("config", "user.email", cwd=a.repo)
    out["git_user"] = {"name": name, "email": email}
    if not name or not email:
        out["problems"].append("git 提交身份未配置：git config user.name / user.email")
        out["ok"] = False

    info = repo_info(a.repo)
    out["repo"] = {
        "root": info["root"], "remote": info["remote"],
        "owner": info["owner"], "repo": info["repo"],
        "branch": info["branch"], "dirty": info["dirty"],
    }
    if not info["remote"]:
        out["problems"].append("没有 origin remote：git remote add origin <url>")
        out["ok"] = False
    elif not info["owner"]:
        out["problems"].append(f"remote 不是 GitHub 地址，无法解析：{info['remote']}")
        out["ok"] = False
    if info["dirty"]:
        out["warnings"].append("工作区有未提交改动，推送前会先要求提交")

    tok = get_token()
    out["token_present"] = bool(tok)
    if not tok:
        out["problems"].append("取不到 GitHub 凭据，先执行一次 git push 或 gh auth login 完成登录")
        out["ok"] = False
        out["authenticated"] = False
    else:
        code, me = api("/user", tok)
        out["authenticated"] = code == 200
        if code == 200:
            out["login"] = me.get("login")
            scopes = me.get("_scopes") or ""
            out["scopes_hint"] = "创建 release 需要对 repo 的写权限"
            if info["owner"] and me.get("login") and me["login"].lower() != info["owner"].lower():
                out["warnings"].append(
                    f"当前凭据属于 {me['login']}，但 remote 指向 {info['owner']}，确认有写权限"
                )
        else:
            out["problems"].append(f"凭据无效或网络不通（HTTP {code}）：{me}")
            out["ok"] = False

    direct = net_ok()
    out["network_direct"] = direct
    if not direct:
        out["warnings"].append(
            "github.com:443 直连不通，git push 会失败；gh_push.py 会自动改走 API"
        )

    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0 if out["ok"] else 1

    say("环境检查")
    say("")
    say(f"  仓库      {out['repo']['root'] or '(不是 git 仓库)'}")
    say(f"  remote    {out['repo']['remote'] or '(未配置)'}")
    say(f"  分支      {out['repo']['branch'] or '?'}")
    say(f"  git 身份  {name or '(未配置)'} <{email or '?'}>")
    say(f"  凭据      {'有效，账号 ' + out.get('login', '?') if out.get('authenticated') else '不可用'}")
    say(f"  直连      {'通' if direct else '不通（走 API）'}")
    if out["warnings"]:
        say("")
        for w in out["warnings"]:
            say(f"  注意：{w}")
    if out["problems"]:
        say("")
        for p in out["problems"]:
            say(f"  问题：{p}")
        say("")
        say("结论：还不能发布，先解决上面的问题")
        return 1
    say("")
    say("结论：可以开始发布")
    return 0


if __name__ == "__main__":
    sys.exit(main())
