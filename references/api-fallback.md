# 网络不通时用 Git Data API 推送

## 什么时候需要

`git push` 报这几类错误，说明 git 的传输层走不通，但 `api.github.com` 往往还能通：

```
Failed to connect to github.com:443 over proxy 127.0.0.1
CONNECT tunnel failed, response 502
Failed to connect to github.com port 443 after 21000 ms
```

先确认 api.github.com 是通的：

```python
import urllib.request
urllib.request.urlopen("https://api.github.com/user", timeout=20)
```

通就走 API，不通就先解决网络。

## 原理

git 传输层走的是 `github.com:443`，而 GitHub 把仓库内容也暴露成了 REST 接口，走 `api.github.com`。两者域名不同，网络策略常常只挡前者。

Git 的对象模型对应四个 API：

| Git 对象 | API |
|---|---|
| 文件内容 | `POST /repos/{o}/{r}/git/blobs` |
| 目录树 | `POST /repos/{o}/{r}/git/trees` |
| 提交 | `POST /repos/{o}/{r}/git/commits` |
| 分支引用 | `PATCH /repos/{o}/{r}/git/refs/heads/{branch}` |

## 完整流程

### 1. 取 token

```python
import subprocess
p = subprocess.run(["git", "credential", "fill"],
                   input="protocol=https\nhost=github.com\n\n",
                   capture_output=True, text=True)
token = next((l.split("=", 1)[1] for l in p.stdout.splitlines()
              if l.startswith("password=")), None)
```

这是 git 的标准凭据接口，跨平台都能用，不读配置文件、不碰钥匙串。

### 2. 读远程当前 HEAD

```python
GET /repos/{o}/{r}/git/refs/heads/main
→ 200 {"object": {"sha": "09a5247..."}}
```

404 表示分支不存在（空仓库），此时建 commit 时不带 `parents`。

### 3. 逐个文件建 blob

```python
GET /repos/{o}/{r}/git/blobs
body: {"content": "<base64>", "encoding": "base64"}
```

文件列表用 `git ls-files` 拿——**只包含已跟踪的文件**，未 add 的不会进去，所以推送前必须先 commit。

### 4. 建 tree

```python
POST /repos/{o}/{r}/git/trees
body: {"tree": [
  {"path": "README.md", "mode": "100644", "type": "blob", "sha": "<blob sha>"},
  ...
]}
```

可执行文件用 `mode: "100755"`。

### 5. 建 commit

```python
POST /repos/{o}/{r}/git/commits
body: {"message": "...", "tree": "<tree sha>", "parents": ["<远程 HEAD>"]}
```

**不带 parents 就是 root commit**，会丢掉全部历史。除非确实要重建历史，否则一定带上。

### 6. 更新分支引用

```python
PATCH /repos/{o}/{r}/git/refs/heads/main
body: {"sha": "<commit sha>", "force": true}
```

`force: true` 才能覆盖已有分支。空仓库用 `POST /git/refs`。

## 现成的实现

`scripts/gh_push.py` 已经把上面整套封装好了，直接：

```bash
python scripts/gh_push.py --repo <路径>
```

它会先试 git，失败自动转 API，不需要手工分步。

## 限制

- **大文件慢**：每个文件一次请求，几十 MB 的二进制会很慢。超过 50 MB 用 Git LFS 或改走 git 协议
- **不带 submodule**：submodule 会变成空的占位，需要单独处理
- **不复制 tag**：tag 要另外 `POST /git/refs` 创建
- **commit 元数据不同**：author/committer 用 token 对应的账号，所以 hash 和本地一定不一样

## 推完之后怎么对齐本地

API 建的 commit 本地没有，`git log` 和远程对不上，下次 `git push` 会报 non-fast-forward。

网络恢复后执行：

```bash
git fetch origin
git reset --hard origin/main
```

`reset --hard` 会丢弃本地未推送的 commit，执行前确认 `git status` 干净、且本地内容已经通过 API 推上去了。

## 手工分步示例（排障用）

```bash
TOKEN=$(printf 'protocol=https\nhost=github.com\n\n' | git credential fill | grep '^password=' | cut -d= -f2)
OWNER=yourname; REPO=yourrepo

# 看远程 HEAD
curl -s -H "Authorization: token $TOKEN" \
  "https://api.github.com/repos/$OWNER/$REPO/git/refs/heads/main"
```

`gh_push.py` 里有完整的 Python 实现，比 curl 拼 JSON 可靠得多，优先用它。
