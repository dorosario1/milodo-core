SKILL_NAME = "web_learner"
SKILL_DESCRIPTION = "Collecte des tendances web/design/dev et les injecte dans le genome MILODO."
SKILL_VERSION = "1.0.0"
EXECUTION_PROFILE = "web"

import json
import re
import urllib.request
from html.parser import HTMLParser


class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._current = None

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return

        attrs_dict = dict(attrs)
        href = attrs_dict.get("href", "")

        if href:
            self._current = {
                "title": "",
                "url": href,
            }

    def handle_data(self, data):
        if self._current is not None:
            self._current["title"] += data

    def handle_endtag(self, tag):
        if tag == "a" and self._current is not None:
            title = _clean_text(self._current.get("title", ""))

            if title:
                self._current["title"] = title
                self.links.append(self._current)

            self._current = None


class WebLearner:
    def __init__(self):
        self.timeout = 12
        self.user_agent = "MILODO-WebLearner/1.0"

    def fetch_dribbble_trends(self):
        html = self._fetch("https://dribbble.com/shots/popular/web-design")
        links = self._extract_links(html, "https://dribbble.com")
        trends = self._filter_links(links, ["design", "website", "landing", "ui", "ux"], 12)
        return self._result("dribbble", trends)

    def fetch_github_trending(self):
        html = self._fetch("https://github.com/trending")
        links = self._extract_links(html, "https://github.com")
        trends = []

        for link in links:
            url = link.get("url", "")

            if re.fullmatch(r"https://github\.com/[^/]+/[^/#?]+", url):
                trends.append(link)

            if len(trends) >= 12:
                break

        return self._result("github_trending", trends)

    def fetch_hacker_news(self):
        html = self._fetch("https://news.ycombinator.com/")
        links = self._extract_links(html, "https://news.ycombinator.com/")
        trends = self._filter_links(links, ["ai", "web", "design", "startup", "developer", "software"], 12)
        return self._result("hacker_news", trends)

    def fetch_arxiv_ai(self):
        xml = self._fetch(
            "https://export.arxiv.org/api/query?search_query=cat:cs.AI&sortBy=submittedDate&sortOrder=descending&max_results=10"
        )
        entries = []

        for entry in re.findall(r"<entry>(.*?)</entry>", xml, re.DOTALL | re.IGNORECASE):
            title_match = re.search(r"<title>(.*?)</title>", entry, re.DOTALL | re.IGNORECASE)
            link_match = re.search(r'<id>(.*?)</id>', entry, re.DOTALL | re.IGNORECASE)

            if title_match:
                entries.append({
                    "title": _clean_text(title_match.group(1)),
                    "url": _clean_text(link_match.group(1)) if link_match else "",
                })

        return self._result("arxiv_ai", entries)

    def fetch_css_techniques(self):
        html = self._fetch("https://css-tricks.com/")
        links = self._extract_links(html, "https://css-tricks.com")
        trends = self._filter_links(links, ["css", "layout", "grid", "flex", "animation", "design"], 12)
        return self._result("css_techniques", trends)

    def inject_into_genome(self):
        payload = {
            "dribbble": self.fetch_dribbble_trends(),
            "github": self.fetch_github_trending(),
            "hacker_news": self.fetch_hacker_news(),
            "arxiv_ai": self.fetch_arxiv_ai(),
            "css": self.fetch_css_techniques(),
        }
        path = ".milodo/genome/web_learner.json"

        try:
            with open(path, "w", encoding="utf-8") as file:
                json.dump(payload, file, indent=2, ensure_ascii=False)
                file.write("\n")

            return {
                "success": True,
                "path": path,
                "data": payload,
            }
        except Exception as error:
            return {
                "success": False,
                "path": path,
                "error": str(error),
                "data": payload,
            }

    def _fetch(self, url):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xml,application/xhtml+xml",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                encoding = response.headers.get_content_charset() or "utf-8"
                return raw.decode(encoding, errors="replace")
        except Exception:
            return ""

    def _extract_links(self, html, base_url):
        parser = _LinkParser()
        parser.feed(html or "")
        output = []
        seen = set()

        for link in parser.links:
            title = _clean_text(link.get("title", ""))
            url = _absolute_url(link.get("url", ""), base_url)

            if not title or not url or url in seen:
                continue

            seen.add(url)
            output.append({
                "title": title,
                "url": url,
            })

        return output

    def _filter_links(self, links, keywords, limit):
        output = []

        for link in links:
            text = f"{link.get('title', '')} {link.get('url', '')}".lower()

            if any(keyword in text for keyword in keywords):
                output.append(link)

            if len(output) >= limit:
                break

        if output:
            return output

        return links[:limit]

    def _result(self, source, items):
        return {
            "success": True,
            "source": source,
            "count": len(items),
            "items": items,
        }


def run(action="inject_into_genome", **kwargs):
    learner = WebLearner()

    if not hasattr(learner, action):
        return {
            "success": False,
            "error": f"Action inconnue : {action}",
        }

    method = getattr(learner, action)
    return method()


def _clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _absolute_url(url, base_url):
    if not url:
        return ""

    if url.startswith("http://") or url.startswith("https://"):
        return url

    if url.startswith("//"):
        return "https:" + url

    if url.startswith("/"):
        return base_url.rstrip("/") + url

    return url
