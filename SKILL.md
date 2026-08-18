---
name: hermes-model-router
description: |-
  多模型快速调用工具集 — 不切换主模型，直接调指定模型 API 处理任务。
  支持 Ollama Cloud（qwen3.5/kimi/deepseek-v4-pro/flash/gemma4）、
  聚鑫（gemini-3.5-flash）、ZAI（glm-5.2）、
  OmniRoute 本地网关（jy/deepseek-v4-flash、jy/deepseek-v4-pro、
  jy/glm-5.2、jy/kimi-k2.7-code = 基元律动经 127.0.0.1:20128 中转）。
  触发词：用XX模型、让XX处理、调XX模型、call_model
---

# hermes-model-router

> 仓库: https://github.com/leonluo2008-ops/hermes-model-router
> 脚本: `scripts/call_model.py`

## 是什么

你说"用 Qwen 3.5 分析这个代码"，我直接调 Qwen 3.5 API 处理，结果给你，**不切换主模型、不改 config、不影响 prompt cache**。

## 安装

```bash
git clone https://github.com/leonluo2008-ops/hermes-model-router.git ~/Github/hermes-model-router
# 或软链到 Hermes 脚本目录
ln -sf ~/Github/hermes-model-router/scripts/call_model.py ~/.hermes/scripts/call_model.py
```

**依赖**：无（只用 Python 标准库 `urllib` + `json`）

**API key**：共享 `~/.hermes/.env`，无需额外配置。

## 用法

```bash
# 直接传 prompt
python3 scripts/call_model.py --model qwen3.5:397b-cloud --prompt "分析这段代码"

# 从 stdin 读（适合长文本）
cat code.py | python3 scripts/call_model.py --model kimi-k2.7-code:cloud

# 带系统提示词
python3 scripts/call_model.py --model deepseek-v4-pro:cloud --system "你是代码审查专家" --prompt "审查这个 PR"

# 列出所有支持的模型
python3 scripts/call_model.py --list-models
```

## 在 Hermes 中使用

你说以下任意一句话，我会自动调对应模型：

| 你说 | 实际调用 |
|---|---|
| "用 Qwen 3.5 分析这个" | `call_model.py --model qwen3.5:397b-cloud` |
| "让 Kimi 2.7 处理这个任务" | `call_model.py --model kimi-k2.7-code:cloud` |
| "用 DeepSeek V4 Pro 审查方案" | `call_model.py --model deepseek-v4-pro:cloud` |
| "用 Gemini 3.5 Flash 看看这张图" | `call_model.py --model gemini-3.5-flash` |

## 扩展

加新 provider 只需在 `PROVIDERS` 字典加一行：

```python
"new-provider": {
    "base_url": "https://api.example.com/v1",
    "key_env": "NEW_API_KEY",
    "models": ["model-name"],
}
```

## 设计原则

- **零副作用**：不改 config、不切模型、不影响 prompt cache
- **用完即扔**：每次调用独立，不残留任何状态
- **共享 ENV**：API key 从 `~/.hermes/.env` 读取，与 Hermes 同一套
- **纯标准库**：零外部依赖，`pip install` 都不需要

## 临时切换 vs 直接调 API

用户说"用 XX 模型"时有两种意图：

| 意图 | 做法 | 副作用 |
|---|---|---|
| **接下来整段对话都用 XX** | `/model X --session`（gateway 内） | 当前对话主模型切换，不改全局 |
| **只是这个任务让 XX 看一下** | `call_model.py` 或 curl 调 API | 零副作用，结果回来继续用原模型 |

详见 `references/temporary-model-switching.md`。

