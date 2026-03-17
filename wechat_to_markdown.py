from __future__ import annotations

import importlib
import os
import re
import subprocess
import sys
from pathlib import Path


PACKAGE_NAME = "wechat-article-to-markdown"
MODULE_NAME = "wechat_article_to_markdown"
DEFAULT_OUTPUT_DIR = Path("temp")
LOCALAPPDATA_DIR = Path(".localappdata")
__all__ = [
    "DEFAULT_OUTPUT_DIR",
    "LOCALAPPDATA_DIR",
    "configure_runtime_environment",
    "download_wechat_article_markdown",
    "ensure_stdout_utf8",
    "fetch_wechat_article_markdown",
    "is_wechat_article_url",
    "sanitize_filename",
]


def ensure_stdout_utf8() -> None:
    # 统一标准输出/错误输出编码，避免中文日志在 Windows 控制台中乱码。
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def configure_runtime_environment(localappdata_dir: Path = LOCALAPPDATA_DIR) -> None:
    # 为依赖库伪造一个可写的本地配置目录，避免在受限环境下因系统目录不可写而失败。
    resolved_dir = localappdata_dir.resolve()
    resolved_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("LOCALAPPDATA", str(resolved_dir))
    os.environ.setdefault("APPDATA", str(resolved_dir / "Roaming"))
    os.environ.setdefault("WIN_PD_OVERRIDE_LOCAL_APPDATA", str(resolved_dir))
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")


def ensure_dependency() -> None:
    # 优先直接导入；缺失时再按需安装，减少首次使用门槛。
    try:
        importlib.import_module(MODULE_NAME)
        return
    except ModuleNotFoundError:
        pass

    print(f"{PACKAGE_NAME} 未安装，开始自动安装...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", PACKAGE_NAME])
    importlib.invalidate_caches()


def camoufox_executable() -> Path:
    # camoufox 与当前 Python 可执行文件通常位于同一目录，直接按文件名推导路径。
    exe_name = "camoufox.exe" if sys.platform.startswith("win") else "camoufox"
    return Path(sys.executable).with_name(exe_name)


def ensure_camoufox_ready() -> None:
    # 某些环境只安装了命令入口但未下载浏览器内核，这里做一次懒加载检查。
    camoufox_bin = camoufox_executable()
    if not camoufox_bin.exists():
        return

    version = subprocess.run(
        [str(camoufox_bin), "version"],
        capture_output=True,
        text=True,
        check=False,
    )
    if "Not downloaded!" not in version.stdout:
        return

    print("Camoufox 浏览器未下载，开始自动获取...")
    subprocess.check_call([str(camoufox_bin), "fetch"])


def sanitize_filename(title: str) -> str:
    # 文件名仅保留中英文、数字及少量安全字符，避免 Windows 路径非法字符导致写入失败。
    filtered = []
    for ch in title:
        code = ord(ch)
        if ch.isalnum() or ch in {" ", "_", "-"}:
            filtered.append(ch)
            continue
        if 0x4E00 <= code <= 0x9FFF:
            filtered.append(ch)

    safe_title = "".join(filtered)
    safe_title = re.sub(r"\s+", "_", safe_title).strip("._-")
    return safe_title[:80] or "wechat_article"


def is_wechat_article_url(url: str) -> bool:
    return url.startswith("https://mp.weixin.qq.com/")


async def fetch_wechat_article_markdown(url: str, output_dir: Path) -> Path:
    import asyncio

    # 在真正抓取前先确保运行时依赖和浏览器内核都已就绪。
    ensure_dependency()
    ensure_camoufox_ready()

    wechat = importlib.import_module(MODULE_NAME)
    beautifulsoup4 = importlib.import_module("bs4")
    async_api = importlib.import_module("camoufox.async_api")

    BeautifulSoup = beautifulsoup4.BeautifulSoup
    AsyncCamoufox = async_api.AsyncCamoufox

    print(f"抓取文章: {url}")
    
    # 用无头浏览器加载页面，处理公众号正文依赖前端渲染的情况。
    async with AsyncCamoufox(headless=True) as browser:
        page = await browser.new_page()
        await page.goto(url, wait_until="domcontentloaded")
        try:
            # 正文节点通常在 #js_content 中，等待它出现能提升抓取稳定性。
            await page.wait_for_selector("#js_content", timeout=10000)
        except Exception:
            pass
        # 额外等待一小段时间，给延迟注入的图片或正文补齐机会。
        await asyncio.sleep(2)
        html = await page.content()

    soup = BeautifulSoup(html, "html.parser")
    # 先提取元信息，标题为空通常意味着链接失效、风控页或需要人工验证。
    meta = wechat.extract_metadata(soup, html)
    title = meta.get("title") or ""
    if not title:
        raise RuntimeError("未提取到文章标题，可能需要人工验证或链接不可访问。")

    meta["source_url"] = url
    # 正文处理阶段同时返回正文 HTML、代码块占位信息和图片链接列表。
    content_html, code_blocks, img_urls = wechat.process_content(soup)
    if not content_html:
        raise RuntimeError("未提取到正文内容。")

    # 先把正文转成 Markdown，再统一回填本地图片路径。
    body_md = wechat.convert_to_markdown(content_html, code_blocks)

    safe_title = sanitize_filename(title)
    output_dir.mkdir(parents=True, exist_ok=True)
    asset_root = output_dir / f"{safe_title}.assets"
    image_dir = asset_root / "images"
    image_dir.mkdir(parents=True, exist_ok=True)

    # 将远程图片下载到本地资源目录，并把 Markdown 中的链接替换为相对路径。
    url_map = await wechat.download_all_images(img_urls, image_dir)
    relative_url_map = {
        remote_url: f"{asset_root.name}/{local_path.replace('\\', '/')}"
        for remote_url, local_path in url_map.items()
    }
    body_md = wechat.replace_image_urls(body_md, relative_url_map)

    # 最终拼装完整 Markdown 文本并落盘。
    result = wechat.build_markdown(meta, body_md)
    md_path = output_dir / f"{safe_title}.md"
    md_path.write_text(result, encoding="utf-8")
    return md_path


def download_wechat_article_markdown(url: str, output_dir: Path = DEFAULT_OUTPUT_DIR) -> Path:
    import asyncio

    # 同步入口仅负责补齐环境并托管事件循环，实际抓取逻辑仍在异步函数中。
    configure_runtime_environment()
    return asyncio.run(fetch_wechat_article_markdown(url, output_dir))
