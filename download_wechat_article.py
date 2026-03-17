from __future__ import annotations

import argparse
from pathlib import Path

from wechat_to_markdown import (
    DEFAULT_OUTPUT_DIR,
    download_wechat_article_markdown,
    ensure_stdout_utf8,
    is_wechat_article_url,
)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="下载公众号文章并转换为 Markdown。"
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=None,
        help="公众号文章链接，例如 https://mp.weixin.qq.com/s/...",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="输出目录，默认 temp",
    )
    return parser.parse_args()


def main() -> int:
    ensure_stdout_utf8()
    args = parse_args()
    if not args.url:
        print("请提供公众号文章链接，例如 https://mp.weixin.qq.com/s/...")
        return 1
    if not is_wechat_article_url(args.url):
        print("请输入有效的微信文章链接，例如 https://mp.weixin.qq.com/s/...")
        return 1

    output_dir = Path(args.output_dir)
    try:
        md_path = download_wechat_article_markdown(args.url, output_dir)
    except KeyboardInterrupt:
        print("已取消。")
        return 130
    except Exception as exc:
        print(f"抓取失败: {exc}")
        return 1

    print(f"Markdown 已写入: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
