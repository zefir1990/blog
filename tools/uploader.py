#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple

REQUEST_TIMEOUT = 60
DEFAULT_SITE_URL = "https://zefir1990.space"
EDITOR_KEY_HEADER = "rusty-blogger-post-editor-key"

TITLE_PATTERN = re.compile(r"\{:([A-Za-z0-9_-]+)\}(.*?)\{:\}", re.DOTALL)
SECTION_START_PATTERN = re.compile(r"^\{:([A-Za-z0-9_-]+)\}(.*)$")
SECTION_END_PATTERN = re.compile(r"^\{:\}$")


class BlogApiError(Exception):
    pass


def load_environment_file(directory: str) -> None:
    path = os.path.join(directory, ".env")
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as file:
        for line in file:
            stripped_line = line.strip()
            if not stripped_line or stripped_line.startswith("#") or "=" not in stripped_line:
                continue
            name, value = stripped_line.split("=", 1)
            name = name.strip()
            value = value.strip().strip('"').strip("'")
            if name and name not in os.environ:
                os.environ[name] = value


def parse_categories(line: str) -> List[str]:
    value = line.strip()
    if value.startswith("Categories:"):
        value = value[len("Categories:"):]
    categories: List[str] = []
    for raw_category in re.split(r"[,|]", value):
        category = raw_category.strip().lower()
        if category and category not in categories:
            categories.append(category)
    return categories


def parse_titles(title_line: str) -> Dict[str, str]:
    titles: Dict[str, str] = {}
    for match in TITLE_PATTERN.finditer(title_line):
        language = match.group(1).strip().lower()
        title = match.group(2).strip()
        if language and title:
            titles[language] = title
    return titles


def parse_sections(lines: List[str]) -> Dict[str, str]:
    sections: Dict[str, str] = {}
    current_language: Optional[str] = None
    current_lines: List[str] = []
    for line in lines:
        stripped_line = line.strip()
        start_match = SECTION_START_PATTERN.match(line.lstrip())
        if start_match:
            if current_language is not None:
                raise ValueError(f"language section {current_language} is not closed")
            current_language = start_match.group(1).strip().lower()
            current_lines = []
            remainder = start_match.group(2)
            if remainder:
                current_lines.append(remainder)
            continue
        if SECTION_END_PATTERN.match(stripped_line):
            if current_language is not None:
                sections[current_language] = "\n".join(current_lines).strip()
                current_language = None
                current_lines = []
            continue
        if current_language is not None:
            current_lines.append(line)
    if current_language is not None:
        raise ValueError(f"language section {current_language} is not closed")
    return sections


def parse_compiled_post(path: str) -> Tuple[str, List[str], Dict[str, str], Dict[str, str]]:
    with open(path, "r", encoding="utf-8") as file:
        lines = file.read().splitlines()
    if len(lines) < 4:
        raise ValueError("compiled post must contain slug, title, categories and a language section")
    slug = lines[0].strip()
    if not slug:
        raise ValueError("compiled post slug is empty")
    categories = parse_categories(lines[2])
    titles = parse_titles(lines[1])
    sections = parse_sections(lines[3:])
    if not sections:
        raise ValueError("compiled post contains no language sections")
    return slug, categories, titles, sections


def request_json(
    method: str,
    url: str,
    headers: Optional[Dict[str, str]] = None,
    payload: Optional[dict] = None,
) -> Tuple[int, str]:
    data = None
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", errors="replace")


class RustyBloggerClient:
    def __init__(self, site_url: str, editor_key: str) -> None:
        self.site_url = site_url.rstrip("/")
        self.editor_key = editor_key

    def existing_post(self, slug: str, language: str) -> Optional[dict]:
        encoded_slug = urllib.parse.quote(slug, safe="")
        query = urllib.parse.urlencode({"lang": language})
        status, body = request_json(
            "GET",
            f"{self.site_url}/api/posts/{encoded_slug}?{query}",
        )
        if status == 404:
            return None
        if status != 200:
            raise BlogApiError(f"GET failed: {status} {body[:200]}")
        post = json.loads(body)
        if post.get("language") != language:
            return None
        return post

    def upsert_post(self, post: dict) -> None:
        existing_post = self.existing_post(post["slug"], post["language"])
        encoded_slug = urllib.parse.quote(post["slug"], safe="")
        write_headers = {EDITOR_KEY_HEADER: self.editor_key}
        if existing_post is None:
            status, body = request_json(
                "POST",
                f"{self.site_url}/api/posts",
                headers=write_headers,
                payload=post,
            )
        else:
            post["published_unix_seconds"] = existing_post.get("published_unix_seconds")
            post["published_date"] = existing_post.get("published_date")
            status, body = request_json(
                "PUT",
                f"{self.site_url}/api/posts/{encoded_slug}",
                headers=write_headers,
                payload=post,
            )
        if status not in (200, 201):
            raise BlogApiError(f"write failed: {status} {body[:200]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or update RustyBlogger post variants.")
    parser.add_argument("--post", required=True, help="Path to the compiled post file.")
    args = parser.parse_args()

    repository_directory = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_environment_file(repository_directory)

    site_url = os.environ.get("RUSTY_BLOGGER_SITE_URL", DEFAULT_SITE_URL)
    editor_key = os.environ.get("RUSTY_BLOGGER_POST_EDITOR_KEY", "").strip()
    if not editor_key:
        print("RUSTY_BLOGGER_POST_EDITOR_KEY is not set", file=sys.stderr)
        return 1

    try:
        slug, categories, titles, sections = parse_compiled_post(args.post)
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1

    client = RustyBloggerClient(site_url, editor_key)
    failures = 0
    for language, body_html in sections.items():
        title = titles.get(language)
        if not title:
            print(f"{language}: skipped, title is missing", file=sys.stderr)
            failures += 1
            continue
        post = {
            "slug": slug,
            "language": language,
            "title": title,
            "categories": categories,
            "body_html": body_html,
            "source_path": f"{slug}.txt",
        }
        try:
            client.upsert_post(post)
        except (BlogApiError, OSError, urllib.error.URLError) as error:
            print(f"{language}: failed: {error}", file=sys.stderr)
            failures += 1
        else:
            print(f"{language}: uploaded")

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
