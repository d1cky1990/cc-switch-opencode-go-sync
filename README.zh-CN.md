# cc-switch-opencode-go-sync

> [English](README.md)

把 [OpenCode Go（Zen）](https://opencode.ai/zen) 的模型列表同步进
[cc-switch](https://github.com/farion1231/cc-switch) 的 Codex 供应商映射表，
以后 OpenCode 加模型、换模型（包括限时模型）都不用再逐条手工填写菜单显示名、
实际请求模型和上下文窗口了。

也可以当 AI agent 的 skill 用：本仓库就是按 skill 的布局组织的——根目录放
`SKILL.md`，脚本放 `scripts/`。

## 原理

1. 按 `base_url` 含 `opencode.ai/zen/go` 的特征找到 Codex 供应商（不写死供应商 id）。
2. 用 cc-switch 里已存的 key 调 `{base_url}/models`，拿到账号真实可见的模型 id
   清单做权威校验。key 只放内存——不打印、不落地。
3. 从 `https://models.dev/api.json` 的 `opencode-go` 条目（OpenCode 官方维护）
   读取显示名和上下文窗口。
4. 打印 diff 表格（`NEW` / `LIVE-ONLY` / `CTX` / `NAME` / `STALE`）给你确认，
   备份 cc-switch 数据库和 catalog，然后只写回 `modelCatalog.models` 数组。
   `auth` 和 `config` 原样不动。
5. 每次写入都按模型 id 字母排序，切换菜单找模型方便。

生效步骤：在 cc-switch 里重新点一下该供应商（或重启 cc-switch），然后**重启 Codex**
（`model_catalog_json` 只在启动时加载）。

## 环境要求

- Windows + Python 3（只用标准库，零依赖）
- cc-switch 里配好了 OpenCode Go（Zen）的 Codex 渠道

## 用法

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

## 窗口等价说明

`1000000 / 1024000 / 1048576` 视为同一“1M 档”（`256000 / 262144` 视为“256K 档”），
写法差异不提示，只处理跨档变化。两边都查不到的未知 id 窗口留空（安全的：
cc-switch 会回退到 128K，只会提前压缩、不会断粮）。

## 开源协议

MIT，见 [LICENSE](LICENSE)。
