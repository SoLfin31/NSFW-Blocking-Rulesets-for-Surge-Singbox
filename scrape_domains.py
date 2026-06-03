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
    """
    从 href 或纯文本中提取规范化的裸域名。
    1. 彻底剔除含有中文等非法字符的整级域名块。
    2. 智能提取根域名，自动切除无用的前缀子域名。
    """
    if not href:
        return None
    href = href.strip()
    if href.startswith(("#", "javascript:", "mailto:")):
        return None
        
    # 兼容处理：如果没有协议头（针对纯文本匹配）
    if not href.startswith(("http://", "https://", "//")):
        href = "http://" + href
        
    try:
        netloc = urlparse(href).netloc
        if not netloc:
            return None
            
        # 去掉端口，转小写
        domain = netloc.split(":")[0].lower()
        
        # ── 步骤 1：按块验证并剔除包含非法字符（如中文）的行 ─────────────────
        parts = domain.split('.')
        clean_parts = []
        
        # 仅允许小写字母、数字和连字符
        valid_part_pattern = re.compile(r'^[a-z0-9\-]+$')
        
        for part in parts:
            if part and valid_part_pattern.match(part):
                clean_parts.append(part)
        
        # 如果清洗后连最基本的两级域名都不够，直接丢弃
        if len(clean_parts) < 2:
            return None
            
        # ── 步骤 2：智能保留根域名（解决类似 cang.45678998.xyz 的问题） ──────
        # 判断末尾是否为双重国家顶级域名后缀（例如 .com.cn, .co.uk, .org.uk）
        is_double_tld = False
        if len(clean_parts[-1]) == 2 and clean_parts[-2] in {"com", "co", "net", "org", "gov", "edu", "biz", "info"}:
            is_double_tld = True
            
        if is_double_tld:
            # 如果是 sub.example.com.cn，切掉多余前缀，只保留最后 3 块
            clean_parts = clean_parts[-3:]
        else:
            # 如果是 cang.45678998.xyz，只保留最后 2 块
            clean_parts = clean_parts[-2:]
            
        clean_domain = ".".join(clean_parts)
        # ───────────────────────────────────────────────────────────────

        if clean_domain.startswith("www."):
            clean_domain = clean_domain[4:]
            
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
    elements = soup.find_all(class_=css_class)

    domains: set[str] = set()
    
    # 匹配标准域名的正则表达式（用于兜底纯文本）
    domain_pattern = re.compile(r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}')

    for el in elements:
        # 提取容器内部所有的 <a> 标签
        links = el.find_all("a")
        # 如果元素本身就是 <a> 标签，也一并加入处理
        if el.name == "a":
            links.append(el)
            
        for tag in links:
            domain = extract_domain(tag.get("href", ""))
            if domain:
                domains.add(domain)
                
        # 兜底处理纯文本
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
