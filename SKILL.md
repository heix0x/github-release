---
name: github-release
description: 在 GitHub 上完成从仓库初始化到正式发版的整套流程，覆盖远程仓库配置、提交与分支管理、版本号与更新日志、Release 打包发布、验证与回滚，并包含 git 推送失败时的 API 兜底方案。当需要新建 GitHub 仓库、把本地项目推上去、发版打 tag、上传 release 附件、设置仓库 About 与 topics、处理推送失败或回滚版本时使用。Use when: 发布到 GitHub, 发版, 打 tag, release, 推送仓库, 上传到 github, 版本发布, 回滚版本, github 仓库初始化。English: publish a project to GitHub end to end — create repo, push with API fallback when the network blocks git, semantic versioning, CHANGELOG, release assets, About and topics, verification, rollback.
agent_created: true
---

# GitHub 发布流程

从零到发布上线，按阶段执行。每个阶段都有验收标准，不通过就不要进下一阶段。

## 什么时候用

- 本地项目要第一次推到 GitHub
- 已有仓库要发一个新版本
- 推送失败（网络、代理、权限）需要排障或换路径
- 发错了版本要回滚

## 五条铁律

1. **先定稿文档，再打包发版。** 反例：打完包又改 README，导致 tag 指向的 commit 落后于 main，release 里的代码和仓库不一致。
2. **发布前工作区必须干净。** `git status --porcelain` 有输出就不许发版。
3. **tag 推上去就不动。** 发错了用新版本号重发，不要删 tag 重建——别人可能已经拉过了。
4. **附件必须验过。** 上传不等于可用：下载回来、解压、跑一次，才算发布完成。
5. **覆盖操作先确认。** `--force`、删 remote 分支、重置 history，执行前必须让人明确同意。

## 阶段 0：环境检查

跑脚本，不要手工猜：

```bash
python scripts/gh_auth.py [--repo <路径>]
```

它检查四项：git 提交身份、GitHub 凭据是否有效、remote 指向哪、github.com:443 直通不通。

**关键判断**：`直连 不通` 不代表不能发，`gh_push.py` 会自动改走 API。但要在回复里说明。

失败处理：
- 没配 git 身份 → `git config user.name` / `user.email`
- 取不到凭据 → 让人先手动完成一次 GitHub 登录（`git push` 弹窗，或 `gh auth login`）
- remote 不是 GitHub → `git remote set-url origin <url>`

## 阶段 1：初始化仓库与 remote

```bash
git init
git add -A
git commit -m "chore: 初始化 <项目名>"
git remote add origin https://github.com/<owner>/<repo>.git
git branch -M main
```

远程仓库必须先存在。两条路：

- **有 token**：`POST /user/repos`，body 里给 `name`、`description`、`private`（description 用英文，见下方「仓库元信息用英文」）
- **没 token**：让人在网页上建空仓库，**不要勾** README / .gitignore / LICENSE（会冲突）

### 必带的三份文件

| 文件 | 作用 |
|---|---|
| `.gitignore` | 排除 `__pycache__`、构建产物、抓取结果、本地凭据 |
| `LICENSE` | 没有明确要求时用 MIT |
| `README.md` | 面向使用者的入口文档 |

`.gitattributes` 建议加上，强制 LF：`* text=auto eol=lf`

### 提交前扫一遍个人信息

```bash
grep -rn "C:\\\\Users\|/Users/" --include="*.py" --include="*.md" .
```

代码注释里出现自己的真实姓名是最容易漏的泄露点，也要一起搜。

## 阶段 2：提交

### 信息写法

**一行，说清做了什么。** 用 conventional 前缀。

```
feat: 判题改为 RabbitMQ 异步，提交接口不再阻塞等判题
fix: 判题链路三处修正——幂等抢占、异常分类、编译错误不再被吞
docs: README 改为 AI 助手优先，命令降为备选
chore: 初始化 <项目名>（模块列表，许可）
```

**不要写**：分条列举改动、解释设计理由、总结"本次完成了什么"。

### 分支

- `main` 保持随时可发布
- 大改动开 `feat/<主题>`，合并前 rebase 到最新 main
- 不提交空提交凑数

### 推送

```bash
python scripts/gh_push.py [--repo <路径>] [--branch main]
```

先用 git，失败自动转 API。

- 遇到 `rejected` 且不是网络问题 → 远程有你本地没有的提交，**不要直接 --force**，先 `git fetch && git rebase origin/main`
- 走 API 成功后，本地 HEAD 和远程 hash 不同，网络恢复后执行 `git fetch && git reset --hard origin/main` 对齐

## 阶段 3：版本号与更新日志

### 语义化版本

| 位 | 什么时候加 |
|---|---|
| `v1.2.**3**` patch | 只修 bug，不改接口 |
| `v1.**3**.0` minor | 加功能，向后兼容 |
| `v**2**.0.0` major | 破坏性变更 |

### CHANGELOG.md

在仓库根放一份，`gh_release.py` 会自动按版本号摘取对应段落：

```markdown
## [1.2.0] - 2026-10-27

### 新增
- 支持离线安装

### 修复
- 修复 Windows 下路径解析错误
```

段落标题必须能匹配版本号（`## 1.2.0` 或 `## [1.2.0]` 都行）。

### 版本号落地位置

除了 tag，还要同步到这些地方（有的话）：

- `package.json` 的 `version`
- `pyproject.toml` / `setup.py`
- 代码里的 `__version__`
- README 里写死的版本号
- 打包脚本的默认值

**漏掉任何一处，下次别人装到的版本号就对不上。**

## README 写法（发版前必查）

README 第一屏必须回答两个问题：**怎么装**、**怎么用**。「它解决什么问题」很重要，但要排在后面——
读者在决定要不要用之前就关掉了。

模板在 `assets/readme-template.md`，改内容直接用。

**三条硬要求：**

1. **安装必须是第一个二级标题**，不是「为什么需要它」。
2. **安装给一句话**：读者能直接复制发给 AI 助手，不用自己拼路径、猜目录。
3. **用法写成「你说 → 它做」的对照表**，不是命令列表。人对命令有距离感，对「你说一句话」没有。

外加一条：**标题下面第一段必须是英文**（`**English:**` 开头），中文紧随其后。原因见下一节「仓库元信息用英文」。

参考做法的出处（热门 skill 项目都在这么写）：

- `awesome-claude-skills` 的 Usage 部分：`Deploy this to Vercel production → Uses vercel-cli skill`
- OneI 的 `One-prompt install`：一段话粘给 agent，它自己装

**反面教材**：开头三千字讲痛点，装法埋在第七节。这种 README 唯一的读者是作者自己。

## 仓库元信息用英文

GitHub 的搜索、topic 页面、趋势榜都按英文字面索引。中文 description 只有中文查询能匹配上，英文查询一条都命中不了。**项目做给谁看，就用谁的语言写 About。**

| 字段 | 语言 | 说明 |
|---|---|---|
| 仓库名 | 英文小写连字符 | 不用拼音，也不用中文 |
| `description`（About） | **英文** | 一句话，动词开头，说清做什么 |
| `topics` | **英文小写** | 优先挑已有 topic，自造词没人搜 |
| README 首段 | 英文一段 + 中文一段 | 英文段以 `**English:**` 开头 |
| commit / CHANGELOG / release 正文 | 中文 | 给人读，不参与检索 |

**description 一句话三段**：`<做什么> — <关键特征> — <它是什么>`。太短的只写第一段也行。

```
Scrape Chaoxing (XueXiTong) assignment pages into Markdown notes, and bulk-fill
answers back — a Playwright-based AI agent skill.
```

**topics 挑 6–10 个**：类别词（`ai-agent`、`skill`）+ 技术词（`playwright`、`python`）+ 领域词（`web-automation`）。GitHub 只接受小写字母、数字、连字符，中文和空格会被接口拒掉——`gh_release.py` 会预先剔除并提示。

`gh_release.py` 发现 description 里有中文会提醒一句。提醒不是限制，确实要中文就带着发。

## 阶段 4：发布

```bash
# 1. 定稿所有文档，提交并推送
git add -A && git commit -m "docs: 定稿 README"
python scripts/gh_push.py

# 2. 打包（项目有打包脚本就用，没有就手打 zip）
python pack.py --version 1.2.0

# 3. 建 release，传附件，顺手设 About（description 和 topics 用英文）
python scripts/gh_release.py --tag v1.2.0 \
  --asset dist/app-1.2.0.zip \
  --description "Do one thing well — a Playwright-based AI agent skill." \
  --topics ai-agent,skill,playwright,python
```

`gh_release.py` 会自动：建 tag 和 release、上传附件、改仓库简介、设话题、打印下载直链。

**正文优先级**：`--body` > `--body-file` > 从 `CHANGELOG.md` 按 tag 摘取。三者都没有会直接报错，不会发一个空 release。

**tag 已存在**时复用已有 release，不报错；但附件同名会跳过，改过内容要先在网页上删旧附件。

## 阶段 5：验证

发布完必须做这三步，缺一不可：

1. **附件真的能下载吗**——`browser_download_url` 走 github.com，网络不通时用 `GET /repos/{o}/{r}/releases/assets/{id}` 加 `Accept: application/octet-stream`
2. **解压后结构对吗**——顶层应该是一个目录，不是散开的文件
3. **跑一次项目自检**——`install.py` / `make test` / `npm test`

**只建 release 不验证，等于没发布。** HTTP 201 只说明文件收到了，不代表能下载、能跑。

验证通过后，把下载直链写进 README，方便直接分享。

## 常见问题

见 `references/troubleshooting.md`。高频的几条：

| 现象 | 原因 | 处理 |
|---|---|---|
| `Failed to connect ... over proxy` | git 配了代理但代理没开 | 查 `git config --get http.proxy`，或改用 `gh_push.py` |
| `CONNECT tunnel failed 502` | 代理不支持 HTTPS 隧道 | 同上，走 API |
| `rejected (non-fast-forward)` | 远程有新提交 | `git fetch && git rebase`，别急着 force |
| `403 Resource not accessible` | token 缺 repo 写权限 | 重新授权，勾 `repo` scope |

## 回滚

见 `references/rollback.md`。按场景分：撤销未推送的提交、撤销已推送的提交、撤回 release、删 tag、紧急回退 main。

## 脚本

| 脚本 | 用途 |
|---|---|
| `scripts/gh_auth.py` | 发布前检查：身份、凭据、remote、网络 |
| `scripts/gh_push.py` | 推送，git 失败自动转 API |
| `scripts/gh_release.py` | 建 release + 传附件 + 配 About |
| `scripts/_gh.py` | 公共模块：取 token、调 API、解析 remote |

`gh_push.py` 和 `gh_release.py` 都支持 `--dry-run`，正式动作前先跑一次看输出。

## 网络不通时的手工兜底

`gh_push.py` 内部已实现，原理与手工步骤见 `references/api-fallback.md`。
