# cc-switch-opencode-go-sync

> [English](README.md)

把 [OpenCode Go（Zen）](https://opencode.ai/zen) 的模型列表同步进
[cc-switch](https://github.com/farion1231/cc-switch) 的 Codex 供应商映射表，
以后 OpenCode 加模型、换模型（包括限时模型）都不用再逐条手工填写菜单显示名、
实际请求模型和上下文窗口了。

不用发布 npm 包，直接从 GitHub 一键安装：

```powershell
npx skills add d1cky1990/cc-switch-opencode-go-sync -g -y
```

---

## 普通用户视角：安装和使用（不用写代码）

### 1. 安装 skill（一次即可）

二选一：

**方式 A —— 一行命令安装（推荐）。** 适用于 Codex、Claude Code、OpenCode
等多种 agent；`-g` 表示装到全局，每个项目都能用：

```powershell
npx skills add d1cky1990/cc-switch-opencode-go-sync -g -y
```

只想给 Codex 用？

```powershell
npx skills add d1cky1990/cc-switch-opencode-go-sync -g -a codex -y
```

想先看看会装什么（什么都不改）？

```powershell
npx skills add d1cky1990/cc-switch-opencode-go-sync --list
```

**方式 B —— 手工 clone。** 把本仓库 clone 到你的 agent 找 skill 的地方
（比如 `<项目>/.agents/skills/` 或全局 skills 目录）：

```powershell
git clone https://github.com/d1cky1990/cc-switch-opencode-go-sync.git
```

以后更新 skill：

```powershell
npx skills update d1cky1990/cc-switch-opencode-go-sync -g -y
```

### 2. 使用：直接跟 AI 说话就行

脚本不用你亲自跑。在装好本 skill 的 agent 里说一句就行，例如：

- “帮我把 OpenCode Go 的新模型同步进 cc-switch”
- “OpenCode Go 好像上了限时模型，帮我同步一下”
- "Sync the new OpenCode Go models into cc-switch"

接下来会发生什么：

1. AI 拉取上游最新列表，给你看一张 **diff 表格**（新增模型 / 窗口修正 /
   显示名更新 / 疑似下架），每行都有推荐操作。
2. 你确认一下——回“按推荐来”就行，也可以逐行定（比如“下架的删掉”）。
3. AI 先备份 cc-switch 数据库和 catalog，只写回模型映射表，并告诉你生效方法：
   去 cc-switch 里重新点一下该供应商（或重启 cc-switch），然后**重启 Codex**
  （模型目录只在启动时加载）。

---

## 开发者 / AI 视角：原理和脚本用法

本仓库就是按 skill 的布局组织的：根目录 `SKILL.md`（agent 严格遵循的工作流）
加 `scripts/`（同步脚本）。

### 原理

1. 按 `base_url` 含 `opencode.ai/zen/go` 的特征找到 Codex 供应商（不写死供应商 id）。
2. 用 cc-switch 里已存的 key 调 `{base_url}/models`，拿到账号真实可见的模型 id
   清单做权威校验。key 只放内存——不打印、不落地。
3. 从 `https://models.dev/api.json` 的 `opencode-go` 条目（OpenCode 官方维护）
   读取显示名和上下文窗口。
4. 打印 diff 表格（`NEW` / `LIVE-ONLY` / `CTX` / `NAME` / `STALE`）给你确认，
   备份 cc-switch 数据库和 catalog，然后只写回 `modelCatalog.models` 数组。
   `auth` 和 `config` 原样不动。
5. 每次写入都按模型 id 字母排序，切换菜单找模型方便。

### 环境要求

- Windows + Python 3（只用标准库，零依赖）
- cc-switch 里配好了 OpenCode Go（Zen）的 Codex 渠道

### 脚本用法

先 dry-run（只读，什么都不改）：

```powershell
python scripts/sync_opencode_go.py
```

确认表格后加 `--apply`（先自动备份）：

```powershell
python scripts/sync_opencode_go.py --apply --skip-new ox-alpha-free --add-live deepseek-flash --drop-stale
```

| 参数 | 作用 |
|---|---|
| `--apply` | 写回 cc-switch 数据库（先备份数据库 + catalog） |
| `--keep-names` | 跳过显示名更新 |
| `--rename ID=NAME` | 强制指定一个显示名（可重复传，配合 `--keep-names` 用） |
| `--skip-new ID` | 这次不加某个 NEW 条目（可重复传） |
| `--add-live ID` | 把 LIVE-ONLY 的 id 加进来（显示名用 id 代替，窗口留空，可重复传） |
| `--set-window ID=NUM` | 强制指定窗口（可重复传） |
| `--drop-stale` | 删除 STALE 条目（默认保留标注） |
| `--no-live` | 跳过鉴权 live 校验（只按目录算 diff） |

### 窗口等价说明

`1000000 / 1024000 / 1048576` 视为同一“1M 档”（`256000 / 262144` 视为“256K 档”），
写法差异不提示，只处理跨档变化。两边都查不到的未知 id 窗口留空（安全的：
cc-switch 会回退到 128K，只会提前压缩、不会断粮）。

### 安全红线（`SKILL.md` 强制执行）

- key 只走“数据库 → 内存 → HTTPS Authorization 头”，永不经 CLI 参数、环境变量、
  文件、日志、报错信息传递。
- 默认 dry-run；每次写库先备份、必须先经用户确认；`auth` / `config` 字段和其他
  供应商绝不动。

## 开源协议

MIT，见 [LICENSE](LICENSE)。
