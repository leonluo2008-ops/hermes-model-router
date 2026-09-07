# plan_review round 2 复审原文（存档）

> 2026-09-07 · 审查员：glm-5.2（ZAI 直连；delegation 后端降级改道，见监理报告 §6）
> 审查对象：docs/plans/2026-09-07-notion-provider-plan.md v2 · 内嵌文件 prompt（模型无文件系统）
> 结论：**需修改后通过** —— F3 严重（剥前缀矛盾）+ 轻微×3；v3 已逐条修复
> 以下为模型输出原文（含推理过程，未删改，保留作证据）：

---

Let me review this plan v2 carefully.

The task: Review the plan v2's §2a revisions against round 1 findings (F1 fatal: _MODEL_TO_PROVIDER flat dict collision; F2 severe: no provider context in call_model/extract_content). Review points:
① Does the prefix scheme eliminate collisions without new pitfalls?
② Is the cfg passing chain feasible in the existing code structure?
③ cfg=None backward compatibility (existing 5 providers unchanged)?
④ Does v2 introduce new problems?

Let me analyze:

**① Prefix scheme analysis:**

Current PROVIDERS registry (call_model.py lines ~41-83): models like "gemini-3.5-flash" (juxin), "jy/deepseek-v4-flash" (omniroute), "qwen3.8" (omniroute), etc.

_MODEL_TO_PROVIDER is built at lines 74-77 (in the actual file, it's after PROVIDERS dict — the loop `for provider_name, cfg in PROVIDERS.items(): for model in cfg["models"]: _MODEL_TO_PROVIDER[model] = provider_name`). Adding "notion-web/gemini-3.5-flash" etc. — these prefixed names don't collide with existing model names ("gemini-3.5-flash" vs "notion-web/gemini-3.5-flash" are different keys). So F1 is resolved.

New pitfalls to check:
1. **Sending the bare name to API**: plan says "实际发给 API 的 model 字段 = 去前缀后的裸名" — strip prefix when sending. Where does stripping happen? The plan says resolve_provider returns (provider_name, cfg, base_url, api_key). But who strips the prefix? Not explicitly stated! main() calls call_model(model=args.model, ...) — if main passes args.model directly, the "notion-web/gemini-3.5-flash" string would be sent to API. The plan doesn't specify where prefix-stripping occurs (in resolve_provider? in call_model via cfg? in main?). This is a gap — the plan mentions stripping but doesn't assign it to a specific task/task-step. Actually T1 says "PROVIDERS 加 notion 条目 + resolve_provider 返回 cfg"; T2 says "call_model() 加 cfg 参数与 503 重试". Neither explicitly mentions prefix stripping logic. This is a moderate issue — the implementation detail is unassigned. Hmm, but is it fatal? It's a plan, so missing explicit assignment could cause implementation to miss it. I'd flag it as 中 (medium) or 轻微. Let me check: §2a D2 says "发 API 时剥前缀" — so the intent exists but the mechanism/location is unspecified. Also, could stripping be generic? E.g., strip "notion-web/" prefix. Or better: cfg could have a "strip_prefix" field, or resolve_provider could return the api-facing model name. The plan should specify: resolve_provider returns api_model or call_model checks cfg.get("model_prefix"). This is a real gap worth flagging.

2. **Potential collision within notion prefix scheme itself**: If two notion models same bare name — no, they're distinct.

3. What about omniroute's existing models with "jy/" prefix? "notion-web/..." doesn't collide with "jy/..." or "jxgpt/...". Fine.

4. Wait — one subtle issue: the OmniRoute gateway uses model name "notion-web/<model>" — i.e., the prefix IS the actual API model name! Look at the plan: "通道端点：`http://127.0.0.1:20128/v1`（OmniRoute），模型名 `notion-web/<model>`". So the actual API expects the model field to be "notion-web/gemini-3.5-flash"! But then §2a D2 says "实际发给 API 的 model 字段 = 去前缀后的裸名" — stripping the prefix and sending bare "gemini-3.5-flash" to OmniRoute endpoint. That contradicts the earlier statement that the channel's model name is `notion-web/<model>`!

Let me re-read: "通道端点：`http://127.0.0.1:20128/v1`（OmniRoute），模型名 `notion-web/<model>`" — this says the model name for the notion channel is `notion-web/<model>`. And "已实测有响应的模型：gemini-3.5-flash（四能力全通过）" — meaning the <model> part. So when testing, they presumably called with model="notion-web/gemini-3.5-flash" via OmniRoute. So the API expects the FULL prefixed name "notion-web/gemini-3.5-flash", not the bare name!

If D2 strips the prefix and sends bare "gemini-3.5-flash" to OmniRoute's /v1/chat/completions, that would route to... probably the regular channel, not the notion-web channel! Or fail. This is a contradiction in the plan: §1 says the channel model name is `notion-web/<model>`, but §2a D2 says send the bare name after stripping the prefix.

Hmm wait, let me re-read D2 more carefully: "调用方式 `--model notion-web/gemini-3.5-flash`，实际发给 API 的 model 字段 = 去前缀后的裸名。" Yes, it says strip prefix when sending to API.

But §1 background says the notion channel via OmniRoute has model name `notion-web/<model>`. And §5 fact 4: "notion-web 模型名格式 `notion-web/<model>`，`/v1/models` 实测 33 个可用" — this strongly implies the API-facing model names ARE `notion-web/<model>` (33 such models listed in /v1/models).

So if the implementation strips the prefix before sending, the API call would send "gemini-3.5-flash" — which is not a notion-web channel model. This would break the feature entirely. Unless the plan intends "剥前缀" to mean stripping... hmm, but that's the only reading. This is a serious contradiction — potentially fatal for T3 smoke test (would fail, and per the smoke gate logic, models would be wrongly excluded). Actually the smoke test would catch it, but the plan's design decision itself is wrong/contradictory.

Wait, but maybe I'm misreading. Maybe the registration name adds an ADDITIONAL prefix beyond what API expects? The registered name is "notion-web/gemini-3.5-flash" and the API expects "notion-web/gemini-3.5-flash" too — in that case NO stripping is needed at all! The plan's stripping instruction is not only unnecessary but actively harmful. Either way, D2's "发 API 时剥前缀" contradicts facts in §1 and §5.4.

This is the biggest find: **F1-new (严重/致命): D2 prefix-stripping contradicts §1/§5.4 facts**. The API expects the full `notion-web/<model>` name; stripping would send a bare name that either routes elsewhere or 404s. Since registered name == API name, stripping is unnecessary; the fix is "don't strip" (or the plan author misunderstood). Severity: 严重 (would cause smoke test failures / misrouting), but caught by T3 smoke gate? The smoke gate would fail all 5 models and remove them all, blocking delivery — the plan says failure removes from whitelist but that would gut the feature. So it's a design bug that must be fixed before implementation. I'd call it 严重.

Hmm, wait. Let me think again. Could OmniRoute accept both? Unknown. The safest reading: the plan's own stated facts (§1: 模型名 `notion-web/<model>`; §5.4) indicate the API model name includes the prefix. D2 says strip. Contradiction stands. Flag as 严重.

Actually, one more consideration: maybe the plan intends registered name "notion-web/gemini-3.5-flash" and API name... let me look at D2 once more: "notion 白名单模型名一律带 `notion-web/` 前缀注册（如 `notion-web/gemini-3.5-flash`）...调用方式 `--model notion-web/gemini-3.5-flash`，实际发给 API 的 model 字段 = 去前缀后的裸名。" Definitely stripping. Contradiction with §5 fact 4. Flag it.

**② cfg passing chain feasibility:**

Current: `resolve_provider(model) -> (provider_name, base_url, api_key)`, main() unpacks and calls call_model(base_url, api_key, model, messages, ...) then extract_content(response).

Plan: resolve_provider returns (provider_name, cfg, base_url, api_key); main passes cfg to call_model() and extract_content(). Feasibility issues:

1. resolve_provider has TWO return statements (key_file path at line ~135 and env path at line ~155, plus the final return). Expanding return tuple requires changing all three return points — trivial but worth noting? Minor.

2. cfg contains models list etc. — passing full cfg dict is fine. But note: cfg values like api key are NOT in cfg (key_env/key_file are). Fine.

3. call_model(cfg: dict | None = None) — added after existing params; backward compatible for positional/keyword calls. main() is the only caller. Fine.

4. extract_content(response, cfg=None) — similarly fine. But note: current code path for non-notion providers — reasoning models (deepseek, glm) rely on reasoning being prepended. With cfg=None, behavior unchanged. Good.

5. One subtlety: `--list-models` path doesn't call resolve_provider — unaffected. Fine.

6. Default system prompt (default_system): plan says PROVIDERS gets optional `default_system` and user `--system` overrides. Where is default_system applied? In main() when building messages — main now has cfg, so feasible. Plan doesn't explicitly state who applies it but main() has cfg via new return. Reasonably implied via T1/T2? Actually neither T1 nor T2 explicitly mentions applying default_system in main. Minor gap — could be flagged as 轻微: default_system 的注入位置（main 构建消息处）未在任务中显式列出，T2 单测也未覆盖 default_system 覆盖逻辑。Let me check T2 tests: ①clean ②503 retry ③non-notion no cfg ④extract no reasoning. No test for default_system injection or override. Minor gap.

**③ cfg=None backward compat:**

- call_model(cfg=None): 503 retry only when cfg has retry_503; else sys.exit — matches current behavior (current code: URLError catch → sys.exit). But wait: current code catches URLError and exits for ALL errors, not just 503. Plan says "cfg 有 retry_503 时 503 走重试循环...否则维持现行为直接 sys.exit". OK — for existing providers, any URLError still sys.exit. Behavior unchanged. Good.
- extract_content(cfg=None): reasoning concatenation preserved. Good.
- 5 existing providers unchanged in registry (notion is a new entry). Good.
- One risk: isinstance checks — if cfg passed is PROVIDERS[provider_name], contains "models" key; call_model uses cfg.get("retry_503") — fine.

Minor: T2 test ③ "mock 非 notion provider 无 cfg" — actually plan says main passes cfg always; the test mocks cfg=None. Fine.

**④ New problems in v2:**

1. The prefix-stripping contradiction (above) — biggest.

2. 503 detection: current except URLError — how to detect 503 specifically? e is HTTPError (subclass of URLError), e.code == 503. Fact 5 acknowledges HTTPError is URLError subclass. Plan needs e.code check — implied. Also: after sleep 28s × up to 2 retries, timeout is urlopen timeout=300 per attempt — total worst case: attempt1 (up to 300s) + 28s + attempt2 + 28s + attempt3 could exceed plan's "最坏 3 次尝试 ≈ 2-3 分钟" estimate? If each attempt is fast-fail 503, 2×28s = 56s + response times. Plan says script timeout 300s is enough — but urlopen timeout is 300s PER attempt; 3 attempts worst case = 900s+ if hangs. But 503 fails fast typically. The plan's risk note is about total time; the stated "脚本 timeout 已是 300s" — wait, what script timeout? urlopen timeout=300 is per-request. If attempt 1 takes 300s then 503... unlikely. Minor nitpick, maybe not worth flagging given 50字 limit. Actually the risk assessment "最坏 3 次尝试 ≈ 2-3 分钟" ignores per-attempt latency of 30-60s responses (stated in §1: responses are 30-60s slow). Worst realistic: 3×(60s) + 2×28s = 236s < 300s per-attempt timeout, but total wall time fine-ish. Eh, borderline. Could mention as 轻微.

3. `clean_output` declares function name "clean_notion_output" — extract_content doesn't call it per plan; clean happens... where? Plan says "清洗函数 clean_notion_output() 只负责 UUID...（后处理）" — so who invokes it? main() after extract_content? Not specified. §2a point 4 says extract_content returns content directly when clean_output declared, and clean function is "后处理" — but the caller/injection point of clean_notion_output isn't assigned in tasks explicitly (T2 mentions implementing it and unit test
[用量: 5756 in / 3000 out / 8756 total]

