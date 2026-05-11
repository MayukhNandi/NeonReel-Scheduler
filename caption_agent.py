from __future__ import annotations

import logging
import os
import random
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class CaptionResult:
    caption: str
    provider: str


def _humanize_filename(filename: str) -> str:
    stem = Path(filename).stem
    cleaned = re.sub(r"[_\-]+", " ", stem)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or "viral reel"


def _sanitize_filename(filename: str) -> str:
    stem = Path(filename).stem
    stem = re.sub(r"\(\s*\d{3,4}p\s*[^)]*\)", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"\b\d{3,4}p\b", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"\b\d{2,3}fps\b", "", stem, flags=re.IGNORECASE)
    stem = re.sub(r"[_\-]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem or "viral reel"


def _fallback_hashtags(topic: str) -> str:
    tag_pool = [
        "#reels",
        "#instareels",
        "#viral",
        "#trending",
        "#contentcreator",
        "#socialmedia",
        "#explorepage",
        "#fyp",
        "#videooftheday",
        "#reelsofinstagram",
        "#viralreels",
        "#trendingnow",
        "#creator",
        "#shorts",
        "#entertainment",
        "#storytime",
        "#animation",
        "#cartoon",
        "#kids",
        "#shortsvideo",
        "#funnyvideos",
        "#dailycontent",
        "#reelitfeelit",
        "#watchtillend",
        "#explore",
        "#memes",
        "#newreel",
        "#trendingreels",
        "#bestreels",
        "#viralcontent",
    ]
    topic_tag = f"#{re.sub(r'[^a-z0-9]+', '', topic.lower()) or 'viral'}"
    picks = random.sample(tag_pool, k=min(14, len(tag_pool)))
    picks.insert(0, topic_tag)
    return " ".join(dict.fromkeys(picks))


def _fallback_caption(filename: str) -> str:
    topic = _humanize_filename(filename)
    hashtags = _fallback_hashtags(topic)
    hook_templates = [
        "You won’t believe what happens in {topic}.",
        "This moment in {topic} is unreal.",
        "Wait for the twist in {topic}.",
        "The ending of {topic} will surprise you.",
        "One small moment makes {topic} unforgettable.",
        "Don’t blink during {topic}.",
    ]
    bullets = [
        "- Keep the first 2 seconds punchy.",
        "- Make the key moment obvious and fast.",
        "- Use simple language and big emotions.",
        "- Add a cliffhanger to boost replays.",
        "- Highlight the main character or action.",
        "- Finish with a clear takeaway.",
    ]
    hook = random.choice(hook_templates).format(topic=topic)
    bullet_choices = random.sample(bullets, k=3)
    return (
        f"{hook}\n"
        f"{bullet_choices[0]}\n"
        f"{bullet_choices[1]}\n"
        f"{bullet_choices[2]}\n\n"
        f"{hashtags}"
    )


@lru_cache(maxsize=1)
def _get_ollama_config() -> dict[str, str]:
    return {
        "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/"),
        "model": os.getenv("OLLAMA_MODEL", "llama3.2:1b").strip() or "llama3.2:1b",
    }


def _build_prompt(filename: str) -> str:
    human = _sanitize_filename(filename)
    return (
        "Write a viral Instagram caption for a video about: \""
        + human
        + "\".\n"
        "Do NOT include any instructions, meta-text, or words like \"Here is your caption\" or \"Hook:\". "
        "Just write the final caption.\n\n"
        "Format strictly like this:\n"
        "[1 Exciting sentence to grab attention]\n"
        "[1 sentence explaining what makes it interesting]\n"
        "[1 sentence asking the viewer a question]\n"
        "[15 popular, relevant Instagram hashtags separated by spaces]"
    )


def _ollama_client():
    import ollama

    cfg = _get_ollama_config()
    return ollama.Client(host=cfg["base_url"])


def _ollama_is_online() -> bool:
    try:
        client = _ollama_client()
        return bool(client.list())
    except Exception:
        return False


def _call_ollama(model: str, prompt: str) -> str:
    client = _ollama_client()
    response = client.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.8, "top_p": 0.9},
        stream=False,
    )
    if isinstance(response, dict):
        message = response.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
    text = getattr(response, "message", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    raise RuntimeError("Ollama returned an empty response")


def _cleanup_caption(text: str) -> str:
    cleaned = text.strip().strip("\"'")
    prefixes = [
        "here is your caption:",
        "caption:",
        "hook:",
    ]
    lowered = cleaned.lower()
    for prefix in prefixes:
        if lowered.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
            break
    cleaned = re.sub(r"^[-*\s]+", "", cleaned)
    return cleaned.strip()


def generate_caption(filename: str) -> CaptionResult:
    cfg = _get_ollama_config()
    model = cfg["model"]
    logger = logging.getLogger("caption_agent")

    random.seed(f"{filename}-{int(time.time())}")

    if not _ollama_is_online():
        logger.warning("Ollama is offline. Using fallback caption.")
        return CaptionResult(caption=_fallback_caption(filename), provider="fallback")

    try:
        prompt = _build_prompt(filename)
        raw = _call_ollama(model, prompt)
        return CaptionResult(caption=_cleanup_caption(raw), provider=f"ollama:{model}")
    except Exception:
        logger.exception("Ollama caption generation failed; using fallback caption.")
        return CaptionResult(caption=_fallback_caption(filename), provider="fallback")


__all__ = ["CaptionResult", "generate_caption"]