# github-release

**English:** Take a project from a local folder to a published GitHub release — repo setup, commits, semantic versioning, release assets, About and topics — including the path where `git push` simply won't connect.

把本地项目一路推到发版上线：建仓库、配 remote、打 tag、传附件、设 About，另加一条 git 推不上时的替代通道。

## 安装

把这段直接发给你正在用的 AI 助手：

```
把 https://github.com/heix0x/github-release 装到你的 skills 目录，
读一下它的 SKILL.md，装好告诉我
```

不用配置。需要 Python 3.9+，以及一份已登录 GitHub 的 git 凭据（本机存过就能直接用）。

<details>
<summary>手动安装</summary>

```bash
git clone https://github.com/heix0x/github-release.git
cp -r github-release ~/.workbuddy/skills/github-release   # 或对应客户端的 skills 目录
```

客户端支持目录链接时，链过去更好，改一次全端生效：

```powershell
New-Item -ItemType Junction -Path "$env:USERPROFILE\.workbuddy\skills\github-release" `
  -Target "D:\path\to\github-release"
```
</details>

## 用法

装好之后直接说人话，不用记命令：

| 你说 | 它做 |
|---|---|
| 「这个项目发到 GitHub 上，仓库叫 xxx」 | 查身份与凭据、扫个人信息残留、建仓库、推代码 |
| 「发个 v1.2.0」 | 校验版本号与 CHANGELOG、打 tag、传附件、设 About 和 topics，再下载回来验一遍 |
| 「push 一直连不上 github」 | 排查代理，自动转 Git Data API 推送，并说明本地与远程怎么对齐 |
| 「v1.2.0 发错了，撤回」 | 按场景处理：删 release / 删 tag / 回退 main，改写历史前先问你 |

## 它解决什么

发布本身不难，难的是**顺序**，以及**失败之后怎么办**。

| 常见毛病 | 表现 | 后果 |
|---|---|---|
| 代理配了但没开 | `Failed to connect ... over proxy 127.0.0.1:7890` | 以为网络挂了，反复重试 |
| 代理不支持 HTTPS 隧道 | `CONNECT tunnel failed 502` | 换一个代理再试，还是不通 |
| 打完包又改文档 | tag 指向的 commit 落后 main | release 里的代码和仓库不一致 |
| 只建 release 不验证 | 页面看着正常 | 附件 404，或者解压出来散一地 |

## 它怎么做的

- **五阶段闸门**：环境 → 初始化 → 提交 → 版本 → 发布 → 验证。每阶段有验收标准，不过不进下一阶段。
- **推送双通道**：先试 `git push`，失败自动改用 Git Data API——建 blob、建 tree、建 commit、移分支指针，绕开传输层。
- **元信息用英文**：About、topics、README 首段走英文。GitHub 搜索按英文字面索引，中文简介只有中文查询能匹配上。
- **发布必须验**：附件下载、解压结构、跑一次自检。HTTP 201 只说明文件收到了，不代表能下载、能跑。

## 不适用的情况

- **CI/CD 与自动化部署**：这里只管「发版」这一步，构建流水线和部署环境不在范围内。
- **多人协作的分支策略**：以单人主线为主，没有 PR 流程和 code review 规则。
- **组织级权限管理**：私有仓库的团队权限、保护分支规则，得在网页上配。

## 结构

```
github-release/
├── SKILL.md                触发条件、五阶段流程、五条铁律
├── references/
│   ├── api-fallback.md     API 推送的原理与手工步骤
│   ├── troubleshooting.md  按报错原文索引
│   └── rollback.md         七种回滚场景
├── scripts/
│   ├── gh_auth.py          发布前四查：身份、凭据、remote、网络
│   ├── gh_push.py          推送，git 失败自动转 API
│   ├── gh_release.py       建 release + 传附件 + 配 About
│   └── _gh.py              公共模块：取 token、调 API、解析 remote
├── assets/
│   └── readme-template.md  发版前的 README 对照模板
└── pack.py                 打 zip
```

## License

MIT
