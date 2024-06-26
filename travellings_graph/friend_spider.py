import datetime
import re
import json
import os
from typing import Any, Generator, Iterable
import scrapy
from scrapy.crawler import CrawlerProcess
import urllib3
import urllib3.util
from travellings_graph.domain_utils import cross_domain, host_or_sub_in_list
from travellings_graph.member_list import download_members, read_members

FRIEND_LINKS_NAME_KEYWORDS = [
    "友情",
    "friend",
    "友链",
    "友人",
    "朋友",
    "左邻右舍",
    "友邻",
]
FRIEND_LINKS_NAME_LENGTH_LIMIT = 10  # 最大（可达到）的指向友链页面的链接名长度
FRIEND_LINKS_URL_PREFIXS = [
    "/link",
    "/friend",
    "/links",
    "/friends",
    "/%e5%8f%8b%e4%ba%ba%e5%b8%90",  # /友人帐
]
HOMEPAGE_CONTINUTE_KEYWORDS = ["博客", "blog"]
FRIEND_BOX_SELECTOR = [
    '*[itemprop="articleBody"]',  # https://schema.org/Article
    ".link-box",  # https://get233.com/archives/mirages-intro.html
    ".post-body",  # https://theme-next.js.org/
    ".post-content",
    ".post",
    ".content",
    "article",
    ".article-container",  # https://github.com/jerryc127/hexo-theme-butterfly
    "main",
    ".main-wrapper",
    ".main-content",  # https://github.com/nineya/halo-theme-dream
    "body",  # fallback
]

FRIEND_LINKS_DENY_HOSTS = set(
    [
        "travellings.link",
        "travellings.cn",
        "gov.moe",
        "travel.moe",
        "gov.cn",
        "foreverblog.cn",
        "aliyun.com",
        "github.com",
        "twitter.com",
        "telegram.me",
        "t.me",
        "typecho.org",
        "creativecommons.org",
        "weibo.com",
        "gitee.io",
        "qlogo.cn",
        "gravatar.com",
        "cravatar.cn",
        "hexo.io",
        "bilibili.com",
        "zhihu.com",
        "qq.com",
        "langchain.com",
        "youtube.com",
    ]
)


def extract_url_from_elem(elem: scrapy.Selector):
    urls_from_elem = elem.re(
        ""  # extract urls from script, which is used for some random-order links
        + r"\"https?://[-A-Za-z0-9+&@#/%?=~_|!:,.;]+[-A-Za-z0-9+&@#/%=~_|]\""
        + "|"
        + r"\'https?://[-A-Za-z0-9+&@#/%?=~_|!:,.;]+[-A-Za-z0-9+&@#/%=~_|]\'"
    )
    for url_str in urls_from_elem:
        url_str = url_str[1:-1]
        yield url_str


class FriendSpider(scrapy.Spider):
    name = "FriendSpider"
    start_urls = []

    def __init__(self):
        super().__init__()
        download_members()
        self.members = read_members()

    def start_requests(self) -> Iterable[scrapy.Request]:
        for member in self.members:
            yield scrapy.Request(
                member.url, dont_filter=True, cb_kwargs={"start": member.url}
            )

    def parse(self, response, **kwargs):
        yield from self.parse_homepage(response, **kwargs)

    def url_to_handle(
        self, url: str | urllib3.util.Url, url_from: str | urllib3.util.Url
    ):
        if isinstance(url, str):
            url = urllib3.util.parse_url(url)
        if isinstance(url_from, str):
            url_from = urllib3.util.parse_url(url_from)
        if url.scheme not in ["http", "https"]:
            return False
        if url.host is not None and host_or_sub_in_list(
            url.host, FRIEND_LINKS_DENY_HOSTS
        ):
            return False
        if url.path is not None:
            if url.path.startswith("/avatar") or url.path.startswith("/gravatar"):
                return False
            if any(
                url.path.endswith(ext)
                for ext in [".jpg", ".png", ".gif", ".jpeg", ".webp", ".svg"]
            ):
                return False
        return True

    def parse_homepage(self, response, **kwargs):
        start_url = kwargs.get("start", response.url)
        url_from = urllib3.util.parse_url(response.url)

        if response.status != 200:
            yield {"kind": "no_friends_page", "start": start_url, "from": response.url}
            return
        if not response.headers.get("Content-Type", b"").startswith(b"text/html"):
            yield {"kind": "no_friends_page", "start": start_url, "from": response.url}
            return

        for policy_stage in range(2):
            visited = set()
            for elem in response.css("a[href]"):
                elem: scrapy.Selector = elem
                url_str = response.urljoin(elem.attrib["href"])
                url = urllib3.util.parse_url(url_str)
                if not self.url_to_handle(url, url_from):
                    continue
                if cross_domain(url, url_from):  # avoid cross-domain
                    continue

                # avoid duplicate urls in the same page
                if url_str in visited:
                    continue
                visited.add(url_str)

                if policy_stage == 0:  # try to find by url path (this is more accurate)
                    if url.path is not None:
                        if any(
                            keyword in url.path.removesuffix(".html").removesuffix("/")
                            for keyword in FRIEND_LINKS_URL_PREFIXS
                        ):
                            yield response.follow(
                                url_str,
                                self.parse_friends_page,
                                cb_kwargs={"start": start_url},
                            )
                            return
                elif policy_stage == 1:  # if no url path matched, try to find by title
                    title_str = "".join(elem.css("::text").getall()).strip()
                    if (
                        title_str is not None
                        and len(title_str) <= FRIEND_LINKS_NAME_LENGTH_LIMIT
                    ):
                        if any(
                            keyword in title_str
                            for keyword in FRIEND_LINKS_NAME_KEYWORDS
                        ):
                            yield response.follow(
                                url_str,
                                self.parse_friends_page,
                                cb_kwargs={"start": start_url},
                            )
                            return

        # if no friend link found, try to find next page (eg. homepage --> blog)
        for elem in response.css("a[href]"):
            url_str = response.urljoin(elem.attrib["href"])
            title_str = "".join(elem.css("::text").getall()).strip()
            if title_str is not None:
                if any(keyword in title_str for keyword in HOMEPAGE_CONTINUTE_KEYWORDS):
                    yield response.follow(
                        url_str, self.parse_homepage, cb_kwargs={"start": start_url}
                    )
                    return

        # Brute force: try some subdomains
        if kwargs.get("allow_brute_force", True):
            # try to use @ www. or blog. to access
            if url_from.host is None or url_from.scheme is None:
                # Skip
                pass
            elif url_from.host.startswith("www."):
                yield response.follow(
                    url_from.scheme + "://blog." + url_from.host[4:],
                    self.parse_homepage,
                    cb_kwargs={"start": start_url, "allow_brute_force": False},
                )
                yield response.follow(
                    url_from.scheme + "://" + url_from.host[4:],
                    self.parse_homepage,
                    cb_kwargs={"start": start_url, "allow_brute_force": False},
                )
            elif url_from.host.startswith("blog."):
                yield response.follow(
                    url_from.scheme + "://" + url_from.host[5:],
                    self.parse_homepage,
                    cb_kwargs={"start": start_url, "allow_brute_force": False},
                )
                yield response.follow(
                    url_from.scheme + "://www." + url_from.host[5:],
                    self.parse_homepage,
                    cb_kwargs={"start": start_url, "allow_brute_force": False},
                )
            else:
                yield response.follow(
                    url_from.scheme + "://blog." + url_from.host,
                    self.parse_homepage,
                    cb_kwargs={"start": start_url, "allow_brute_force": False},
                )
                yield response.follow(
                    url_from.scheme + "://www." + url_from.host,
                    self.parse_homepage,
                    cb_kwargs={"start": start_url, "allow_brute_force": False},
                )

        if url_from.host is not None and url_from.scheme is not None:
            # Brute force: try to access /links or /friends directly
            response.follow(
                url_from.scheme + "://" + url_from.host + "/links",
                self.parse_friends_page,
                cb_kwargs={"start": start_url, "allow_brute_force": False},
            )
            response.follow(
                url_from.scheme + "://" + url_from.host + "/friends",
                self.parse_friends_page,
                cb_kwargs={"start": start_url, "allow_brute_force": False},
            )

        yield {"kind": "no_friends_page", "start": start_url, "from": response.url}

    def parse_friends_page(self, response, **kwargs):
        start_url = kwargs.get("start", response.url)
        if b"%c Mix Space %c https://github.com/mx-space" in response.body:
            yield {
                "kind": "friends_page",
                "start": start_url,
                "target": response.url,
            }
            iterator = self.try_parse_friend_page_mix_space_index(response, **kwargs)
            while True:
                try:
                    yield next(iterator)
                except StopIteration as e:
                    if e.value is True:
                        return
                    break

        yield from self.parse_friends_page_generic(response, **kwargs)

    def parse_friends_page_generic(self, response, **kwargs):
        start_url = kwargs.get("start", response.url)
        url_from = urllib3.util.parse_url(response.url)

        if response.status != 200:
            yield {
                "kind": "no_friends_link",
                "start": start_url,
                "from": response.url,
            }
            return
        if not response.headers.get("Content-Type", b"").startswith(b"text/html"):
            yield {
                "kind": "no_friends_link",
                "start": start_url,
                "from": response.url,
            }
            return

        yield {
            "kind": "friends_page",
            "start": start_url,
            "target": response.url,
        }

        visited_host = set()
        visited_host.add(url_from.host)

        for cur_selector in FRIEND_BOX_SELECTOR:
            root_elems = response.css(cur_selector)
            has_friend_link = False
            for root_elem in root_elems:
                urls_str = root_elem.css("a[href]::attr(href)").getall()
                urls_str += root_elem.css(
                    "div[hrefs]::attr(hrefs)"
                ).getall()  # for typecho-bearsimple

                for elem in root_elem.css("script"):
                    elem: scrapy.Selector = elem
                    urls_str += list(extract_url_from_elem(elem))

                for url_str in urls_str:
                    url = urllib3.util.parse_url(url_str)
                    if not self.url_to_handle(url, url_from):
                        continue

                    # avoid duplicate host
                    if url.host in visited_host:
                        continue
                    visited_host.add(url.host)

                    has_friend_link = True
                    yield {
                        "kind": "friends_link",
                        "start": start_url,
                        "from": response.url,
                        "target": url_str,
                        "selector": cur_selector,
                    }

            if has_friend_link:
                # if we found friend link in this selector, we don't need to try other selectors
                break

        if not has_friend_link:
            yield {
                "kind": "no_friends_link",
                "start": start_url,
                "from": response.url,
            }

    def try_parse_friend_page_mix_space_index(
        self, response, **kwargs
    ) -> Generator[Any, None, bool]:
        patterns = [
            r"\"NEXT_PUBLIC_API_URL\"\s*:\s*\"([^\"]*)\"",
            r"\\\"NEXT_PUBLIC_API_URL\\\"\s*:\s*\\\"([^\"]*)\\\"",
            r'<meta\s+name="api_url"\s+content="([^\"]*)"\/?\s*>',
        ]
        body_str = response.body.decode("utf-8")
        start_url = kwargs.get("start", response.url)
        for pattern in patterns:
            api_url = re.findall(pattern, body_str)
            if len(api_url) == 0:
                continue
            api_url = api_url[0]
            links_url = api_url + "/links/all"
            yield response.follow(
                links_url,
                self.parse_friend_page_mix_space_data,
                cb_kwargs={"start": start_url},
            )
            return True
        return False

    def parse_friend_page_mix_space_data(self, response, **kwargs):
        start_url = kwargs.get("start", response.url)
        if response.status != 200:
            return
        if not response.headers.get("Content-Type", b"").startswith(
            b"application/json"
        ):
            return
        json_data = json.loads(response.body.decode("utf-8"))
        if "data" not in json_data:
            return
        for link in json_data["data"]:
            yield {
                "kind": "friends_link",
                "start": start_url,
                "from": response.url,
                "target": link["url"],
                "selector": "::mix_space",
            }


def run_spider():
    if os.path.exists("friends.lines.json"):
        bak_time = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
        os.rename("friends.lines.json", f"friends.lines.json.bak.{bak_time}")
    user_agent = " ".join(
        [
            "Mozilla/5.0 (Linux x86_64)",
            "AppleWebKit/537.36 (KHTML, like Gecko)",
            "Chrome/124.0.0.0",
            "Safari/537.36",
            "TravellingsGraph/0.1 (Travellings.cn)",
        ]
    )
    process = CrawlerProcess(
        {
            "USER_AGENT": user_agent,
            "FEED_FORMAT": "jsonlines",
            "FEED_URI": "friends.lines.json",
        }
    )
    process.crawl(FriendSpider)
    process.start()


if __name__ == "__main__":
    run_spider()
