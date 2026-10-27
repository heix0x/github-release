# 排错对照表

按报错原文查。每条给出现象、原因、处理。

## 一、网络与代理

### `Failed to connect to github.com:443 over proxy 127.0.0.1`

**原因**：git 配了代理但代理没运行。

```bash
git config --list --show-origin | grep -i proxy
```

常见是 `http.https://github.com.proxy = http://127.0.0.1:7890`（Clash 默认端口）。

**处理**（三选一）：
1. 开代理软件
2. 临时绕过：`git -c http.https://github.com.proxy= push`
3. 改用 `python scripts/gh_push.py`，它走 api.github.com

**不要**直接删全局配置——那是用户有意设的，开了代理就该用。

### `CONNECT tunnel failed, response 502`

**原因**：配的代理不支持 HTTPS CONNECT 隧道（常见于只转发 HTTP 的内部代理）。

**处理**：换代理，或走 `gh_push.py` 的 API 通道。

### `Failed to connect to github.com port 443 after 21000 ms: Could not connect`

**原因**：直连超时，没有走任何代理。

**处理**：走 API（见 `api-fallback.md`），或配一个可用代理。

### 直连时通时不通

**原因**：国内访问 GitHub 的网络本身不稳定，不是配置问题。

**处理**：`gh_push.py` 会先试 git，失败再走 API，正好覆盖这种情况。不要反复手工重试。

---

## 二、认证与权限

### `取不到 GitHub 凭据`

**原因**：本机从没登录过 GitHub，凭据管理器里没有记录。

**处理**：让人手动完成一次登录——随便 `git push` 一个仓库触发弹窗，或 `gh auth login`。登录一次之后 `git credential fill` 才有东西可读。

### `403 Resource not accessible by personal access token`

**原因**：token 权限不够。创建 release、改 About 需要 `repo` scope。

**处理**：重新授权，勾上 `repo`（fine-grained token 需要 Contents: Read and write）。

### `401 Bad credentials`

**原因**：token 过期或被撤销。

**处理**：重新登录。Windows 上可以在「凭据管理器 → Windows 凭据」里删掉 `git:https://github.com` 再推一次。

### `凭据属于 A，但 remote 指向 B`

**原因**：用别人的 token 推自己的仓库，或反过来。

**处理**：确认账号对目标仓库有写权限，否则换 token 或换 remote。

---

## 三、推送冲突

### `! [rejected] main -> main (non-fast-forward)`

**原因**：远程有本地没有的提交。

**处理**：

```bash
git fetch origin
git log --oneline HEAD..origin/main    # 看远程多出什么
git rebase origin/main                 # 把你的提交接在后面
```

**不要**直接 `--force`——会覆盖别人的工作。确认只有自己在用这个仓库，才考虑 `--force-with-lease`。

### `fatal: refusing to merge unrelated histories`

**原因**：本地和远程是两个独立的提交树（各自 init 过）。

**处理**：确认要保留哪边，然后

```bash
git pull origin main --allow-unrelated-histories
```

或者用远程内容重建本地（会丢本地历史，先确认）。

### 推送成功但 `git status` 显示 ahead

**原因**：走 API 推的，本地 commit 和远程 commit 的 hash 不同，git 认为你还没推。

**处理**：`git fetch && git reset --hard origin/main` 对齐。内容是同步的，只是 hash 不一样。

---

## 四、Release 相关

### `422 Validation Failed` 建 release 时

**原因**：tag 已存在。

**处理**：`gh_release.py` 会自动复用已有 release。如果是要改内容，去网页上编辑，或先删 release 和 tag 再重发。

### 附件上传返回 201 但下载 404

**原因**：
- release 是 draft 状态，附件对外不可见
- 或者刚上传，CDN 还没同步（等几十秒）

**处理**：确认 `draft: false`；稍等重试。

### `browser_download_url` 打不开

**原因**：那个地址走 `github.com`，网络不通时必然失败。

**处理**：用 API 下载验证：

```python
GET /repos/{o}/{r}/releases/assets/{asset_id}
Accept: application/octet-stream
```

这只说明你的网络问题，不代表别人也下不了。

### 附件同名被跳过

**原因**：`gh_release.py` 检测到同名 asset 已存在，跳过上传。

**处理**：先在网页上删掉旧附件，再跑一次。或者发一个新版本号。

---

## 五、仓库配置

### `git add` 后发现不该提交的文件

```bash
git rm --cached <文件>
echo "<文件>" >> .gitignore
git commit -m "chore: 移除误提交的 <文件>"
```

**注意**：文件已经进了历史，从当前版本删掉不等于从历史删掉。真含密钥的话必须改历史（见 `rollback.md`）。

### 提交里混进了个人信息

```bash
git log -p | grep -n "真实姓名\|C:\\\\Users\|/Users/"
```

找到后按 `rollback.md` 的「清理历史中的敏感信息」处理。

### `.gitignore` 不生效

**原因**：文件已经被跟踪过了，`.gitignore` 只对未跟踪文件生效。

**处理**：`git rm --cached <文件>` 后再提交。

---

## 六、跨平台

### Windows 上中文文件名乱码

`.gitattributes` 加：

```
* text=auto eol=lf
```

同时确认 `git config core.quotepath false`，否则 `git status` 会把中文显示成 `\346\226\207`。

### 换行符导致整个文件显示为修改

**原因**：Windows 的 CRLF 和仓库的 LF 冲突。

**处理**：加 `.gitattributes` 强制 LF，然后 `git add --renormalize .`。
