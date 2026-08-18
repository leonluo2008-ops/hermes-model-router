> 2026-08-04 实战。用户说"切换模型"，实际想临时在本次对话用某个模型，不想要全局持久化。

## 关键区分

在 gateway（Telegram / 飞书）对话里，/model 命令默认会**持久化**写到 `~/.hermes/config.yaml`。用户说"临时切换""本次用用"时，必须用 `--session` 显式会话级切换。

| 命令 | 是否改 config.yaml | 会话结束后 |
|---|---|---|
| `/model X --session` | ❌ 不改 | 自动恢复全局默认 |
| `/model X`（不带 flag） | ✅ 持久化 | 保留为新默认 |
| `/model X --global` | ✅ 写全局配置 | 永久生效 |
| `/model X --provider P --session` | ❌ 不改 | 自动恢复 |

## 用户原话触发词

当用户说这些时，默认走 `--session`：
- "切一下模型"
- "临时用 XX 模型"
- "本次对话用 XX 模型"
- "切换布局"
- "让 XX 处理这个"（如果只是临时想让某个模型看一下）

当用户说这些时，才考虑持久化：
- "把默认模型改成 XX"
- "以后都用 XX"
- "全局切换"

## 已验证的快捷表（本机 config.yaml）

| 想用 | 会话临时命令 |
|---|---|
| DeepSeek V4 Flash（全局默认） | `/model deepseek-v4-flash:0731 --session` |
| Kimi 2.7 Code | `/model kimi-k2.7-code:cloud --session` |
| Gemma 4 31B | `/model gemma4:31b-cloud --session` |
| GLM-5.2 | `/model glm-5.2 --provider zai --session` |
| Gemini 3.5 Flash | `/model gemini-3.5-flash --provider juxin-gemini --session` |

## 误操作后的修复

如果已经误用 `--global` 把全局默认改了，用户想改回去：

```bash
# 改回全局默认（一次性 dict，避免 base_url 残留）
hermes config set model '{"default": "deepseek-v4-flash:0731", "provider": "ollama-cloud"}'
```

改完必须重启 gateway：`systemctl --user restart hermes-gateway`（在网关外部 shell 执行）。

## 与 "主 agent 直接调 API" 的区别

- `/model --session`：改变当前对话的主模型，后续所有回复都由该模型生成
- `call_model.py`/curl 直接调 API：不改变主模型，只把某个具体任务丢给指定模型，结果返回后仍用原模型继续对话

用户如果只是"想让 XX 模型看一下某个材料"，优先推荐直接调 API（零副作用）；用户如果想"接下来整段对话都用 XX 模型"，才用 `/model --session`。

## 参考

- Hermes 源码：`gateway/slash_commands.py:1381-1412`（`/model` 命令解析 `--session` / `--global`）
- 相关 skill：`hermes-config-hub` §Model 与 Provider 配置
