#!/usr/bin/env python3
"""
从网站抓取 NSFW 域名，追加到 domains.txt

scrapeUrls.txt 格式：
  https://example.com              ← 使用默认 class "visit-icon"
  https://example.com | my-class   ← 指定自定义 class
  # 这是注释行，会被跳过
"""

import sys
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.google.com/",
}

DEFAULT_CLASS = "visit-icon"
URLS_FILE     = "scrapeUrls.txt"
OUTPUT_FILE   = "domains.txt"
REQUEST_DELAY = 1.5   # 相邻请求间隔（秒），避免对目标服务器造成压力


# ── 工具函数 ──────────────────────────────────────────────

def extract_domain(href: str) -> str | None:
    """从 href 中提取规范化的裸域名，失败返回 None。"""
    if not href:
        return None
    href = href.strip()
    if href.startswith(("#", "javascript:", "mailto:")):
        return None
    try:
        netloc = urlparse(href).netloc
        if not netloc:
            return None
        # 去掉端口，转小写，去掉 www. 前缀
        domain = netloc.split(":")[0].lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain or None
    except Exception:
        return None


def scrape_page(url: str, css_class: str = DEFAULT_CLASS) -> set[str]:
    """抓取单个页面，返回域名集合；失败时返回空集合。"""
    print(f"    请求: {url}  [class='{css_class}']")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        print(f"    ✗ 超时", file=sys.stderr)
        return set()
    except requests.exceptions.HTTPError as e:
        print(f"    ✗ HTTP {e.response.status_code}", file=sys.stderr)
        return set()
    except requests.exceptions.RequestException as e:
        print(f"    ✗ 请求失败: {e}", file=sys.stderr)
        return set()

    soup  = BeautifulSoup(resp.text, "html.parser")
    links = soup.find_all("a", class_=css_class)

    domains: set[str] = set()
    for tag in links:
        domain = extract_domain(tag.get("href", ""))
        if domain:
            domains.add(domain)

    return domains


def parse_urls_file(path: str) -> list[tuple[str, str]]:
    """
    解析配置文件，返回 [(url, css_class), ...] 列表。
    格式：每行 "URL" 或 "URL | class"，# 开头为注释。
    """
    entries: list[tuple[str, str]] = []
    try:
        with open(path, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "|" in line:
                    url_part, class_part = line.split("|", 1)
                    entries.append((url_part.strip(), class_part.strip()))
                else:
                    entries.append((line, DEFAULT_CLASS))
    except FileNotFoundError:
        # 文件不存在时静默退出，不中断 CI
        print(f"未找到 {path}，跳过网站抓取步骤。", file=sys.stderr)
    return entries


# ── 主流程 ────────────────────────────────────────────────

def main() -> None:
    entries = parse_urls_file(URLS_FILE)
    if not entries:
        print("scrapeUrls.txt 中无有效条目，退出。")
        return

    all_domains: set[str] = set()
    total = len(entries)

    for i, (url, css_class) in enumerate(entries, start=1):
        print(f"[{i}/{total}] 抓取: {url}")
        found = scrape_page(url, css_class)
        print(f"    → 找到 {len(found)} 个域名")
        all_domains.update(found)

        if i < total:
            time.sleep(REQUEST_DELAY)

    if not all_domains:
        print("⚠ 未抓取到任何域名。", file=sys.stderr)
        return

    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        for domain in sorted(all_domains):
            f.write(domain + "\n")

    print(f"\n✓ 合计 {len(all_domains)} 个域名已追加至 {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
