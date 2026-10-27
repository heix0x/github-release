# 回滚手册

按场景查。每条都标了「是否改写历史」和「是否需要 force push」——这两点决定影响范围。

## 场景速查

| 场景 | 命令 | 改写历史 | 需 force |
|---|---|---|---|
| 撤销本地未提交的改动 | `git restore` / `git checkout --` | 否 | 否 |
| 撤销本地已提交但未推送 | `git reset` | 是（仅本地） | 否 |
| 撤销已推送的提交 | `git revert` | 否 | 否 |
| 紧急回退 main 到旧版本 | `git reset --hard` + force | 是 | **是** |
| 撤回 release | 网页删除 或 `DELETE /releases/{id}` | 否 | 否 |
| 删除 tag | `git push origin :refs/tags/<tag>` | 否 | 否 |
| 清理历史中的敏感信息 | `filter-repo` | 是 | **是** |

**原则**：能用 `revert` 就不要 `reset`，能用新提交解决就不要改写历史。

---

## 一、撤销未提交的改动

```bash
git restore <文件>              # 丢弃工作区改动
git restore --staged <文件>     # 取消暂存，保留改动
git stash                       # 暂时收起来，之后能 stash pop
```

**不可逆**：`git restore` 丢弃的改动找不回来。

---

## 二、撤销已提交、还没推送

```bash
git reset --soft HEAD~1     # 撤销提交，改动留在暂存区
git reset --mixed HEAD~1    # 撤销提交，改动留在工作区（默认）
git reset --hard HEAD~1     # 撤销提交并丢弃改动（危险）
```

只想改提交信息的话：

```bash
git commit --amend -m "新信息"
```

**已经推送过的提交不要用 `--amend`**，会产生分叉，下一个人拉取会冲突。

---

## 三、撤销已推送的提交

**用 `revert`，不要用 `reset`。** `reset` 需要 force push，会打断所有人的本地仓库。

```bash
git revert <commit-sha>          # 生成一个反向提交
git revert <sha1>^..<sha2>       # 撤销一段连续提交
```

撤销 merge 提交要指定主线：

```bash
git revert -m 1 <merge-sha>
```

`-m 1` 表示保留第一父提交（通常是主干）的内容。

---

## 四、紧急回退 main

**只在自己独占仓库时用。** 有协作者的话走 `revert`。

```bash
git log --oneline -10                    # 找到要回退到的点
git reset --hard <good-sha>
git push --force-with-lease origin main
```

`--force-with-lease` 比 `--force` 安全：远程在你上次 fetch 之后如果又变了，它会拒绝推送，防止覆盖别人的提交。

**回退前先打一个备份 tag**：

```bash
git tag backup-before-rollback
git push origin backup-before-rollback
```

出问题还能回来。

---

## 五、撤回 release

### 只删 release，保留 tag

```python
DELETE /repos/{owner}/{repo}/releases/{release_id}
```

网页上也可以：Release 页面 → Edit → Delete。

### 连 tag 一起删

```bash
git push origin :refs/tags/v1.2.0     # 删远程 tag
git tag -d v1.2.0                      # 删本地 tag
```

API 方式：`DELETE /repos/{o}/{r}/git/refs/tags/v1.2.0`

**注意**：已经有人拉过这个 tag 的话，删了会造成困惑。宁可发 `v1.2.1` 说明「撤回 v1.2.0」。

### 把 release 改成草稿下线

```python
PATCH /repos/{o}/{r}/releases/{id}
body: {"draft": true}
```

比删除温和，随时能再发布。

---

## 六、清理历史中的敏感信息

**文件里泄露了密钥、密码、真实姓名**，单纯删文件没用——历史里还在。

```bash
pip install git-filter-repo
git filter-repo --path <敏感文件> --invert-paths
```

或者替换内容：

```bash
git filter-repo --replace-text replacements.txt
```

`replacements.txt` 格式：

```
真实姓名==>REDACTED
sk-abc123==>REDACTED
```

**之后必须**：

1. `git push --force --all`
2. `git push --force --tags`
3. **立即吊销泄露的密钥**——历史清理不等于密钥安全，它可能已经被抓取过了
4. 通知所有协作者重新 clone（他们的本地还留着旧历史）

**这一步风险最高**，执行前确认：仓库是否公开过、是否有 fork、是否有人已经拉取。

---

## 七、回滚后的收尾清单

- [ ] 新版本号更新到所有位置（`package.json` / `__version__` / README）
- [ ] CHANGELOG 补充回滚说明
- [ ] 如果撤回的是 release，在仓库里留一条说明，别让人以为是自己网络问题
- [ ] 如果改写历史，通知所有协作者重新 clone
- [ ] 如果泄露过密钥，先吊销再清理，顺序不能反
