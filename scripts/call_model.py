#!/usr/bin/env python3
"""
call_model.py — 多模型快速调用工具

用法:
  python3 call_model.py --model qwen3.5:397b-cloud --prompt "分析这段代码"
  python3 call_model.py --model kimi-k2.7-code:cloud < input.txt
  python3 call_model.py --model deepseek-v4-pro:cloud --prompt "审查方案"

支持模型:
  Ollama Cloud: qwen3.5:397b-cloud, kimi-k2.7-code:cloud, deepseek-v4-pro:cloud,
                deepseek-v4-flash:cloud, gemma4:31b-cloud
  聚鑫:         gemini-3.5-flash, gpt-5.6-sol
  ZAI:          glm-5.2
  OmniRoute:   jy/* (deepseek/glm/kimi/qwen), jxgpt/gpt-5.6-sol

API key 从 ~/.hermes/.env 读取，与 Hermes 共享。
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

# ── Provider 注册表（可扩展） ──
# 加新 provider 只需在这里加一行
PROVIDERS = {
    "ollama-cloud": {
        "base_url": "https://ollama.com/v1",
        "key_env": "OLLAMA_API_KEY",
        "models": [
            "qwen3.5:397b-cloud",
            "kimi-k2.7-code:cloud",
            "deepseek-v4-pro:cloud",
            "deepseek-v4-flash:cloud",
            "gemma4:31b-cloud",
        ],
    },
    "juxin": {
        "base_url": "https://api.jxincm.cn/v1",
        "key_env": "JUXIN_API_KEY",
        "models": ["gemini-3.5-flash", "gemini-3.6-flash"],
    },
    "juxin-gpt": {
        "base_url": "https://api.jxincm.cn/v1",
        "key_file": "/home/luo/OneDrive-Hermes-Exchange/聚鑫gpt-key.txt",
        "models": ["gpt-5.6-sol", "gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol-max", "gpt-5.6-sol-ultra"],
    },
    "zai": {
        "base_url": "https://open.bigmodel.cn/api/coding/paas/v4",
        "key_env": "ZAI_API_KEY",
        "models": ["glm-5.2"],
    },
    "omniroute": {
        "base_url": "http://127.0.0.1:20128/v1",
        "key_env": "OMNIROUTE_API_KEY",
        "models": [
            "jy/deepseek-v4-flash",
            "jy/deepseek-v4-pro",
            "jy/glm-5.2",
            "jy/kimi-k2.7-code",
            "jy/qwen3.8-max",
            "jxgpt/gpt-5.6-sol",
            "qwen3.8",
        ],
    },
}

# ── 模型 → Provider 反向索引 ──
_MODEL_TO_PROVIDER = {}
for provider_name, cfg in PROVIDERS.items():
    for model in cfg["models"]:
        _MODEL_TO_PROVIDER[model] = provider_name


def load_env(hermes_home: Path) -> dict:
    """读取 ~/.hermes/.env，返回 {KEY: VALUE} 字典。"""
    env_path = hermes_home / ".env"
    if not env_path.exists():
        return {}
    env = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        env[key] = value
    return env


def resolve_provider(model: str) -> tuple[str, str, str]:
    """根据模型名返回 (provider_name, base_url, api_key)。"""
    provider_name = _MODEL_TO_PROVIDER.get(model)
    if not provider_name:
        available = ", ".join(sorted(_MODEL_TO_PROVIDER.keys()))
        sys.exit(f"错误: 不支持的模型 '{model}'。\n可用模型: {available}")

    cfg = PROVIDERS[provider_name]
    base_url = cfg["base_url"]

    # ① 优先 key_file（文件内第一行非空为 key）
    if cfg.get("key_file"):
        kf = Path(cfg["key_file"])
        if not kf.exists():
            sys.exit(f"错误: key 文件不存在: {kf}")
        key_lines = [l.strip() for l in kf.read_text(encoding="utf-8").splitlines() if l.strip()]
        if not key_lines:
            sys.exit(f"错误: key 文件为空: {kf}")
        return provider_name, base_url, key_lines[0]

    # ② 环境变量读取（系统 env 优先，fallback 到 .env）
    key_env = cfg["key_env"]
    api_key = os.environ.get(key_env)
    if not api_key:
        hermes_home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
        env = load_env(hermes_home)
        api_key = env.get(key_env)

    if not api_key:
        sys.exit(f"错误: 找不到 {key_env}。请确保 ~/.hermes/.env 中已配置。")

    return provider_name, base_url, api_key


def call_model(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> dict:
    """调用 OpenAI 兼容的 chat completions API。"""
    url = f"{base_url.rstrip('/')}/chat/completions"
    body = json.dumps(
        {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
    ).encode("utf-8")

    req = Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")

    try:
        resp = urlopen(req, timeout=300)
        raw = resp.read().decode("utf-8")
        # 兼容强制流式的网关：body 以 data: 开头时聚合 SSE chunk
        if raw.lstrip().startswith("data:"):
            return _aggregate_sse(raw)
        return json.loads(raw)
    except URLError as e:
        # 尝试读取错误响应体
        error_body = ""
        if hasattr(e, "read"):
            try:
                error_body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass
        sys.exit(f"API 调用失败: {e}\n{error_body}")


def _aggregate_sse(raw: str) -> dict:
    """聚合 SSE 流式响应为单个 chat.completion 对象（兼容强制流式的网关）。"""
    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    final = {
        "id": "", "object": "chat.completion", "created": 0, "model": "",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": ""}, "finish_reason": None}],
        "usage": None,
    }
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if payload == "[DONE]":
            break
        try:
            chunk = json.loads(payload)
        except json.JSONDecodeError:
            continue
        final["id"] = final["id"] or chunk.get("id", "")
        final["created"] = final["created"] or chunk.get("created", 0)
        final["model"] = final["model"] or chunk.get("model", "")
        if chunk.get("usage"):
            final["usage"] = chunk["usage"]
        for ch in chunk.get("choices", []):
            delta = ch.get("delta", {})
            content_parts.append(delta.get("content") or "")
            reasoning_parts.append(delta.get("reasoning_content") or delta.get("reasoning") or "")
            if ch.get("finish_reason"):
                final["choices"][0]["finish_reason"] = ch["finish_reason"]
    final["choices"][0]["message"]["content"] = "".join(content_parts)
    msg = final["choices"][0]["message"]
    reasoning = "".join(reasoning_parts)
    if reasoning:
        msg["reasoning_content"] = reasoning
    return final


def extract_content(response: dict) -> str:
    """从 API 响应中提取文本内容，处理推理模型。"""
    choices = response.get("choices", [])
    if not choices:
        return ""

    message = choices[0].get("message", {})
    content = message.get("content", "")

    # 处理推理模型
    # DeepSeek V4 系列用 "reasoning" 字段（Ollama 格式）
    # GLM-5.2 用 "reasoning_content" 字段（ZAI 格式）
    reasoning = message.get("reasoning") or message.get("reasoning_content") or ""
    if reasoning:
        reasoning = re.sub(r"<\|think\|>.*?</\|think\|>", "", reasoning, flags=re.DOTALL).strip()
        if reasoning:
            content = f"{reasoning}\n\n---\n\n{content}" if content else reasoning

    # 如果 content 仍为空但 finish_reason 是 "length"，说明 reasoning 被截断
    # 此时尝试从 reasoning 取最后一段
    if not content.strip() and choices[0].get("finish_reason") == "length":
        content = reasoning

    return content.strip()


def main():
    parser = argparse.ArgumentParser(
        description="多模型快速调用工具 — 调指定模型处理任务，用完即扔"
    )
    parser.add_argument(
        "--model",
        help="模型名，如 qwen3.5:397b-cloud、kimi-k2.7-code:cloud",
    )
    parser.add_argument("--prompt", help="提示文本（可选，不传则从 stdin 读取）")
    parser.add_argument(
        "--max-tokens", type=int, default=4096, help="最大输出 token 数（默认 4096）"
    )
    parser.add_argument(
        "--temperature", type=float, default=0.7, help="采样温度（默认 0.7）"
    )
    parser.add_argument(
        "--system", help="系统提示词（可选）"
    )
    parser.add_argument(
        "--list-models", action="store_true", help="列出所有支持的模型"
    )

    args = parser.parse_args()

    # 列出模型
    if args.list_models:
        print("支持的模型：")
        for provider_name, cfg in PROVIDERS.items():
            print(f"\n  [{provider_name}] ({cfg['base_url']})")
            for model in cfg["models"]:
                print(f"    {model}")
        return

    # 获取 prompt
    prompt = args.prompt
    if not prompt:
        prompt = sys.stdin.read().strip()
    if not prompt:
        sys.exit("错误: 请提供 --prompt 或通过 stdin 传入文本。")

    # 解析 provider
    provider_name, base_url, api_key = resolve_provider(args.model)

    # 构建消息
    messages = []
    if args.system:
        messages.append({"role": "system", "content": args.system})
    messages.append({"role": "user", "content": prompt})

    # 调用
    response = call_model(
        base_url=base_url,
        api_key=api_key,
        model=args.model,
        messages=messages,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
    )

    # 输出结果
    content = extract_content(response)
    print(content)

    # 输出用量信息到 stderr（不影响 stdout 的管道使用）
    usage = response.get("usage", {})
    if usage:
        print(
            f"\n[用量: {usage.get('prompt_tokens', '?')} in / {usage.get('completion_tokens', '?')} out / {usage.get('total_tokens', '?')} total]",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
