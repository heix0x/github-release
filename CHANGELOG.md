# CHANGELOG

版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

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
