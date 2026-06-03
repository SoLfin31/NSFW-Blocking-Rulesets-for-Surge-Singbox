#!/usr/bin/env python3
"""
从网站抓取 NSFW 域名，追加到 domains.txt

scrapeUrls.txt 格式：
  https://example.com            ← 使用默认 class "visit-icon"
  https://example.com | my-class   ← 指定自定义 class
  # 这是注释行，会被跳过
"""

import sys
import time
import re
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
    """从 href 或纯文本中提取规范化的裸域名。如果某一级域名包含非法字符（如中文），整级丢弃。"""
    if not href:
        return None
    href = href.strip()
    if href.startswith(("#", "javascript:", "mailto:")):
        return None
        
    # 兼容处理：如果没有协议头
    if not href.startswith(("http://", "https://", "//")):
        href = "http://" + href
        
    try:
        netloc = urlparse(href).netloc
        if not netloc:
            return None
            
        # 去掉端口，转小写
        domain = netloc.split(":")[0].lower()
        
        # ── 核心修复：按块 (block) 验证并剔除 ─────────────────────────
        # 分割域名，例如 "签t.obaba1.com" -> ["签t", "obaba1", "com"]
        parts = domain.split('.')
        clean_parts = []
        
        # 允许的字符集：仅限小写字母、数字和连字符
        # 这个正则要求整个 block 必须全是合法字符
        valid_part_pattern = re.compile(r'^[a-z0-9\-]+$')
        
        for part in parts:
            # 如果这个块包含任何非标准字符（比如中文），正则匹配会失败，整个块被直接抛弃
            if part and valid_part_pattern.match(part):
                clean_parts.append(part)
        
        # 重新拼合剩下的干净块
        clean_domain = ".".join(clean_parts)
        # ───────────────────────────────────────────────────────────────

        if clean_domain.startswith("www."):
            clean_domain = clean_domain[4:]
            
        # 简单验证：必须至少包含一个点号（两级以上），且整体长度大于3
        if "." in clean_domain and len(clean_domain) > 3:
            return clean_domain
        return None
    except Exception:
        return None


def scrape_page(url: str, css_class: str = DEFAULT_CLASS) -> set[str]:
    """抓取单个页面，提取容器内的所有域名；失败时返回空集合。"""
    print(f"    请求: {url}  [class='{css_class}']")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding # 防止乱码
    except requests.exceptions.Timeout:
        print(f"    ✗ 超时", file=sys.stderr)
        return set()
    except requests.exceptions.HTTPError as e:
        print(f"    ✗ HTTP {e.response.status_code}", file=sys.stderr)
        return set()
    except requests.exceptions.RequestException as e:
        print(f"    ✗ 请求失败: {e}", file=sys.stderr)
        return set()

    soup = BeautifulSoup(resp.text, "html.parser")
    
    # 获取所有包含该 class 的元素（可能是 <a>，也可能是 <div> / <ul> 等容器）
    elements = soup.find_all(class_=css_class)
    domains: set[str] = set()
    
    # 匹配标准域名的正则表达式（用于兜底纯文本）
    domain_pattern = re.compile(r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}')

    for el in elements:
        # 策略 1: 提取元素内部所有的 <a> 标签
        links = el.find_all("a")
        # 如果元素本身就是 <a> 标签，也一并加入处理
        if el.name == "a":
            links.append(el)
            
        for tag in links:
            domain = extract_domain(tag.get("href", ""))
            if domain:
                domains.add(domain)
                
        # 策略 2: 兜底处理纯文本（如果域名是作为普通文本写在 html 里的）
        text_content = el.get_text(separator=" ")
        for match in domain_pattern.findall(text_content):
            domain = extract_domain(match)
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
