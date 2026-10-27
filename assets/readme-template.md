# <skill-name>

**English:** <One sentence: what this skill lets an agent do. Verb-first, concrete, no hype.>

<一句话中文：同一件事，给中文读者。>

## 安装

把这段直接发给你正在用的 AI 助手：

```
把 https://github.com/<owner>/<repo> 装到你的 skills 目录，
读一下它的 SKILL.md，装好告诉我
```

不用配置，不用改路径。装完下次说到相关的事，它自己会调用。

<details>
<summary>手动安装</summary>

```bash
git clone https://github.com/<owner>/<repo>.git
cp -r <repo> ~/.workbuddy/skills/<name>     # 或对应的客户端 skills 目录
```

如果客户端支持目录链接，更好的做法是链过去，改一次全端生效：

```bash
mklink /J "%USERPROFILE%\.workbuddy\skills\<name>" "<repo 路径>"
```
</details>

## 用法

装好之后直接说人话，不用记命令：

| 你说 | 它做 |
|---|---|
| 「<最常见的请求，贴近真实口语>」 | <具体动作> |
| 「<第二个典型请求>」 | <具体动作> |
| 「<第三个，最好是另一种场景>」 | <具体动作> |

<如果有需要精确指定的参数，在这里补一句，例如：>
> 想指定课程名、输出目录这类细节时，一句话带上就行：「……，课程是 XXX，放到 ./out」。

## 它解决什么

<为什么需要这个 skill。原来的做法哪里疼，一两句说清即可，不要展开成散文。>

<如果痛点能列表格，用表格，一眼看完：>

| 常见毛病 | 表现 | 后果 |
|---|---|---|
| <问题 1> | <具体表现> | <导致什么> |
| <问题 2> | <具体表现> | <导致什么> |

## 它怎么做的

<核心方法，3-5 条。让读者判断这个思路靠不靠谱，不需要讲实现细节。>

- **<方法 1>**：<一句话>
- **<方法 2>**：<一句话>

## 不适用的情况

<诚实划线。读者看到这里还有兴趣，说明真的合适。>

- <场景 1>：<原因>
- <场景 2>：<原因>

## 结构

```
<name>/
├── SKILL.md          触发条件与调用说明
├── scripts/          <有就写，没有删掉这行>
└── references/       <同上>
```

## License

MIT
