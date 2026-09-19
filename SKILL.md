---
name: cc-switch-opencode-go-sync
description: Sync OpenCode Go (Zen) model list into the cc-switch Codex provider. Use when the user says models changed, new or limited-time models appeared, or asks to sync/update OpenCode models in cc-switch or Codex.
---

# OpenCode Go 模型同步

把 OpenCode Go（Zen）上游的模型列表同步进 cc-switch 里 Codex 渠道 `OpenCode Go` 供应商的模型映射表，省掉逐条手工填写菜单显示名、实际请求模型、上下文窗口。

## 数据来源与字段映射

- 上游目录：`https://models.dev/api.json` 的 `opencode-go` 条目（OpenCode 官方维护）。
  - `id` → 实际请求模型（`model`）
  - `name` → 菜单显示名（`displayName`）
  - `limit.context` → 上下文窗口（`contextWindow`）
- 权威校验（可选但推荐）：用该供应商的 key 调 `{base_url}/models`（OpenAI 兼容接口），确认账号真实可见的 id 清单。限时模型可能不在目录里、也可能目录里有但账号不可见，两边对不上的一律标出来给人看，不擅自决定。

## 工作流（严格按顺序）

1. **定位供应商**：读 `~/.cc-switch/cc-switch.db` 的 `providers` 表，按 `app_type = codex` 且配置里 base_url 含 `opencode.ai/zen/go` 匹配。不要写死 provider id。
2. **备份**：写库前先备份 `cc-switch.db`（放到 `~/.cc-switch/backups/`，沿用 `db_backup_YYYYMMDD_HHMMSS.db` 命名）和 `~/.codex/cc-switch-model-catalog.json`。
3. **拉取并算 diff**：跑 `scripts/sync_opencode_go.py`（默认 dry-run，只读不写），输出四类：
   - `NEW`：上游有、本地无，默认加入；
   - `STALE`：本地有、上游无（如 `hy3-preview`），默认保留并标注，不删除；
   - `CTX`：窗口跨档差异，默认按上游改；
   - `NAME`：显示名差异（如 `DeepSeek V4 Pro (New)` 后缀），默认跟随上游。
4. **确认**：把 diff 按下表完整呈现给用户（不要只贴脚本 raw 输出），`--apply` 写入前必须有用户明确确认。用户回复“按推荐来”即按推荐列执行，或逐行指定（如“2 也加上，8 全跟”）。

   | # | 模型 | 差异类型 | 现状 → 变更后 | 你的选项 | 我的推荐 |
   |---|---|---|---|---|---|
   - 差异类型含：新增 / 新增（账号 live 不可见）/ Live 独有（疑似限时模型）/ 窗口修正 / 显示名补名 / 显示名风格 churn / STALE（疑似下架）。
   - 用户一句话可改默认动作（例如“下架的删掉”“ox 那个窗口按 1M 填”）。

5. **写入**：只改该供应商 `settings_config` 里 `modelCatalog.models` 数组，`auth`（key）和 `config` 文本原样保留。
6. **生效提醒**：改完必须告诉用户——去 cc-switch 里重新点一下该供应商（或重启 cc-switch）让它重新投影 catalog，然后**重启 Codex**（`model_catalog_json` 只在启动时加载）。

## 固定决策规则（已和用户对齐，不要再问）

- `1000000 / 1024000 / 1048576` 视为同一“1M 档”，`256000 / 262144` 视为同一“256K 档”，档内写法差异不动，只处理跨档差异。
- 上游和目录都查不到的未知模型 id：`displayName` 用 id 代替，`contextWindow` 留空并标 `NEW`，diff 里附同系列参考窗口。留空是安全的（cc-switch 会回退到 128K，只会提前压缩、不会断粮）；窗口填大反而可能让请求被上游拒绝。
- `live /v1/models` 与目录对不上的 id，只警告、不自动增删。
- 当前 `config.toml` 正在用的模型若被标 STALE，只警告，绝不自动切换。
- 首版范围：只管 Codex + OpenCode Go。匹配逻辑保持可扩展，后续加别家供应商时再说。

## 安全红线

- key 只从库里读、只放内存（路径：DB → 内存 → HTTPS Authorization header），**永不经 CLI 参数、环境变量、文件、日志、报错信息传递**。不要改用环境变量方案：那会在注册表/shell profile 里多存一份明文 key，容易被 `echo` 进历史记录，还会在 cc-switch 里换 key 后过期——以 DB 为唯一来源，暴露面最小且永远不会过期。
- 备份文件（`~/.cc-switch/backups/` 下的 db 备份和 catalog `.bak`）与 live DB 同等敏感，里面同样含 key。这是 cc-switch 本身的存放方式，工具不新增暴露面；不要把备份拷到别处。
- 异常和报错只允许含 URL 与状态码，不 dump 任何变量；diff 输出与聊天记录里绝不出现 key（最多只说“key 存在，已隐藏”）。
- 默认 dry-run；任何写库操作必须先备份、必须先经用户确认。
- 绝不碰 `auth` 和 `config` 字段；绝不改其他供应商；绝不直接手改 `cc-switch-model-catalog.json`（那是投影产物，会被覆盖）。

## Diff 之外的两类输出和常用 flags

- `LIVE-ONLY`：账号 live 名单里有、目录里没有的 id（多半是限时模型）。默认只报告不写；用户说加时，以 `displayName = id`、窗口留空加入。
- `--keep-names`：跳过显示名改名（上游偶尔会做连字符化改名，如 GLM 5 改成 GLM-5，这种纯风格 churn 可跳过；实质补名如 muse-spark 建议保留）。
- `--rename ID=NAME`：只改指定的显示名（配合 `--keep-names` 可实现“只补实质改名，跳过风格 churn”）。
- `--skip-new ID`：这次不加某个 NEW 条目（例如账号 live 不可见的）。
- `--add-live ID`：把 LIVE-ONLY 的 id 加进来（显示名用 id 代替，窗口留空）。
- `--set-window ID=NUM`：给某个 id 强制指定窗口（可重复传）。
- `--drop-stale`：删除 STALE 条目（默认保留标注）。
- `--no-live`：跳过鉴权 live 校验（key 不可用或离线时用，此时 NEW/STALE 只按目录算）。
- 写入时一律按 `model` id 字母顺序（大小写不敏感）排序后保存；纯顺序变化不在 diff 里单独列项，每次 `--apply` 自动归一化。
