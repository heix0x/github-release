#!/usr/bin/env python3
"""在 GitHub 上建 Release、传附件、设置仓库 About。

会自动做四件事：
1. 建 tag + release（tag 已存在则复用）
2. 上传附件到 release
3. 有 --description 就改仓库简介，有 --topics 就设话题
4. 打印下载直链，方便直接贴给别人

更新日志可以从 CHANGELOG.md 里按版本号自动摘取，不用手写 --body。

用法：
    python gh_release.py --tag v1.2.0
    python gh_release.py --tag v1.2.0 --asset dist/app-1.2.0.zip
    python gh_release.py --tag v1.2.0 --body-file notes.md --prerelease
    python gh_release.py --tag v1.2.0 \
        --description "Do one thing well — a Playwright-based AI agent skill." \
        --topics ai-agent,skill,playwright
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys

from _gh import api, get_token, repo_info, say

CJK = re.compile(r"[\u4e00-\u9fff]")
TOPIC_OK = re.compile(r"^[a-z0-9][a-z0-9-]{0,49}$")


def warn_meta(description: str | None) -> None:
    """About 应当用英文。

    GitHub 的搜索与 topic 页按英文字面索引，中文 description 只有中文查询能命中，
    英文查询一条都匹配不到。这里只提醒，不拦截——确实要中文就带着发。
    """
    if description and CJK.search(description):
        say("  ! 简介里有中文：英文查询搜不到它，建议改英文（见 SKILL.md「仓库元信息用英文」）")


def clean_topics(raw: str) -> tuple[list[str], list[str]]:
    """GitHub 只接受小写字母、数字、连字符，最多 50 字符。不合规的提前剔除。"""
    items = [t.strip().lower() for t in raw.split(",") if t.strip()]
    ok = [t for t in items if TOPIC_OK.match(t)]
    bad = [t for t in items if t not in ok]
    return ok, bad


def body_from_changelog(path: str, version: str):
    """从 CHANGELOG.md 里摘出指定版本的段落。"""
    if not os.path.exists(path):
        return None
    text = open(path, encoding="utf-8").read()
    ver = version.lstrip("v")
    pattern = re.compile(
        r"^##\s*\[?v?" + re.escape(ver) + r"\]?.*?$(.*?)(?=^##\s|\Z)",
        re.S | re.M,
    )
    m = pattern.search(text)
    if not m:
        return None
    body = m.group(1).strip()
    return body or None


def ensure_release(token, owner, repo, tag, name, body, target, prerelease, draft):
    code, rel = api(f"/repos/{owner}/{repo}/releases", token, "POST", {
        "tag_name": tag,
        "target_commitish": target,
        "name": name or tag,
        "body": body or "",
        "draft": draft,
        "prerelease": prerelease,
    })
    if code == 201:
        return rel, "created"
    if code == 422:
        code2, rel2 = api(f"/repos/{owner}/{repo}/releases/tags/{tag}", token)
        if code2 == 200:
            return rel2, "existing"
        raise RuntimeError(f"tag {tag} 已存在但读不到 release: HTTP {code2} {rel2}")
    raise RuntimeError(f"创建 release 失败: HTTP {code} {rel}")


def upload_assets(token, owner, repo, rel, paths):
    existing = {a["name"] for a in rel.get("assets", [])}
    out = []
    for p in paths:
        name = os.path.basename(p)
        if name in existing:
            out.append({"name": name, "status": "已存在，跳过"})
            continue
        raw = open(p, "rb").read()
        code, asset = api(
            f"https://uploads.github.com/repos/{owner}/{repo}/releases/{rel['id']}/assets?name={name}",
            token, "POST", raw=raw, ctype="application/zip", timeout=300,
        )
        if code == 201:
            out.append({"name": name, "status": "上传成功", "size": asset.get("size")})
        else:
            out.append({"name": name, "status": f"失败 HTTP {code}", "detail": str(asset)[:200]})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="发布 GitHub Release 并配置仓库 About")
    ap.add_argument("--repo", default=".", help="仓库路径")
    ap.add_argument("--tag", required=True, help="版本标签，如 v1.2.0")
    ap.add_argument("--name", help="release 标题，默认与 tag 相同")
    ap.add_argument("--body", help="release 说明正文")
    ap.add_argument("--body-file", help="从文件读正文")
    ap.add_argument("--changelog", default="CHANGELOG.md", help="自动摘取更新日志的文件")
    ap.add_argument("--asset", action="append", default=[], help="要上传的附件，可重复")
    ap.add_argument("--asset-glob", help="用通配符指定附件，如 'dist/*.zip'")
    ap.add_argument("--target", default="main", help="tag 指向的分支或 commit")
    ap.add_argument("--prerelease", action="store_true")
    ap.add_argument("--draft", action="store_true")
    ap.add_argument("--description", help="同时更新仓库简介")
    ap.add_argument("--topics", help="同时设置话题，逗号分隔")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    info = repo_info(a.repo)
    if not info["owner"]:
        say(f"remote 不是 GitHub 地址：{info['remote'] or '(未配置)'}"); return 1
    owner, repo = info["owner"], info["repo"]

    # 附件
    assets = list(a.asset)
    if a.asset_glob:
        assets += sorted(glob.glob(os.path.join(a.repo, a.asset_glob)))
    assets = [p for p in assets if os.path.isfile(p)]
    for p in assets:
        if not os.path.isfile(p):
            say(f"附件不存在：{p}"); return 1

    # 正文
    body = a.body
    if not body and a.body_file:
        body = open(a.body_file, encoding="utf-8").read()
    if not body:
        body = body_from_changelog(os.path.join(a.repo, a.changelog), a.tag)
    if not body:
        say(f"没有 release 正文。用 --body / --body-file，或补 {a.changelog} 的对应段落。")
        return 1

    say(f"仓库   {owner}/{repo}")
    say(f"版本   {a.tag}")
    say(f"附件   {', '.join(os.path.basename(p) for p in assets) if assets else '(无)'}")
    say(f"正文   {len(body)} 字符")

    if a.dry_run:
        say("\n--dry-run，未提交任何更改")
        say("\n--- 正文预览 ---")
        say(body[:600])
        return 0

    tok = get_token()
    if not tok:
        say("取不到凭据"); return 1

    try:
        rel, state = ensure_release(tok, owner, repo, a.tag, a.name, body,
                                    a.target, a.prerelease, a.draft)
    except Exception as e:
        say(f"失败：{e}"); return 1
    say(f"\nrelease {'已存在，复用' if state == 'existing' else '创建成功'}：{rel['html_url']}")

    if assets:
        for r in upload_assets(tok, owner, repo, rel, assets):
            say(f"  附件 {r['name']}  {r['status']}")

    if a.description:
        warn_meta(a.description)
        c, _ = api(f"/repos/{owner}/{repo}", tok, "PATCH", {"description": a.description})
        say(f"仓库简介 {'已更新' if c == 200 else f'更新失败 HTTP {c}'}")

    if a.topics:
        names, bad = clean_topics(a.topics)
        if bad:
            say(f"  话题剔除（只接受小写字母数字连字符）：{', '.join(bad)}")
        c, r = api(f"/repos/{owner}/{repo}/topics", tok, "PUT", {"names": names})
        say(f"话题 {'已设置：' + ', '.join(names) if c == 200 else f'设置失败 HTTP {c}'}")

    if assets:
        say("")
        say("下载直链：")
        for p in assets:
            n = os.path.basename(p)
            say(f"  https://github.com/{owner}/{repo}/releases/download/{a.tag}/{n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
