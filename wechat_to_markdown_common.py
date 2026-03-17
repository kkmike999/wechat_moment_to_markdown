from __future__ import annotations

import re
from http.cookies import SimpleCookie
from pathlib import Path

import markdownify
import requests
from bs4 import BeautifulSoup, Tag


DEFAULT_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://mp.weixin.qq.com/",  # 关键：模拟从微信内跳转
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
    }


def parse_cookie_header(cookie_header: str) -> requests.cookies.RequestsCookieJar:
    # Chrome 导出的单行 Cookie header 需要先拆成 cookie jar，requests 才能稳定复用。
    jar = requests.cookies.RequestsCookieJar()
    raw_cookie = cookie_header.strip()
    if not raw_cookie:
        return jar

    simple_cookie = SimpleCookie()
    simple_cookie.load(raw_cookie)

    if simple_cookie:
        for name, morsel in simple_cookie.items():
            jar.set(name, morsel.value)
        return jar

    # 某些导出文本包含 requests 不认识的字符，退回到最宽松的手动分割逻辑。
    for item in raw_cookie.split(";"):
        name, separator, value = item.strip().partition("=")
        if separator and name:
            jar.set(name, value)

    return jar


def load_cookie_header(cookie_file: str | Path) -> str:
    return Path(cookie_file).read_text(encoding="utf-8").strip()


def fetch_url_html(
    url: str,
    headers: dict[str, str] | None = None,
    cookies: requests.cookies.RequestsCookieJar | dict[str, str] | None = None,
    cookie_header: str | None = None,
    cookie_file: str | Path | None = None,
    timeout: int = 30,
    encoding: str = "utf-8",
) -> str:
    # 统一封装请求参数和编码处理，方便其他脚本直接复用。
    request_cookies = cookies
    if cookie_header:
        request_cookies = parse_cookie_header(cookie_header)
    elif cookie_file:
        request_cookies = parse_cookie_header(load_cookie_header(cookie_file))

    response = requests.get(
        url,
        headers=headers or DEFAULT_HEADERS,
        cookies=request_cookies,
        timeout=timeout,
    )
    response.raise_for_status()
    response.encoding = encoding
    return response.text


def extract_wechat_content_div(html: str) -> Tag:
    # 微信公众号正文通常位于 #js_content，后续转换都以这个节点为入口。
    soup = BeautifulSoup(html, "html.parser")
    content_div = soup.find(id="js_content")
    if not content_div:
        raise ValueError("无法找到文章内容")
    return content_div


def extract_wechat_title(html: str) -> str:
    # 标题优先取页面主标题，缺失时再回退到 og:title，兼容不同文章模板。
    soup = BeautifulSoup(html, "html.parser")
    title_node = soup.find(id="activity-name")
    if title_node:
        title = title_node.get_text(strip=True)
        if title:
            return title

    meta_title = soup.find("meta", attrs={"property": "og:title"})
    if meta_title and meta_title.get("content"):
        return meta_title["content"].strip()

    raise ValueError("无法找到文章标题")


def normalize_wechat_images(content_div: Tag) -> Tag:
    # 微信文章的真实图片地址常放在 data-src，需要补到 src 才能被 markdownify 正确识别。
    for img in content_div.find_all("img"):
        if img.get("data-src"):
            img["src"] = img["data-src"]
    return content_div


def clean_wechat_attrs(text: str) -> str:
    # 去掉微信公众号遗留的 data/style 属性，避免污染最终 Markdown。
    text = re.sub(r'\s*data-[a-z-]+="[^"]*"', "", text)
    text = re.sub(r'\s*style="[^"]*"', "", text)
    return text


def html_to_markdown(html: str | Tag) -> str:
    # 统一定义 Markdown 转换参数，保证不同调用方产出的格式一致。
    markdown = markdownify.markdownify(
        str(html),
        heading_style="ATX",
        bullets="-",
        strip=["script", "style"],
    )
    return clean_wechat_attrs(markdown)


def wechat_article_html_to_markdown(html: str) -> str:
    # 组合公众号文章的标准转换流程：提取正文、修正图片、输出 Markdown。
    content_div = extract_wechat_content_div(html)
    normalize_wechat_images(content_div)
    return html_to_markdown(content_div)
