import html
import logging
import urllib.parse
from typing import TYPE_CHECKING, List, Optional, cast

import attr

from synapse.media.preview_html import parse_html_description
from synapse.types import JsonDict
from synapse.util import json_decoder

if TYPE_CHECKING:
    from lxml import etree

    from synapse.server import HomeServer

logger = logging.getLogger(__name__)


@attr.s(slots=True, frozen=True, auto_attribs=True)
class OEmbedResult:
    open_graph_result: JsonDict
    author_name: Optional[str]
    cache_age: Optional[int]


class OEmbedProvider:
    """
    A helper for accessing oEmbed content.

    It can be used to check if a URL should be accessed via oEmbed and for
    requesting/parsing oEmbed content.
    """

    def __init__(self, hs: "HomeServer"):
        self._oembed_patterns = {}
        for oembed_endpoint in hs.config.oembed.oembed_patterns:
            api_endpoint = oembed_endpoint.api_endpoint
            if (
                oembed_endpoint.formats is not None
                and "json" not in oembed_endpoint.formats
            ) or api_endpoint.endswith(".xml"):
                logger.info(
                    "Ignoring oEmbed endpoint due to not supporting JSON: %s",
                    api_endpoint,
                )
                continue

            for pattern in oembed_endpoint.url_patterns:
                self._oembed_patterns[pattern] = api_endpoint

    def get_oembed_url(self, url: str) -> Optional[str]:
        """
        Check whether the URL should be downloaded as oEmbed content instead.

        Args:
            url: The URL to check.

        Returns:
            A URL to use instead or None if the original URL should be used.
        """
        for url_pattern, endpoint in self._oembed_patterns.items():
            if url_pattern.fullmatch(url):
                endpoint = endpoint.replace("{format}", "json")

                args = {"url": url, "format": "json"}
                query_str = urllib.parse.urlencode(args, True)
                return f"{endpoint}?{query_str}"

        return None

    def autodiscover_from_html(self, tree: "etree._Element") -> Optional[str]:
        """
        Search an HTML document for oEmbed autodiscovery information.

        Args:
            tree: The parsed HTML body.

        Returns:
            The URL to use for oEmbed information, or None if no URL was found.
        """
        for tag in cast(
            List["etree._Element"],
            tree.xpath("//link[@rel='alternate'][@type='application/json+oembed']"),
        ):
            if "href" in tag.attrib:
                return cast(str, tag.attrib["href"])

        for tag in cast(
            List["etree._Element"],
            tree.xpath("//link[@rel='alternative'][@type='application/json+oembed']"),
        ):
            if "href" in tag.attrib:
                return cast(str, tag.attrib["href"])

        return None

    def parse_oembed_response(self, url: str, raw_body: bytes) -> OEmbedResult:
        """
        Parse the oEmbed response into an Open Graph response.

        Args:
            url: The URL which is being previewed (not the one which was
                requested).
            raw_body: The oEmbed response as JSON encoded as bytes.

        Returns:
            json-encoded Open Graph data
        """

        try:
            oembed = json_decoder.decode(raw_body.decode("utf-8"))
        except ValueError:
            return OEmbedResult({}, None, None)

        oembed_version = oembed.get("version", "1.0")
        if oembed_version != "1.0" and oembed_version != 1:
            return OEmbedResult({}, None, None)

        try:
            cache_age = int(oembed.get("cache_age")) * 1000
        except (TypeError, ValueError):
            cache_age = None

        open_graph_response: JsonDict = {"og:url": url}

        title = oembed.get("title")
        if title and isinstance(title, str):
            open_graph_response["og:title"] = html.unescape(title)

        author_name = oembed.get("author_name")
        if not isinstance(author_name, str):
            author_name = None

        provider_name = oembed.get("provider_name")
        if provider_name and isinstance(provider_name, str):
            open_graph_response["og:site_name"] = provider_name

        thumbnail_url = oembed.get("thumbnail_url")
        if thumbnail_url and isinstance(thumbnail_url, str):
            open_graph_response["og:image"] = thumbnail_url

        oembed_type = oembed.get("type")
        if oembed_type == "rich":
            html_str = oembed.get("html")
            if isinstance(html_str, str):
                calc_description_and_urls(open_graph_response, html_str)

        elif oembed_type == "photo":
            url = oembed.get("url")
            if url and isinstance(url, str):
                open_graph_response["og:image"] = url

        elif oembed_type == "video":
            open_graph_response["og:type"] = "video.other"
            html_str = oembed.get("html")
            if html_str and isinstance(html_str, str):
                calc_description_and_urls(open_graph_response, oembed["html"])
            for size in ("width", "height"):
                val = oembed.get(size)
                if type(val) is int:  # noqa: E721
                    open_graph_response[f"og:video:{size}"] = val

        elif oembed_type == "link":
            open_graph_response["og:type"] = "website"

        else:
            logger.warning("Unknown oEmbed type: %s", oembed_type)

        return OEmbedResult(open_graph_response, author_name, cache_age)


def _fetch_urls(tree: "etree._Element", tag_name: str) -> List[str]:
    results = []
    for tag in cast(List["etree._Element"], tree.xpath("//*/" + tag_name)):
        if "src" in tag.attrib:
            results.append(cast(str, tag.attrib["src"]))
    return results


def calc_description_and_urls(open_graph_response: JsonDict, html_body: str) -> None:
    """
    Calculate description for an HTML document.

    This uses lxml to convert the HTML document into plaintext. If errors
    occur during processing of the document, an empty response is returned.

    Args:
        open_graph_response: The current Open Graph summary. This is updated with additional fields.
        html_body: The HTML document, as bytes.

    Returns:
        The summary
    """
    if not html_body:
        return

    from lxml import etree

    parser = etree.HTMLParser(recover=True, encoding="utf-8")

    tree = etree.fromstring(html_body, parser)  # type: ignore[arg-type]

    if tree is None:
        return  # type: ignore[unreachable]

    if "og:image" not in open_graph_response:
        image_urls = _fetch_urls(tree, "img")
        if image_urls:
            open_graph_response["og:image"] = image_urls[0]

    video_urls = _fetch_urls(tree, "video") + _fetch_urls(tree, "embed")
    if video_urls:
        open_graph_response["og:video"] = video_urls[0]

    description = parse_html_description(tree)
    if description:
        open_graph_response["og:description"] = description
