import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timezone, timedelta
import time
import logging
from tqdm import tqdm
from typing import List, Dict, Optional, Generator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

START_DATE = datetime(2025, 1, 1, tzinfo=timezone.utc)
END_DATE = datetime(2025, 9, 30, 23, 59, 59, tzinfo=timezone.utc)
START_DATE_FILTER = datetime(2024, 12, 1, tzinfo=timezone.utc)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

FIRM_KEYWORDS = [
    "vcb", "hpg", "fpt", "vic", "vnm", "bid", "ctg", "mwg", "ssi", "tcb",
    "vpb", "mbb", "acb", "eib", "stb", "hdb", "vib", "gas", "plx", "pow",
    "gvr", "vre", "vhm", "msn", "sab", "bvh", "tpb", "pdr", "nvl", "kdh"
]
MACRO_KEYWORDS = [
    "lai-suat", "lam-phat", "gdp", "tang-truong-kinh-te", "ty-gia",
    "chinh-sach-tien-te", "vnd", "usd", "vn-index", "vnindex",
    "chung-khoan", "ngan-hang-nha-nuoc", "trai-phieu", "co-phieu"
]
ALL_KEYWORDS_FILTER = FIRM_KEYWORDS + MACRO_KEYWORDS

RE_SITEMAP_OUT_OF_RANGE = re.compile(
 r'(20[0-1][0-9]|202[0-3])' # 2000-2023
 r'|(2024)' # 2024
 r'|-(2025)-(10|11|12)' # Dạng -2025-10
 r'_(2025)_(10|11|12)' # Dạng _2025_10
 r'-2025-10-|-2025-11-|-2025-12-'# Dạng 2025-10- (của cafef)
)

RE_SITEMAP_JUNK = re.compile(
    r'google-news-sitemap\.xml|'
    r'latest-news-sitemap\.xml|'
    r'latestnews-sitemap\.xml|'
    r'category\.rss|'
    r'category-sitemap\.xml|'
    r'sitemaparticles-site|'
    r'category_sitemap|'
    r'topics\.xml|'
    r'event-sitemap\.xml|'
    r'categories\.xml'
)

RE_CAFEF_ARTICLE = re.compile(r'-\d{10,}\.chn$')


def get_soup(url: str) -> Optional[BeautifulSoup]:
    try:
        # Tăng timeout lên 30s cho mạng chậm
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()

        # --- SỬA LỖI WARNING: TỰ ĐỘNG CHỌN PARSER ---
        # Nếu link là .xml hoặc có chữ 'sitemap' -> Dùng 'xml' parser
        if url.endswith('.xml') or 'sitemap' in url:
            return BeautifulSoup(response.content, 'xml')

        # Các trường hợp còn lại (bài báo) -> Dùng 'lxml' parser (HTML)
        else:
            return BeautifulSoup(response.text, 'lxml')

    except requests.RequestException:
        return None

def _parse_datetime_sitemap(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str).astimezone(timezone.utc)
    except ValueError:
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            return None

def parse_sitemap_links(sitemap_url: str) -> Generator[str, None, None]:
    soup = get_soup(sitemap_url)
    if not soup:
        return

    is_sitemap_index = soup.find('sitemapindex')
    entries = soup.find_all('url')
    if not entries:
        entries = soup.find_all('sitemap')

    for entry in entries:
        loc_tag = entry.find('loc')
        if not loc_tag:
            continue

        url = loc_tag.text.strip()
        lastmod_tag = entry.find('lastmod')
        lastmod_date = None

        if lastmod_tag and lastmod_tag.text:
            lastmod_date = _parse_datetime_sitemap(lastmod_tag.text.strip())

        if lastmod_date:
            if lastmod_date < START_DATE_FILTER or lastmod_date > END_DATE:
                continue

        if not is_sitemap_index:
            url_lower = url.lower()
            if not any(keyword in url_lower for keyword in ALL_KEYWORDS_FILTER):
                continue

        yield url


def parse_sitemap(sitemap_url: str) -> Generator[str, None, None]:
    if RE_SITEMAP_JUNK.search(sitemap_url):
        logging.warning(f"Bỏ qua sitemap rác/không liên quan: {sitemap_url}")
        return

    if RE_SITEMAP_OUT_OF_RANGE.search(sitemap_url):
        logging.warning(f"Bỏ qua sitemap ngoài phạm vi (lọc theo tên): {sitemap_url}")
        return

    soup = get_soup(sitemap_url)
    if not soup:
        return

    if soup.find('sitemapindex'):
        logging.info(f"Phân tích Sitemap Index: {sitemap_url}")
        for child_sitemap_url in parse_sitemap_links(sitemap_url):
            yield from parse_sitemap(child_sitemap_url)
    else:
        logging.info(f"Phân tích Sitemap Links: {sitemap_url}")
        for article_url in parse_sitemap_links(sitemap_url):
            yield article_url


def _parse_datetime_meta(iso_date_str: str) -> Optional[datetime]:
    if not iso_date_str:
        return None
    try:
        return datetime.fromisoformat(iso_date_str).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def process_article(url: str, selectors: Dict[str, str], date_parser) -> Optional[Dict]:
    soup = get_soup(url)
    if not soup:
        return None

    title = None
    timestamp = None

    try:
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            title = og_title['content'].strip()

        if not title:
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.text.strip()
                if '|' in title:
                    title = title.split('|')[0].strip()
                if ' - ' in title:
                    parts = title.split(' - ')
                    if len(parts) > 1 and len(parts[-1]) < 25:
                        title = ' - '.join(parts[:-1]).strip()

        if not title:
            title_element = soup.select_one(selectors['title'])
            if title_element:
                title = title_element.text.strip()

        meta_time = soup.find('meta', property='article:published_time')
        if meta_time and meta_time.get('content'):
            timestamp = _parse_datetime_meta(meta_time['content'])

        if not timestamp:
            time_element = soup.select_one(selectors['time'])
            if time_element:
                if time_element.has_attr('datetime'):
                    timestamp = _parse_datetime_meta(time_element['datetime'])

                if not timestamp:
                    time_str = time_element.text.strip()
                    timestamp_naive = date_parser(time_str)
                    if timestamp_naive:
                        try:
                            timestamp = timestamp_naive.replace(tzinfo=timezone(timedelta(hours=7))).astimezone(
                                timezone.utc)
                        except:
                            timestamp = timestamp_naive.replace(tzinfo=timezone.utc)

        if not title or not timestamp:
            return None

        if (START_DATE <= timestamp <= END_DATE):
            return {
                'source': selectors['source_name'],
                'url': url,
                'title': title,
                'timestamp': timestamp.isoformat()
            }

    except Exception as e:
        logging.error(f"Lỗi khi xử lý bài viết {url}: {e}")

    return None


def scrape_cafef() -> List[Dict]:
    SOURCE_NAME = "CafeF"
    SITEMAPS = ['https://cafef.vn/sitemap.xml']
    SELECTORS = {
        'title': 'h1.title, h1.title-top-focus',
        'time': 'span.pdate, span.time-top-focus, span.date, span.time-source-detail',
        'source_name': SOURCE_NAME
    }

    def _parse_date(date_str: str) -> Optional[datetime]:
        clean_date_str = date_str.split(' (')[0].strip()
        try:
            return datetime.strptime(clean_date_str, '%d-%m-%Y - %H:%M %p')
        except ValueError:
            try:
                return datetime.strptime(clean_date_str, '%d/%m/%Y %H:%M')
            except ValueError:
                return None

    articles = []
    processed_urls = set()
    for sitemap in SITEMAPS:
        for url in parse_sitemap(sitemap):
            if not RE_CAFEF_ARTICLE.search(url):
                continue
            if url not in processed_urls:
                article = process_article(url, SELECTORS, _parse_date)
                if article:
                    articles.append(article)
                processed_urls.add(url)
                time.sleep(0.05)
    logging.info(f"Hoàn tất {SOURCE_NAME}, tìm thấy {len(articles)} bài viết.")
    return articles


def scrape_cafebiz() -> List[Dict]:
    SOURCE_NAME = "CafeBiz"
    SITEMAPS = ['https://cafebiz.vn/sitemap.xml']
    SELECTORS = {
        'title': 'h1.title, h1.title-top-focus',
        'time': 'span.time, span.pdate, span.time-top-focus, span.date',
        'source_name': SOURCE_NAME
    }

    def _parse_date(date_str: str) -> Optional[datetime]:
        clean_date_str = date_str.split(' (')[0].strip()
        try:
            return datetime.strptime(clean_date_str, '%d/%m/%Y %H:%M %p')
        except ValueError:
            try:
                return datetime.strptime(clean_date_str, '%d/%m/%Y %H:%M')
            except ValueError:
                return None

    articles = []
    processed_urls = set()
    for sitemap in SITEMAPS:
        for url in parse_sitemap(sitemap):
            if not RE_CAFEF_ARTICLE.search(url):
                continue
            if url not in processed_urls:
                article = process_article(url, SELECTORS, _parse_date)
                if article:
                    articles.append(article)
                processed_urls.add(url)
                time.sleep(0.05)
    logging.info(f"Hoàn tất {SOURCE_NAME}, tìm thấy {len(articles)} bài viết.")
    return articles


def scrape_vietstock() -> List[Dict]:
    SOURCE_NAME = "Vietstock"
    SITEMAPS = ['https://vietstock.vn/sitemap.xml']
    SELECTORS = {
        'title': 'h1.article-title',
        'time': 'span.date',
        'source_name': SOURCE_NAME
    }

    def _parse_date(date_str: str) -> Optional[datetime]:
        try:
            return datetime.strptime(date_str.strip(), '%d/%m/%Y %H:%M')
        except ValueError:
            return None

    articles = []
    processed_urls = set()
    for sitemap in SITEMAPS:
        for url in parse_sitemap(sitemap):
            if url not in processed_urls:
                article = process_article(url, SELECTORS, _parse_date)
                if article:
                    articles.append(article)
                processed_urls.add(url)
                time.sleep(0.05)
    logging.info(f"Hoàn tất {SOURCE_NAME}, tìm thấy {len(articles)} bài viết.")
    return articles


def scrape_vneconomy() -> List[Dict]:
    SOURCE_NAME = "VnEconomy"
    SITEMAPS = ['https://vneconomy.vn/sitemap.xml']
    SELECTORS = {
        'title': 'h1.name-detail',
        'time': 'p.date',
        'source_name': SOURCE_NAME
    }

    def _parse_date(date_str: str) -> Optional[datetime]:
        try:
            return datetime.strptime(date_str.strip(), '%d/%m/%Y, %H:%M')
        except ValueError:
            return None

    articles = []
    processed_urls = set()
    for sitemap in SITEMAPS:
        for url in parse_sitemap(sitemap):
            if url not in processed_urls:
                article = process_article(url, SELECTORS, _parse_date)
                if article:
                    articles.append(article)
                processed_urls.add(url)
                time.sleep(0.05)
    logging.info(f"Hoàn tất {SOURCE_NAME}, tìm thấy {len(articles)} bài viết.")
    return articles


def scrape_baodautu() -> List[Dict]:
    SOURCE_NAME = "Bao Dau tu"
    SITEMAPS = ['https://baodautu.vn/sitemap.xml']
    SELECTORS = {
        'title': 'div.title-detail',
        'time': 'span.post-time',
        'source_name': SOURCE_NAME
    }

    def _parse_date(date_str: str) -> Optional[datetime]:
        try:
            clean_date_str = date_str.strip(' -')
            return datetime.strptime(clean_date_str, '%d/%m/%Y %H:%M')
        except ValueError:
            return None

    articles = []
    processed_urls = set()
    for sitemap in SITEMAPS:
        for url in parse_sitemap(sitemap):
            if url not in processed_urls:
                article = process_article(url, SELECTORS, _parse_date)
                if article:
                    articles.append(article)
                processed_urls.add(url)
                time.sleep(0.05)
    logging.info(f"Hoàn tất {SOURCE_NAME}, tìm thấy {len(articles)} bài viết.")
    return articles


def scrape_nhadautu() -> List[Dict]:
    SOURCE_NAME = "Nha dau tu"
    SITEMAPS = ['https://nhadautu.vn/sitemap.xml']
    SELECTORS = {
        'title': 'h1#title_detail_check',
        'time': 'div.t.mr-3',
        'source_name': SOURCE_NAME
    }

    def _parse_date(date_str: str) -> Optional[datetime]:
        try:
            return datetime.strptime(date_str.strip(), '%H:%M %d/%m/%Y')
        except ValueError:
            return None

    articles = []
    processed_urls = set()
    for sitemap in SITEMAPS:
        for url in parse_sitemap(sitemap):
            if url not in processed_urls:
                article = process_article(url, SELECTORS, _parse_date)
                if article:
                    articles.append(article)
                processed_urls.add(url)
                time.sleep(0.05)
    logging.info(f"Hoàn tất {SOURCE_NAME}, tìm thấy {len(articles)} bài viết.")
    return articles


def scrape_tinnhanhchungkhoan() -> List[Dict]:
    SOURCE_NAME = "Tin nhanh chung khoan"
    SITEMAPS = ['https://www.tinnhanhchungkhoan.vn/sitemap.xml']
    SELECTORS = {
        'title': 'h1.article__header.cms-title',
        'time': 'time.time',
        'source_name': SOURCE_NAME
    }

    def _parse_date(date_str: str) -> Optional[datetime]:
        try:
            return datetime.strptime(date_str.strip(), '%d/%m/%Y %H:%M')
        except ValueError:
            return None

    articles = []
    processed_urls = set()
    for sitemap in SITEMAPS:
        for url in parse_sitemap(sitemap):
            if url not in processed_urls:
                article = process_article(url, SELECTORS, _parse_date)
                if article:
                    articles.append(article)
                processed_urls.add(url)
                time.sleep(0.05)
    logging.info(f"Hoàn tất {SOURCE_NAME}, tìm thấy {len(articles)} bài viết.")
    return articles

def scrape_thoibaotaichinh() -> List[Dict]:
    SOURCE_NAME = "Thoi bao tai chinh"
    SITEMAPS = ['https://thoibaotaichinhvietnam.vn/sitemap_site_1.xml']
    SELECTORS = {
        'title': 'h1.post-title',
        'time': 'span.format_date',
        'source_name': SOURCE_NAME
    }

    def _parse_date(date_str: str) -> Optional[datetime]:
        try:
            return datetime.strptime(date_str.strip(), '%d/%m/%Y')
        except ValueError:
            return None

    articles = []
    processed_urls = set()
    for sitemap in SITEMAPS:
        for url in parse_sitemap(sitemap):
            if url not in processed_urls:
                article = process_article(url, SELECTORS, _parse_date)
                if article:
                    articles.append(article)
                processed_urls.add(url)
                time.sleep(0.05)
    logging.info(f"Hoàn tất {SOURCE_NAME}, tìm thấy {len(articles)} bài viết.")
    return articles

def scrape_kinhtedothi() -> List[Dict]:
    SOURCE_NAME = "Kinh te do thi"
    SITEMAPS = ['https://kinhtedothi.vn/sitemap.xml']
    SELECTORS = {
        'title': 'h1.article-title',
        'time': 'div.article-published-on',
        'source_name': SOURCE_NAME
    }

    def _parse_date(date_str: str) -> Optional[datetime]:
        try:
            clean_str = re.sub(r'^\w+,\s*', '', date_str, flags=re.IGNORECASE)
            return datetime.strptime(clean_str, '%H:%M %d/%m/%Y')
        except ValueError:
            return None

    articles = []
    processed_urls = set()
    for sitemap in SITEMAPS:
        for url in parse_sitemap(sitemap):
            if url not in processed_urls:
                article = process_article(url, SELECTORS, _parse_date)
                if article:
                    articles.append(article)
                processed_urls.add(url)
                time.sleep(0.05)
    logging.info(f"Hoàn tất {SOURCE_NAME}, tìm thấy {len(articles)} bài viết.")
    return articles

def run_all_scrapers() -> List[Dict]:
    all_articles = []
    scraper_functions = [
        scrape_cafef, scrape_cafebiz, scrape_vietstock, scrape_vneconomy,
        scrape_baodautu, scrape_nhadautu, scrape_tinnhanhchungkhoan,
        scrape_thoibaotaichinh, scrape_kinhtedothi,
    ]

    for func in tqdm(scraper_functions, desc="Đang cào dữ liệu các trang"):
        logging.info(f"--- Bắt đầu chạy {func.__name__} ---")
        try:
            articles = func()
            all_articles.extend(articles)
            logging.info(f"--- Hoàn tất {func.__name__}, tìm thấy {len(articles)} bài ---")
        except Exception as e:
            logging.error(f"Lỗi nghiêm trọng khi chạy {func.__name__}: {e}")

    logging.info(f"*** HOÀN TẤT TOÀN BỘ QUÁ TRÌNH, TỔNG CỘNG {len(all_articles)} BÀI VIẾT ***")
    return all_articles