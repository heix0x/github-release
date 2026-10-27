# CHANGELOG

版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.1.0] - 2026-10-27

### 新增

- `scripts/gh_scan.py`：发布前安全扫描，扫「即将被 `git add -A` 收进去的全部文件」——已跟踪的，加上未跟踪且没被 `.gitignore` 排除的
- 三级判定：BLOCK（私钥块、AWS/GitHub/GitLab/Slack/OpenAI/Google/Stripe 密钥格式）、WARN（密码字面量、带用户名的绝对路径、邮箱/身份证/手机号、真实姓名、下载即执行、`eval` 套输入、`os.system` 拼 f-string、敏感文件名）、INFO（大文件、数据库）
- 证据打码（`AKIA***MPLE`），避免扫描日志本身成为泄露载体
- `.ghscanignore`：按「规则名 + 路径 glob」豁免，不提供按内容豁免
- `--strict` 让 WARN 也算失败；`--json` 给机器读；`--extra` 追加自定义正则

### 流程

- 新增阶段 1.5「发布前安全门」，卡在 `git add -A` 之前
- 阶段 4 发布前再扫一遍：阶段 1.5 之后可能又加过文件，API 推送会把 `git ls-files` 整个重发
- 铁律从五条变六条，新增「BLOCK 不许带着推」
- 阶段 1 原来那条只匹配 `*.py` / `*.md` 两种扩展名的 `grep`，改为调用 `gh_scan.py`

### 说明

不判定代码是否恶意。代码意图不可判，只标记危险模式，由人确认。

## [1.0.0] - 2026-10-27

首个版本。

### 流程

- 五阶段闸门：环境检查 → 初始化 → 提交 → 版本 → 发布 → 验证，每阶段带验收标准
- 五条铁律：先定稿再打包、发布前工作区干净、tag 不动、附件必验、覆盖操作先确认

### 脚本

- `gh_auth.py`：发布前四查——git 身份、GitHub 凭据、remote、直连连通性
- `gh_push.py`：先试 `git push`，失败自动转 Git Data API 推送
- `gh_release.py`：建 tag 与 release、上传附件、设置 About 与 topics，可从 CHANGELOG 自动摘正文
- `pack.py`：打 zip 分发

### 约定

- 仓库 About 与 topics 用英文：GitHub 搜索按英文字面索引，中文简介只有中文查询能匹配
- `gh_release.py` 会提示简介里的中文，并剔除不合规的 topic
- README 首段中英各一段，安装放在第一个二级标题

### 文档

- `references/api-fallback.md`：API 推送原理与手工步骤
- `references/troubleshooting.md`：按报错原文索引
- `references/rollback.md`：七种回滚场景
