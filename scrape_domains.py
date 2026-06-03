#!/usr/bin/env python3
"""
从网站抓取 NSFW 域名，追加到 domains.txt

scrapeUrls.txt 格式：
  https://example.com              ← 使用默认 class "visit-icon"
  https://example.com | my-class   ← 指定自定义 class
  # 这是注释行，会被跳过
"""
import os
import re
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

def extract_clean_domain(target_string):
    """
    Cleans up a string (URL or text) and extracts just the valid domain name.
    """
    if not target_string:
        return None
        
    target_string = target_string.strip().lower()
    
    if target_string.startswith('//'):
        target_string = 'http:' + target_string
        
    if target_string.startswith(('http://', 'https://')):
        parsed = urlparse(target_string)
        domain = parsed.netloc
    else:
        if '/' in target_string:
            parsed = urlparse('http://' + target_string)
            domain = parsed.netloc
        else:
            domain = target_string

    domain = domain.split(':')[0]
    
    if domain.startswith('www.'):
        domain = domain[4:]

    # Strict regex check to ensure it's a valid domain format
    domain_regex = re.compile(r'^([a-z0-9]+(-[a-z0-9]+)*\.)+[a-z]{2,}$')
    if domain_regex.match(domain):
        return domain
        
    return None

def main():
    if not os.path.exists('scrapeUrls.txt'):
        print("未找到 scrapeUrls.txt")
        return

    with open('scrapeUrls.txt', 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]

    all_scraped_domains = []
    total_urls = len(lines)

    for idx, line in enumerate(lines, 1):
        # Support both "|" and " " split formats just in case
        if '|' in line:
            url, css_class = line.split('|', 1)
        elif ',' in line:
            url, css_class = line.split(',', 1)
        else:
            url = line
            css_class = 'visit-icon'
            
        url = url.strip()
        css_class = css_class.strip()
        
        print(f"[{idx}/{total_urls}] 抓取: {url}")
        print(f"    请求: {url}  [class='{css_class}']")

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            
            soup = BeautifulSoup(response.text, 'html.parser')
            elements = soup.find_all(class_=css_class)
            
            site_domains = []
            for el in elements:
                # ── 核心升级：深度提取容器内部数据 ──────────────────
                
                # 1. 寻找容器内所有的 <a> 标签链接
                inner_links = el.find_all('a')
                if inner_links:
                    for link in inner_links:
                        target = link.get('href') or link.text
                        clean_domain = extract_clean_domain(target)
                        if clean_domain:
                            site_domains.append(clean_domain)
                
                # 2. 如果容器内是纯文本或者错综复杂的排版，使用正则抓取所有域名格式的字符串
                # 这个正则可以完美捞出文本中形如 "abc.com" 或 "xyz.net" 的内容
                text_matches = re.findall(r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}', el.text)
                for match in text_matches:
                    clean_domain = extract_clean_domain(match)
                    if clean_domain:
                        site_domains.append(clean_domain)
                        
                # 3. 保底兜底：如果是扁平元素，直接处理元素本身
                if not inner_links and not text_matches:
                    target = el.get('href') or el.text
                    clean_domain = extract_clean_domain(target)
                    if clean_domain:
                        site_domains.append(clean_domain)
            
            unique_site_domains = list(set(site_domains))
            print(f"    → 找到 {len(unique_site_domains)} 个域名")
            all_scraped_domains.extend(unique_site_domains)

        except Exception as e:
            print(f"    ❌ 抓取失败 {url}: {e}")

    if all_scraped_domains:
        all_scraped_domains = list(set(all_scraped_domains))
        with open('domains.txt', 'a', encoding='utf-8') as f:
            for domain in all_scraped_domains:
                f.write(f"{domain}\n")
        print(f"\n✓ 合计 {len(all_scraped_domains)} 个域名已追加至 domains.txt")

if __name__ == '__main__':
    main()
