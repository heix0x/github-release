#!/usr/bin/env python3
"""发布前安全扫描：找出不该进公开仓库的东西。

扫的对象是「即将被 git add 收进去的全部文件」——
已跟踪的，加上未跟踪且没被 .gitignore 排除的。后者最容易被忘掉。

三个级别：
    BLOCK  几乎不可能是误报（私钥块、云厂商密钥格式）→ 必须处理
    WARN   可能是真泄露，也可能是文档示例 → 人确认
    INFO   体积与类型提示 → 看一眼

退出码：0 干净 · 2 有 BLOCK · 3 只有 WARN
`--strict` 让 WARN 也算失败。

豁免写在仓库根的 .ghscanignore，一行一条：
    <规则名>  <路径 glob>
    <路径 glob>                 # 该路径豁免所有规则
规则名在报告里，路径支持 * 和 **。

用法：
    python gh_scan.py
    python gh_scan.py --repo <路径>
    python gh_scan.py --strict
    python gh_scan.py --extra "2261\\d{8}"     # 追加自定义规则（WARN）
    python gh_scan.py --json
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path

MAX_SCAN_BYTES = 2 * 1024 * 1024
BIG_FILE_BYTES = 1024 * 1024
MAX_HITS_PER_RULE = 5

# ---------------------------------------------------------------- 规则

BLOCK, WARN, INFO = "BLOCK", "WARN", "INFO"

# (级别, 规则名, 正则, 说明)
CONTENT_RULES = [
    (BLOCK, "PRIVATE_KEY",
     r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
     "硬编码私钥"),
    (BLOCK, "AWS_ACCESS_KEY",
     r"\bAKIA[0-9A-Z]{16}\b",
     "AWS Access Key ID"),
    (BLOCK, "GITHUB_TOKEN",
     r"\bgh[pousr]_[A-Za-z0-9]{36,}\b",
     "GitHub token"),
    (BLOCK, "GITLAB_TOKEN",
     r"\bglpat-[A-Za-z0-9_-]{20,}\b",
     "GitLab token"),
    (BLOCK, "SLACK_TOKEN",
     r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b",
     "Slack token"),
    (BLOCK, "OPENAI_KEY",
     r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b",
     "OpenAI / 兼容接口的 key"),
    (BLOCK, "GOOGLE_API_KEY",
     r"\bAIza[0-9A-Za-z_-]{35}\b",
     "Google API key"),
    (BLOCK, "STRIPE_LIVE_KEY",
     r"\b[sr]k_live_[0-9A-Za-z]{20,}\b",
     "Stripe 生产密钥"),

    (WARN, "GENERIC_SECRET",
     r"(?i)(?:api[_-]?key|secret|passwd|password|access[_-]?key|auth[_-]?token)"
     r"\s*[:=]\s*['\"]([^'\"\s]{8,})['\"]",
     "疑似把密码/密钥写成了字面量"),
    (WARN, "ABS_PATH_WIN",
     r"[A-Za-z]:[\\/]{1,4}Users[\\/][A-Za-z0-9._-]{2,}",
     "Windows 绝对路径带用户名"),
    (WARN, "ABS_PATH_UNIX",
     r"/(?:Users|home)/[A-Za-z0-9._-]{2,}/",
     "Unix 绝对路径带用户名"),
    (WARN, "EMAIL",
     r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
     "邮箱地址"),
    (WARN, "CN_ID_CARD",
     r"(?<!\d)\d{17}[\dXx](?!\d)",
     "18 位身份证号"),
    (WARN, "CN_PHONE",
     r"(?<!\d)1[3-9]\d{9}(?!\d)",
     "手机号"),
    (WARN, "PIPE_TO_SHELL",
     r"(?:curl|wget)[^\n|]{0,200}\|\s*(?:sudo\s+)?(?:ba|z)?sh\b",
     "下载即执行"),
    (WARN, "EVAL_INPUT",
     r"\beval\s*\(\s*input\s*\(",
     "eval 直接套在 input 外面"),
    (WARN, "OS_SYSTEM_FSTRING",
     r"os\.system\s*\(\s*f['\"]",
     "os.system 拼 f-string，容易被注入"),
]

# 路径规则：(级别, 规则名, 文件名 glob, 说明)
PATH_RULES = [
    (WARN, "ENV_FILE", ".env", ".env 文件"),
    (WARN, "ENV_FILE", ".env.*", ".env 文件"),
    (WARN, "SSH_KEY", "id_rsa*", "私钥文件"),
    (WARN, "SSH_KEY", "id_ed25519*", "私钥文件"),
    (WARN, "CERT_FILE", "*.p12", "证书/密钥库"),
    (WARN, "CERT_FILE", "*.pfx", "证书/密钥库"),
    (WARN, "CERT_FILE", "*.jks", "Java 密钥库"),
    (WARN, "CERT_FILE", "*.keystore", "Java 密钥库"),
    (WARN, "CERT_FILE", "*.pem", "证书或私钥"),
    (WARN, "CERT_FILE", "*.key", "私钥"),
    (WARN, "CREDENTIAL_FILE", "credentials*", "凭据文件"),
    (WARN, "CREDENTIAL_FILE", "service-account*.json", "服务账号密钥"),
    (INFO, "BINARY_DB", "*.db", "数据库文件"),
    (INFO, "BINARY_DB", "*.sqlite*", "数据库文件"),
]

# 报告里要打码的规则：打印出来等于二次泄露
# （私钥的 BEGIN/END 头不算秘密，打码反而看不出是哪种密钥，故不列入）
MASK_RULES = {
    "AWS_ACCESS_KEY", "GITHUB_TOKEN", "GITLAB_TOKEN",
    "SLACK_TOKEN", "OPENAI_KEY", "GOOGLE_API_KEY", "STRIPE_LIVE_KEY",
    "GENERIC_SECRET", "CUSTOM",
}

EMAIL_ALLOW = re.compile(
    r"@(?:users\.noreply\.github\.com|example\.(?:com|org|net)|.*\.test)$",
    re.I,
)


def git(*args: str, cwd: str) -> str:
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.stdout if p.returncode == 0 else ""


def collect_files(repo: str) -> tuple[list[str], list[str], list[str]]:
    tracked = [f for f in git("ls-files", "-z", cwd=repo).split("\0") if f]
    untracked = [f for f in git("ls-files", "-z", "--others",
                                "--exclude-standard", cwd=repo).split("\0") if f]
    return tracked, untracked, sorted(set(tracked) | set(untracked))


def load_ignore(repo: str) -> list[tuple[str, str]]:
    """读 .ghscanignore。返回 [(规则名 或 '*', glob)]。"""
    p = Path(repo) / ".ghscanignore"
    if not p.is_file():
        return []
    out = []
    for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) == 1:
            out.append(("*", parts[0]))
        else:
            for g in parts[1:]:
                out.append((parts[0], g))
    return out


def ignored(rules: list[tuple[str, str]], rule: str, rel: str) -> bool:
    for name, glob in rules:
        if name not in ("*", rule):
            continue
        if fnmatch.fnmatch(rel, glob) or fnmatch.fnmatch(Path(rel).name, glob):
            return True
        if glob.startswith("**/") and fnmatch.fnmatch(rel, glob[3:]):
            return True
    return False


def mask(text: str) -> str:
    if len(text) <= 8:
        return "*" * len(text)
    return f"{text[:4]}***{text[-4:]}"


def looks_binary(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            return b"\0" in f.read(8192)
    except OSError:
        return True


def scan(repo: str, extra: list[str]) -> dict:
    tracked, untracked, files = collect_files(repo)
    ignore_rules = load_ignore(repo)
    names = git("config", "user.name", cwd=repo).strip()
    # 只对「像人名的」生效：含中文或带空格。heix0x 这种句柄本来就是公开的，不算泄露。
    if names and not (re.search(r"[\u4e00-\u9fff]", names) or " " in names):
        names = ""

    hits = []
    skipped = []

    def add(level, rule, rel, line_no, evidence, msg):
        if ignored(ignore_rules, rule, rel):
            return
        same = [h for h in hits if h["rule"] == rule and h["file"] == rel]
        if len(same) >= MAX_HITS_PER_RULE:
            same[0]["suppressed"] = same[0].get("suppressed", 0) + 1
            return
        hits.append({"level": level, "rule": rule, "file": rel,
                     "line": line_no, "evidence": evidence, "msg": msg})

    for rel in files:
        path = Path(repo) / rel
        if not path.is_file():
            continue
        size = path.stat().st_size

        for level, rule, glob, msg in PATH_RULES:
            name = Path(rel).name
            if not fnmatch.fnmatch(name, glob):
                continue
            # .env.example / .env.sample 这类是给人看的模板，不算泄露
            if name.endswith((".example", ".sample", ".template", ".dist")):
                continue
            add(level, rule, rel, 0, name, msg)

        if size > BIG_FILE_BYTES:
            add(INFO, "BIG_FILE", rel, 0, f"{size/1024/1024:.1f} MB", "大文件")
        if size > MAX_SCAN_BYTES or looks_binary(path):
            skipped.append(rel)
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            skipped.append(rel)
            continue

        for line_no, line in enumerate(text.splitlines(), 1):
            if len(line) > 4000:
                line = line[:4000]
            for level, rule, pattern, msg in CONTENT_RULES:
                m = re.search(pattern, line)
                if not m:
                    continue
                val = m.group(1) if m.re.groups else m.group(0)
                if rule == "EMAIL" and EMAIL_ALLOW.search(val):
                    continue
                ev = mask(val) if rule in MASK_RULES else val
                add(level, rule, rel, line_no, ev, msg)
            if names and len(names) >= 2 and names in line:
                add(WARN, "REAL_NAME", rel, line_no, names,
                    "出现 git 配置里的真实姓名")
            for pat in extra:
                m = re.search(pat, line)
                if m:
                    add(WARN, "CUSTOM", rel, line_no, mask(m.group(0)),
                        f"自定义规则 {pat}")

    hits.sort(key=lambda h: ({BLOCK: 0, WARN: 1, INFO: 2}[h["level"]],
                             h["file"], h["line"]))
    return {"tracked": len(tracked), "untracked": len(untracked),
            "scanned": len(files), "skipped": skipped, "hits": hits}


def print_report(r: dict, repo: str) -> None:
    print("发布前安全扫描")
    print(f"  仓库   {repo}")
    print(f"  文件   {r['scanned']} 个（已跟踪 {r['tracked']} / "
          f"未跟踪未忽略 {r['untracked']}）")
    if r["skipped"]:
        print(f"  跳过   {len(r['skipped'])} 个（二进制或超过 2 MB）")

    if not r["hits"]:
        print("\n结果   干净，没有命中任何规则")
        return

    counts = {BLOCK: 0, WARN: 0, INFO: 0}
    for h in r["hits"]:
        counts[h["level"]] += 1

    print()
    for h in r["hits"]:
        loc = h["file"] if not h["line"] else f"{h['file']}:{h['line']}"
        print(f"[{h['level']:5}] {loc}")
        print(f"        规则  {h['rule']}  {h['msg']}")
        print(f"        证据  {h['evidence']}")
        if h.get("suppressed"):
            print(f"        还有  {h['suppressed']} 处同类命中未列出")
    print(f"\n结果   BLOCK {counts[BLOCK]} · WARN {counts[WARN]} · INFO {counts[INFO]}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="发布前安全扫描")
    ap.add_argument("--repo", default=".", help="仓库路径")
    ap.add_argument("--strict", action="store_true", help="WARN 也算失败")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--extra", action="append", default=[],
                    help="追加自定义正则（WARN 级），可重复")
    a = ap.parse_args(argv)

    repo = os.path.abspath(a.repo)
    if not (Path(repo) / ".git").exists():
        print(f"不是 git 仓库：{repo}", file=sys.stderr)
        return 1

    r = scan(repo, a.extra)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print_report(r, repo)

    if any(h["level"] == BLOCK for h in r["hits"]):
        return 2
    if a.strict and any(h["level"] == WARN for h in r["hits"]):
        return 2
    return 3 if r["hits"] else 0


if __name__ == "__main__":
    sys.exit(main())
