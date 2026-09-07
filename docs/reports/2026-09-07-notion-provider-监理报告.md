# Notion 调研档接入 hermes-model-router — 监理报告（任务终止存档）

> 2026-09-07 · 状态：**已暂停，实施未开始** · 用户拍板：停止投入，转做正事
> 恢复入口：本报告 + `docs/plans/2026-09-07-notion-provider-plan.md`（v3，可直接作实施蓝本）+ `docs/reviews/` 复审原文

## 1. 任务是什么

把 OmniRoute notion-web 通道（Notion AI 订阅的模型，经本地网关 `127.0.0.1:20128`）注册为 hermes-model-router 的独立 provider，使 CLI 可直接 `--model notion-web/gemini-3.5-flash` 调用。用途：Notion 通道模型被服务端 agent 脚手架锁死、只能当纯文本模型用（写作/审读/评审），本任务让它能被程序化批量调用。

## 2. 已完成（有实测背书）

- **通道四能力实测**（2026-09-07）：工作区检索 / 读页 / 联网搜索 / 网页浏览 全通过，交叉核验 Notion v3.8.51 版本号吻合
- `/v1/models` 实测 33 个 `notion-web/*` 模型可用
- 已知缺陷清单（写入 plan §1）：503 频发（约 24s reset）、响应 30-60s 偏慢、思考泄漏（UUID 伪影行 + 推理独白）、`<mention-page>` / `[^URL]` 标记
- **能力边界**：不能承载 agent 工具环（本地文件/终端够不着，Notion 服务端沙箱）
- **plan 三轮迭代**：v1 初稿 → v2（修 round-1 审查 F1/F2）→ v3（修 round-2 复审 F3 + 3 项施工缺口），终态为"审查通过、可实施"

## 3. 审查结论（两轮对抗审查）

### round 1 — qa-test-agent plan_review（结论经本人读码独立核验为真）

| 编号 | 级别 | 内容 | v2 处置 |
|---|---|---|---|
| F1 | 致命 | `_MODEL_TO_PROVIDER` 扁平反向索引（call_model.py:74-77）同名模型后注册覆盖先注册——裸名 `gemini-3.5-flash` 进 notion 白名单会覆盖 juxin 注册，毁掉 juxin 通道 | notion-web/ 前缀命名，天然异键 |
| F2 | 严重 | `call_model()` / `extract_content()` 无 provider 上下文，provider 级行为（清洗/默认 prompt/重试）无处挂；深层根因：extract_content 会把 reasoning_content 拼进正文，纯后处理治标不治本 | resolve_provider 返回 cfg 传递链 + PROVIDERS 可选字段 retry_503 / default_system / clean_output |

### round 2 — glm-5.2 直连复审（delegation 后端降级改道，详见 §6）

| 编号 | 级别 | 内容 | v3 处置 |
|---|---|---|---|
| F3 | 严重 | v2 的"剥前缀发裸名"自相矛盾——`notion-web/<model>` 本身就是 OmniRoute 实际路由名（`/v1/models` 列出的即全名，同 `jy/*` 先例），剥了会路由错或 404 | 注册名 = API 名 = 全名直发，零剥离逻辑 |
| 轻微×3 | 施工缺口 | default_system 注入点未指派、clean_notion_output 调用点未指派、503 判定未显式用 HTTPError.code | 全部落 plan §2b，含对应单测项 |

## 4. 当前状态（git 现场）

- `scripts/call_model.py` / `SKILL.md` 有**遗留改动**（juxin 白名单加 gemini-3.6-flash + SKILL.md 描述同步）——属此前工作的收尾，与本任务无关，已单独 commit
- **本任务代码零改动**（停在 plan 审查阶段，实施未开始）——无回滚需求
- 全部文档存档于 `docs/`：plan v3 + 本报告 + round-2 复审原文

## 5. 若日后恢复

按 plan v3 任务表 T0→T4 顺序执行即可。T0（.hermes.md 检查 + 遗留 commit）已在本次存档中完成；T4 冒烟测试是模型白名单准入闸，失败的模型剔出。

## 6. 过程中的基建观察（非本任务范围，记录不处理）

- delegation 后端 `gemini-3.6-flash @ juxin` 两次 480s 响应超时 + 输出推理独白且答非所问（降级态，transient；直连探测通道本身存活）
- OmniRoute 本地请求队列 `maxWaitMs=15s` 排队饱和 503（deepseek-v4-pro）——OmniRoute 的 queue budget 而非上游超时，如需解在 Settings → Resilience 调大
- 审查改道记录：delegation（gemini-3.6-flash）超时 ×2 → jy/deepseek-v4-pro 队列 503 → glm-5.2 直连（无文件系统，改内嵌文件 prompt）成功产出复审
