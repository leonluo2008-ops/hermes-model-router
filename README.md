# Hermes Model Router

多模型快速调用工具集 — **不切换主模型，直接调指定模型 API 处理任务，用完即扔。**

## 痛点

Hermes 主力模型是 `deepseek-v4-flash:cloud`（经济省钱），但有时需要更强的模型处理复杂任务：

- Qwen 3.5（397B）做深度分析
- Kimi 2.7 Code 做代码审查
- DeepSeek V4 Pro 做方案评审

传统做法是 `/model qwen` 切模型 → 处理完 → `/model flash` 切回来。**麻烦，且每次切换破坏 prompt cache。**

## 解决方案

你说"用 Qwen 3.5 分析这个代码"，我直接调 Qwen 3.5 API 处理，结果给你，**主力模型不动、config 不改、cache 不破**。

```bash
# 直接调 Qwen 3.5，不切主模型
python3 scripts/call_model.py --model qwen3.5:397b-cloud --prompt "分析这段代码"

# 让 Kimi 2.7 处理
cat code.py | python3 scripts/call_model.py --model kimi-k2.7-code:cloud

# 用 DeepSeek V4 Pro 审查方案
python3 scripts/call_model.py --model deepseek-v4-pro:cloud --system "你是代码审查专家" --prompt "审查这个 PR"
```

## 支持的模型

| 模型 | Provider | API 端点 |
|---|---|---|
| `qwen3.5:397b-cloud` | Ollama Cloud | `https://ollama.com/v1` |
| `kimi-k2.7-code:cloud` | Ollama Cloud | `https://ollama.com/v1` |
| `deepseek-v4-pro:cloud` | Ollama Cloud | `https://ollama.com/v1` |
| `deepseek-v4-flash:cloud` | Ollama Cloud | `https://ollama.com/v1` |
| `gemma4:31b-cloud` | Ollama Cloud | `https://ollama.com/v1` |
| `gemini-3.5-flash` | 聚鑫 | `https://api.jxincm.cn/v1` |
| `glm-5.2` | ZAI | `https://open.bigmodel.cn/api/coding/paas/v4` |

## 安装

```bash
# 克隆仓库
git clone https://github.com/leonluo2008-ops/hermes-model-router.git ~/Github/hermes-model-router

# 软链到 Hermes 脚本目录（可选，方便 Hermes 直接调用）
ln -sf ~/Github/hermes-model-router/scripts/call_model.py ~/.hermes/scripts/call_model.py
```

**依赖**：无（纯 Python 标准库，`urllib` + `json`）

**API key**：共享 `~/.hermes/.env`，无需额外配置。需要以下环境变量：

| 环境变量 | 用途 |
|---|---|
| `OLLAMA_API_KEY` | Ollama Cloud 模型 |
| `JUXIN_API_KEY` | 聚鑫模型（gemini-3.5-flash） |
| `ZAI_API_KEY` | ZAI 模型（glm-5.2） |

## 用法

```bash
# 列出所有支持的模型
python3 scripts/call_model.py --list-models

# 直接传 prompt
python3 scripts/call_model.py --model qwen3.5:397b-cloud --prompt "分析这段代码"

# 从 stdin 读（适合长文本、管道）
cat code.py | python3 scripts/call_model.py --model kimi-k2.7-code:cloud

# 带系统提示词
python3 scripts/call_model.py --model deepseek-v4-pro:cloud \
  --system "你是代码审查专家" \
  --prompt "审查这个 PR"

# 控制输出长度
python3 scripts/call_model.py --model glm-5.2 \
  --prompt "写一篇 500 字的技术方案" \
  --max-tokens 2048 \
  --temperature 0.3
```

## 在 Hermes Agent 中使用

安装后，在 Hermes 会话中直接说：

> "用 Qwen 3.5 分析这个代码"
> "让 Kimi 2.7 处理这个任务"
> "用 DeepSeek V4 Pro 审查这个方案"
> "用 Gemini 3.5 Flash 看看这张图"

Hermes 会自动调对应模型 API，结果返回给你，**主力模型不动**。

## 扩展

加新 provider 只需在 `scripts/call_model.py` 的 `PROVIDERS` 字典加一行：

```python
PROVIDERS = {
    "ollama-cloud": {
        "base_url": "https://ollama.com/v1",
        "key_env": "OLLAMA_API_KEY",
        "models": ["qwen3.5:397b-cloud", "kimi-k2.7-code:cloud", ...],
    },
    "new-provider": {                          # ← 加这里
        "base_url": "https://api.example.com/v1",
        "key_env": "NEW_API_KEY",
        "models": ["model-name"],
    },
}
```

## 设计原则

- **零副作用**：不改 config、不切模型、不影响 prompt cache
- **用完即扔**：每次调用独立，不残留任何状态
- **共享 ENV**：API key 从 `~/.hermes/.env` 读取，与 Hermes 同一套
- **纯标准库**：零外部依赖，`pip install` 都不需要
- **可扩展**：加 provider 只需一行字典

## 项目结构

```
hermes-model-router/
├── SKILL.md              # Hermes Skill 定义
├── README.md             # 本文件
├── scripts/
│   └── call_model.py     # 核心脚本
└── .env.example          # 环境变量模板
```

## 许可证

MIT
