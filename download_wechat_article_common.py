import argparse
import re
import sys
import time
import os
from dataclasses import dataclass

from wechat_to_markdown_common import (
    extract_wechat_title,
    fetch_url_html,
    wechat_article_html_to_markdown,
)
from extract_urls_from_md import extract_urls_from_md_file

@dataclass
class WeChatArticleDownloader:
    """微信公众号文章下载器"""

    @staticmethod
    def _sanitize_filename(title: str) -> str:
        # 过滤 Windows 非法文件名字符，以及 —、– 等易引起问题的字符
        s = re.sub(r'[\\/*?:"<>|]', '', title)
        s = re.sub(r'[—–]', '', s)  # 去掉 em dash、en dash 等
        s = re.sub(r'\s+', ' ', s)   # 多余空白合并为单个空格
        s = s.strip()[:50] or "wechat_article"
        return s
    
    def download_article(
        self,
        url: str,
        title: str = None,
        cookie_file: str | None = None,
        cookie_header: str | None = None,
    ) -> str:
        """下载单篇文章并转为 Markdown"""
        # 下载器只负责流程编排，具体抓取和转换逻辑下沉到公共模块。
        html = fetch_url_html(url, cookie_file=cookie_file, cookie_header=cookie_header)
        article_title = title or extract_wechat_title(html)
        markdown = wechat_article_html_to_markdown(html)
        
        # 添加标题
        markdown = f"# {article_title}\n\n原文链接：{url}\n\n{markdown}"
        
        return markdown

    def download_article_to_file(
        self,
        url: str,
        output_dir: str = "temp",
        title: str = None,
        cookie_file: str | None = None,
        cookie_header: str | None = None,
    ) -> str:
        # 单篇下载默认写入 temp/<文章标题>.md，便于直接落盘使用。
        html = fetch_url_html(url, cookie_file=cookie_file, cookie_header=cookie_header)
        article_title = title or extract_wechat_title(html)
        markdown = wechat_article_html_to_markdown(html)
        markdown = f"# {article_title}\n\n原文链接：{url}\n\n{markdown}"

        os.makedirs(output_dir, exist_ok=True)
        safe_title = self._sanitize_filename(article_title)
        filepath = os.path.join(output_dir, f"{safe_title}.md")
        with open(filepath, 'w', encoding='utf-8') as out:
            out.write(markdown)
        extract_urls_from_md_file(filepath)
        return filepath

# 使用示例
if __name__ == "__main__":
    downloader = WeChatArticleDownloader()
    
    # 单篇下载：支持命令行参数或交互式输入
    parser = argparse.ArgumentParser(description="下载微信公众号文章为 Markdown")
    parser.add_argument("url", nargs="?", help="文章链接")
    parser.add_argument("--output-dir", "-o", default=None, help="输出目录，默认 temp")
    args = parser.parse_args()
    url = (args.url or input("请输入微信公众号文章链接: ")).strip()
    output_dir = args.output_dir if args.output_dir else (input("请输入输出目录 (默认 temp，直接回车使用默认): ").strip() or "temp")
    filepath = downloader.download_article_to_file(url, output_dir)
    print(f"已写入: {filepath}")
