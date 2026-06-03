def extract_domain(href: str) -> str | None:
    """
    从 href 或纯文本中提取规范化的裸域名。
    1. 彻底剔除含有中文等非法字符的整级域名块。
    2. 智能提取根域名，自动切除无用的前缀子域名（如 cang.45678998.xyz -> 45678998.xyz）。
    """
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
            # 如果是 sub.example.com.cn，切掉多余前缀，只保留最后 3 块 -> example.com.cn
            clean_parts = clean_parts[-3:]
        else:
            # 如果是 cang.45678998.xyz 或 123.leileisi3.xyz，只保留最后 2 块 -> 45678998.xyz
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
