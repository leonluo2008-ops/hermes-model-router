# Notion 调研档接入 hermes-model-router — 实施 Plan（v3 · 已暂停）

> 2026-09-07 · powerflow Phase 2 · 前置实测：2026-09-07 OmniRoute notion-web 通道四能力验证（工作区检索/读页/联网搜索/网页浏览全通过，交叉核验 v3.8.51 版本号吻合）
> **状态：任务已暂停（2026-09-07 用户拍板），实施未开始；plan 审查已通过，恢复时按 T0→T4 直接实施。存档说明见 `docs/reports/2026-09-07-notion-provider-监理报告.md`**
> **v2 修订**（plan_review round 1 对抗审查后）：修复 F1 致命（模型名索引碰撞）+ F2 严重（provider 上下文路由缺失），详见 §2a
> **v3 修订**（plan_review round 2 复审后）：修复 F3 严重（剥前缀矛盾——`notion-web/<model>` 本身就是 API 路由名，注册名=API 名全名直发，同 `jy/*` 先例，删除剥离逻辑）+ 3 项施工缺口显式化（default_system 注入点/清洗调用点/503 判定），详见 §2b

## 1. 背景与目标

**用户决策**：Notion 订阅经 OmniRoute 的 notion-web 通道是「优质大脑 + 联网搜索 + 网页浏览 + 用户 Notion 工作区上下文」四合一调研引擎，吃已付订阅额度。拍板接入 hermes-model-router 作专用调研档。

**实测事实基础**（全部本机验证过，标注来源）：
- 通道端点：`http://127.0.0.1:20128/v1`（OmniRoute），模型名 `notion-web/<model>`，key `OMNIROUTE_API_KEY`（与现有 omniroute provider 共享）
- 响应强制 SSE 流（即使请求 `stream:false`）→ call_model.py 已有 `_aggregate_sse` 兜底（call_model.py:157 `raw.lstrip().startswith("data:")` 分支），兼容
- 已实测有响应的模型：gemini-3.5-flash（四能力全通过）、deepseek-v4-flash、gpt-5.4、haiku-4.5
- 已知缺陷：①503 频发（"temporarily-unavailable, reset after 24s"，实测 30s 后重试即恢复）②响应 30-60s 偏慢 ③回包混思考泄漏（UUID 伪影行 + 推理独白）④`<mention-page url="X">标题</mention-page>` 页面引用标记 ⑤`[^URL]` 行内引用标记
- **能力边界**（不进 plan 范围但写进文档）：不能承载 agent 工具环（本地文件/终端够不着），Notion 服务端沙箱边界

## 2b. v3 修订（针对 round 2 复审报告）

**F3（严重）：D2"剥前缀发裸名"自相矛盾**——§1/§5.4 已载明 `notion-web/<model>` 就是 OmniRoute 的实际路由模型名（`/v1/models` 列出的 33 个即全名）；现有 omniroute 条目的 `jy/deepseek-v4-flash` 等就是全名注册全名直发的先例。剥前缀会把请求路由到错误通道或 404。
→ **修订 D2/T1**：注册名 = API 名 = `notion-web/<model>` 全名，**无任何剥离逻辑**。F1 的碰撞防护由前缀命名天然保证（`notion-web/gemini-3.5-flash` ≠ juxin 的 `gemini-3.5-flash`，是两个不同的注册键）。

**3 项施工缺口显式化**（round 2 轻微×3）：
1. **default_system 注入点**：main() 构建 messages 时——`system = args.system or cfg.get("default_system")`（cfg 取到才注入，其他 provider cfg 无此字段即 None，行为不变）；T2 单测加第⑤项：cfg 带 default_system 且无 --system → messages[0] 为 system 角色且内容匹配；有 --system → 覆盖生效
2. **clean_notion_output 调用点**：main() 中 `content = extract_content(response, cfg)` 之后——cfg 有 clean_output 时对 content 调用对应清洗函数再 print；T2 单测覆盖经 main 路径的清洗生效
3. **503 判定**：显式 `except HTTPError as e: if e.code == 503 and retry:` 走重试，其余 URLError 维持 sys.exit（HTTPError 是 URLError 子类，先接 HTTPError 再兜 URLError）；T2 单测 ②改为断言 503 触发重试、非 503（如 401）不重试直接退出

## 2a. v2 修订（针对 round 1 审查报告）

**F1（致命）：`_MODEL_TO_PROVIDER` 扁平索引碰撞**——call_model.py:74-77 后注册覆盖先注册，`gemini-3.5-flash` 直接进 notion 白名单会毁掉 juxin 通道。
→ **修订 D2**：notion 白名单模型名一律带 `notion-web/` 前缀注册（如 `notion-web/gemini-3.5-flash`），天然不与任何现有模型名冲突；`--list-models` 输出同名完整前缀。调用方式 `--model notion-web/gemini-3.5-flash`，实际发给 API 的 model 字段 = 去前缀后的裸名。

**F2（严重）：provider 上下文路由缺失**——call_model() 签名无 provider 信息，清洗/默认 prompt/503 重试无处挂载。且新发现根因：extract_content() :226-230 把 reasoning_content 前置拼进正文，是思考泄漏进入 stdout 的真正入口。
→ **修订 T1/T2**：
1. PROVIDERS 条目允许可选字段 `retry_503: true`、`default_system: str`、`clean_output: str`（函数名）
2. `resolve_provider()` 返回值扩为 `(provider_name, cfg, base_url, api_key)`，main() 把 cfg 传给 call_model() 和 extract_content()
3. `call_model()` 增加 `cfg: dict | None = None` 参数：cfg 有 `retry_503` 时 503 走重试循环（sleep 28s，上限 2 次），否则维持现行为直接 sys.exit——**现有 provider 行为零变化**
4. **思考泄漏根治在提取层**：extract_content() 增加分支——当 cfg 声明 `clean_output` 时，**不拼接 reasoning_content**（丢弃），content 直接返回；清洗函数 clean_notion_output() 只负责 UUID 伪影行 + mention-page 链接化 + 空行折叠（后处理）

**审查报告其余两条（中等）**：已核验，无需改设计——D2 白名单准入闸（T3 冒烟失败剔除）本身闭环；主 agent 独立复核已在本流程执行（本次 round-1 核验即实例），T6 报告后仍加主 agent 复核步骤。

## 2. 设计决策

| # | 决策 | 选择 | 理由 |
|---|---|---|---|
| D1 | provider 形态 | PROVIDERS 加独立 `"notion"` 条目（base_url/key_env 同 omniroute） | 需要挂 provider 级行为：清洗 + 503 重试 + 默认 system prompt；混进 omniroute 条目做不到 |
| D2 | 模型白名单 | **注册名 = API 名 = `notion-web/<model>` 全名直发，无剥离逻辑**（v3/F3 修订）：`notion-web/gemini-3.5-flash`（默认档）、`notion-web/deepseek-v4-flash`、`notion-web/gpt-5.4`、`notion-web/sonnet-5`、`notion-web/opus-4.8`。**T4 冒烟测试是准入闸，失败的剔出** | 前三个有实测响应记录；sonnet-5/opus-4.8 是订阅优质模型主力但未深测，冒烟过了才留；`notion-web/` 前缀本身就是 OmniRoute 路由名（同 `jy/*` 先例，§5.4），全名注册同时天然杜绝 _MODEL_TO_PROVIDER 碰撞（call_model.py:74-77，审查 F1/F3 已核验为真） |
| D3 | 输出清洗 `clean_notion_output()` | v1 只做三件：裸 UUID 伪影行删除、mention-page → `[标题](URL)`、3+ 空行折叠 | YAGNI；`[^URL]` 引用标记保留原样（含信息量，清洗收益低），文档说明 |
| D4 | 503 重试 | call_model() 内 HTTP 503 → sleep 28s → 重试，上限 2 次（仅 notion provider 启用，`retry_503: true`） | 实测 24s reset 窗口，28s 留裕量；其它 provider 行为不变 |
| D5 | 默认 system prompt | notion provider 配 `default_system`（直出结果+禁思考过程），用户传 `--system` 时覆盖 | 缓解思考泄漏，但不能依赖（llm-output-parsing 铁律：后处理必须） |
| D6 | 仓库 housekeeping | 先单独 commit 前会话遗留的 gemini-3.6-flash 补录（SKILL.md + call_model.py），再叠新 feature commit | 历史干净，遗留改动内容合理不需回滚 |
| D7 | `.hermes.md` 缺失 | 手写最小化项目 .hermes.md（继承 ~/.hermes.md 关键规则：禁 git add -A / 线性 push / 中文注释） | hermes-md-init skill 不存在（已查证 0 命中），铁律 2 要求仓库有 .hermes.md |
| D8 | 推送 | origin master 线性 push（现有领先 2 commit 一并推） | 该仓库 origin 是 GitHub（leonluo2008-ops/hermes-model-router），非 skills 仓，不受 Gitee 单平台约束 |

## 3. 任务分解

| # | 任务 | 验证 |
|---|---|---|
| T0 | 写 .hermes.md（D7）+ commit 遗留改动（D6） | `git log --oneline -2` 出现两条独立 commit |
| T1 | PROVIDERS 加 notion 条目（D1/D2 前缀白名单 + retry_503 + default_system + clean_output 字段）+ resolve_provider 返回 cfg（v2/F2 修订①②） | `--list-models` 列出 5 个 notion-web/* 模型；juxin 的 gemini-3.5-flash 仍解析到 juxin |
| T2 | call_model() 加 cfg 参数与 503 重试（v2/F2 修订③）+ extract_content() cfg 分支（不拼 reasoning）+ `clean_notion_output()`（D3，v2/F2 修订④） | 单测：①构造含 UUID 行/mention-page/多空行的样本 → 断言清洗输出 ②mock 503→200 序列 → 断言重试命中 ③mock 非 notion provider 无 cfg → 行为与现版一致 ④extract_content 带 clean_output 时不输出 reasoning 前缀。单测文件 `tests/test_notion.py`，`python3 tests/test_notion.py` 全绿 |
| T3 | T4 冒烟：5 模型各发一条真实调研短调用 | 每模型返回非空 content；失败者从白名单剔除并记录 |
| T4 | SKILL.md 更新：description、模型表加 notion 档、「调研档用法与边界」节（能做什么/不能做什么/慢/清洗说明/调用示例 `--model notion-web/gemini-3.5-flash`） | skill_view 回读，description 含 notion 触发词（"用notion查"、"notion调研"） |
| T5 | commit feature + push origin master（D8） | `git status` 干净；`git log origin/master..master` 为空 |
| T6 | code_review 子 agent 独立验证（qa-test-agent 工作流 A）+ 主 agent 复核其报告（qa-test-agent 铁律：不信自报） | 审查报告无 FAIL，且主 agent 抽查关键指控属实 |

## 4. 风险与边界

- **503 重试会拖长总耗时**：最坏 3 次尝试 ≈ 2-3 分钟，脚本 timeout 已是 300s 够用；文档标注"调研档是异步任务，不当实时链路用"
- **清洗是启发式**：思考独白无法可靠剥离（v1 不做），文档明示"回包可能带推理残留，程序化消费需自查"
- **sonnet-5/opus-4.8 若冒烟失败**：剔出白名单不阻塞交付，核心默认档 gemini-3.5-flash 已四能力实测
- **回滚**：纯 git revert 两个 commit 即可，无外部状态变更（不动 OmniRoute 配置、不动 Hermes config）

## 5. 已核证事实清单（供审查 agent 直接采信，不必重验）

1. 仓库真身 `/home/luo/Github/hermes-model-router`，`~/.hermes/skills/hermes-model-router` 是软链（8月18日建）
2. master 领先 origin/master 2 commit，未提交改动 = SKILL.md（2行）+ call_model.py（1行 gemini-3.6-flash）
3. call_model.py 已有 SSE 聚合兜底（:157）与 key_file/env 双路径 key 解析（:100-120）
4. notion-web 模型名格式 `notion-web/<model>`，`/v1/models` 实测 33 个可用
5. HTTPError 是 URLError 子类，现有 except URLError 能接住 503，但当前直接 sys.exit（需改为可重试路径）
6. delegation.model = gemini-3.6-flash（≠主力 glm-5.3-flash），plan_review 跨模型成立
