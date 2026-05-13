SKILL_NAME = "web_learner"
SKILL_DESCRIPTION = "Collecte des tendances web/design/dev via APIs publiques et enrichit le genome MILODO."
SKILL_VERSION = "2.0.0"
EXECUTION_PROFILE = "web"

import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path


class WebLearner:
    def __init__(self):
        self.timeout = 15
        self.headers = {
            "Accept": "application/json",
            "User-Agent": "MILODO-WebLearner/2.0"
        }

    def _request(self, url):
        """
        Retourne la réponse brute en texte.
        Gère les erreurs réseau.
        """

        try:
            import ssl

            request = urllib.request.Request(
                url,
                headers=self.headers
            )

            with urllib.request.urlopen(
                request,
                timeout=self.timeout,
                context=ssl._create_unverified_context()
            ) as response:
                raw = response.read()
                encoding = (
                    response.headers.get_content_charset()
                    or "utf-8"
                )
                return raw.decode(
                    encoding,
                    errors="replace"
                )

        except Exception as error:
            return {
                "success": False,
                "error": str(error),
                "url": url
            }

    def _fetch_json(self, url):
        """
        Retourne JSON Python.
        """

        response = self._request(url)

        if isinstance(response, dict):
            return response

        try:
            return json.loads(response)

        except Exception as error:
            return {
                "success": False,
                "error": str(error),
                "url": url
            }

    def _fetch_xml(self, url):
        """
        Retourne root ElementTree.
        """

        response = self._request(url)

        if isinstance(response, dict):
            return response

        try:
            return ET.fromstring(response)

        except Exception as error:
            return {
                "success": False,
                "error": str(error),
                "url": url
            }

    def _success(self, source, items):
        return {
            "success": True,
            "source": source,
            "count": len(items),
            "items": items
        }

    def _failure(self, source, error):
        return {
            "success": False,
            "source": source,
            "count": 0,
            "items": [],
            "error": str(error)
        }

    def _clean_text(self, value):
        text = str(value or "")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def fetch_hacker_news(self):
        source = "hacker_news"
        stories_url = (
            "https://hacker-news.firebaseio.com/v0/"
            "topstories.json"
        )

        try:
            story_ids = self._fetch_json(stories_url)

            if isinstance(story_ids, dict) and story_ids.get("success") is False:
                return self._failure(source, story_ids.get("error"))

            if not isinstance(story_ids, list):
                return self._failure(source, "Format Hacker News invalide")

            items = []

            for story_id in story_ids[:15]:
                item_url = (
                    "https://hacker-news.firebaseio.com/v0/"
                    f"item/{story_id}.json"
                )
                story = self._fetch_json(item_url)

                if isinstance(story, dict) and story.get("success") is False:
                    continue

                if not isinstance(story, dict):
                    continue

                title = self._clean_text(story.get("title"))

                if not title:
                    continue

                url = story.get("url") or (
                    "https://news.ycombinator.com/"
                    f"item?id={story_id}"
                )

                items.append({
                    "title": title,
                    "url": url,
                    "score": story.get("score", 0),
                    "source": source
                })

            return self._success(source, items)

        except Exception as error:
            return self._failure(source, error)

    def fetch_github_trending(self):
        source = "github"
        url = (
            "https://api.github.com/search/repositories"
            "?q=stars:>100+pushed:>2025-01-01"
            "&sort=stars&order=desc&per_page=15"
        )

        try:
            data = self._fetch_json(url)

            if isinstance(data, dict) and data.get("success") is False:
                return self._failure(source, data.get("error"))

            if not isinstance(data, dict):
                return self._failure(source, "Format GitHub invalide")

            items = []

            for repo in data.get("items", [])[:15]:
                if not isinstance(repo, dict):
                    continue

                items.append({
                    "title": repo.get("full_name", ""),
                    "url": repo.get("html_url", ""),
                    "description": repo.get("description", ""),
                    "stars": repo.get("stargazers_count", 0),
                    "language": repo.get("language"),
                    "source": source
                })

            return self._success(source, items)

        except Exception as error:
            return self._failure(source, error)

    def fetch_arxiv_ai(self):
        source = "arxiv"
        url = (
            "https://export.arxiv.org/api/query"
            "?search_query=cat:cs.AI"
            "&sortBy=submittedDate"
            "&sortOrder=descending"
            "&max_results=10"
        )
        namespace = {
            "atom": "http://www.w3.org/2005/Atom"
        }

        try:
            root = self._fetch_xml(url)

            if isinstance(root, dict) and root.get("success") is False:
                return self._failure(source, root.get("error"))

            items = []

            for entry in root.findall("atom:entry", namespace):
                title = self._clean_text(
                    entry.findtext(
                        "atom:title",
                        default="",
                        namespaces=namespace
                    )
                )
                summary = self._clean_text(
                    entry.findtext(
                        "atom:summary",
                        default="",
                        namespaces=namespace
                    )
                )
                published = self._clean_text(
                    entry.findtext(
                        "atom:published",
                        default="",
                        namespaces=namespace
                    )
                )
                url_value = ""

                for link in entry.findall("atom:link", namespace):
                    if link.attrib.get("rel") in (None, "alternate"):
                        url_value = link.attrib.get("href", "")
                        break

                items.append({
                    "title": title,
                    "url": url_value,
                    "summary": summary,
                    "published": published,
                    "source": source
                })

            return self._success(source, items)

        except Exception as error:
            return self._failure(source, error)

    def fetch_css_techniques(self):
        source = "dev_to_css"
        url = "https://dev.to/api/articles?tag=CSS&per_page=15"

        try:
            return self._fetch_dev_to_articles(url, source)

        except Exception as error:
            return self._failure(source, error)

    def fetch_dev_to(self):
        source = "dev_to_webdev"
        url = "https://dev.to/api/articles?tag=webdev&per_page=15"

        try:
            return self._fetch_dev_to_articles(url, source)

        except Exception as error:
            return self._failure(source, error)

    def _fetch_dev_to_articles(self, url, source):
        data = self._fetch_json(url)

        if isinstance(data, dict) and data.get("success") is False:
            return self._failure(source, data.get("error"))

        if not isinstance(data, list):
            return self._failure(source, "Format Dev.to invalide")

        items = []

        for article in data[:15]:
            if not isinstance(article, dict):
                continue

            items.append({
                "title": article.get("title", ""),
                "url": article.get("url", ""),
                "description": (
                    article.get("description")
                    or article.get("summary")
                    or ""
                ),
                "tags": article.get("tag_list", []),
                "source": source
            })

        return self._success(source, items)

    def inject_into_genome(self):
        path = ".milodo/genome/web_knowledge.json"

        try:
            payload = {
                "trends": {
                    "hacker_news": self.fetch_hacker_news(),
                    "dev_to_webdev": self.fetch_dev_to()
                },
                "repos": {
                    "github": self.fetch_github_trending()
                },
                "papers": {
                    "arxiv_ai": self.fetch_arxiv_ai()
                },
                "articles": {
                    "dev_to_css": self.fetch_css_techniques()
                }
            }

            genome_dir = Path(".milodo/genome")
            genome_dir.mkdir(
                parents=True,
                exist_ok=True
            )

            output_path = Path(path)
            output_path.write_text(
                json.dumps(
                    payload,
                    indent=2,
                    ensure_ascii=False
                ),
                encoding="utf-8"
            )

            return {
                "success": True,
                "path": path,
                "data": payload
            }

        except Exception as error:
            return {
                "success": False,
                "path": path,
                "data": {},
                "error": str(error)
            }


def run(action="inject_into_genome", **kwargs):
    learner = WebLearner()

    if not hasattr(learner, action):
        return {
            "success": False,
            "error": f"Action inconnue : {action}"
        }

    method = getattr(learner, action)
    return method(**kwargs)
