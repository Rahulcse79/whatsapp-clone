#!/usr/bin/env python3
import codecs
import logging
import re
from typing import (
    TYPE_CHECKING,
    Callable,
    Dict,
    Generator,
    Iterable,
    List,
    Optional,
    Set,
    Union,
    cast,
)

if TYPE_CHECKING:
    from lxml import etree

logger = logging.getLogger(__name__)

_charset_match = re.compile(
    rb'<\s*meta[^>]*charset\s*=\s*"?([a-z0-9_-]+)"?', flags=re.I
)
_xml_encoding_match = re.compile(
    rb'\s*<\s*\?\s*xml[^>]*encoding="([a-z0-9_-]+)"', flags=re.I
)
_content_type_match = re.compile(r'.*; *charset="?(.*?)"?(;|$)', flags=re.I)

ARIA_ROLES_TO_IGNORE = {"directory", "menu", "menubar", "toolbar"}


def _normalise_encoding(encoding: str) -> Optional[str]:
    """Use the Python codec's name as the normalised entry."""
    try:
        return codecs.lookup(encoding).name
    except LookupError:
        return None


def _get_html_media_encodings(
    body: bytes, content_type: Optional[str]
) -> Iterable[str]:
    """
    Get potential encoding of the body based on the (presumably) HTML body or the content-type header.

    The precedence used for finding a character encoding is:

    1. <meta> tag with a charset declared.
    2. The XML document's character encoding attribute.
    3. The Content-Type header.
    4. Fallback to utf-8.
    5. Fallback to windows-1252.

    This roughly follows the algorithm used by BeautifulSoup's bs4.dammit.EncodingDetector.

    Args:
        body: The HTML document, as bytes.
        content_type: The Content-Type header.

    Returns:
        The character encoding of the body, as a string.
    """
    attempted_encodings: Set[str] = set()

    body_start = body[:1024]

    match = _charset_match.search(body_start)
    if match:
        encoding = _normalise_encoding(match.group(1).decode("ascii"))
        if encoding:
            attempted_encodings.add(encoding)
            yield encoding

    match = _xml_encoding_match.match(body_start)
    if match:
        encoding = _normalise_encoding(match.group(1).decode("ascii"))
        if encoding and encoding not in attempted_encodings:
            attempted_encodings.add(encoding)
            yield encoding

    if content_type:
        content_match = _content_type_match.match(content_type)
        if content_match:
            encoding = _normalise_encoding(content_match.group(1))
            if encoding and encoding not in attempted_encodings:
                attempted_encodings.add(encoding)
                yield encoding

    for fallback in ("utf-8", "cp1252"):
        if fallback not in attempted_encodings:
            yield fallback


def decode_body(
    body: bytes, uri: str, content_type: Optional[str] = None
) -> Optional["etree._Element"]:
    """
    This uses lxml to parse the HTML document.

    Args:
        body: The HTML document, as bytes.
        uri: The URI used to download the body.
        content_type: The Content-Type header.

    Returns:
        The parsed HTML body, or None if an error occurred during processed.
    """
    if not body:
        return None

    for encoding in _get_html_media_encodings(body, content_type):
        try:
            body.decode(encoding)
        except Exception:
            pass
        else:
            break
    else:
        logger.warning("Unable to decode HTML body for %s", uri)
        return None

    from lxml import etree

    parser = etree.HTMLParser(recover=True, encoding=encoding)

    return etree.fromstring(body, parser)  # type: ignore[arg-type]


def _get_meta_tags(
    tree: "etree._Element",
    property: str,
    prefix: str,
    property_mapper: Optional[Callable[[str], Optional[str]]] = None,
) -> Dict[str, Optional[str]]:
    """
    Search for meta tags prefixed with a particular string.

    Args:
        tree: The parsed HTML document.
        property: The name of the property which contains the tag name, e.g.
            "property" for Open Graph.
        prefix: The prefix on the property to search for, e.g. "og" for Open Graph.
        property_mapper: An optional callable to map the property to the Open Graph
            form. Can return None for a key to ignore that key.

    Returns:
        A map of tag name to value.
    """
    results: Dict[str, Optional[str]] = {}
    for tag in cast(
        List["etree._Element"],
        tree.xpath(
            f"//*/meta[starts-with(@{property}, '{prefix}:')][@content][not(@content='')]"
        ),
    ):
        if len(results) >= 50:
            logger.warning(
                "Skipping parsing of Open Graph for page with too many '%s:' tags",
                prefix,
            )
            return {}

        key = cast(str, tag.attrib[property])
        if property_mapper:
            new_key = property_mapper(key)
            if new_key is None:
                continue
            key = new_key

        results[key] = cast(str, tag.attrib["content"])

    return results


def _map_twitter_to_open_graph(key: str) -> Optional[str]:
    """
    Map a Twitter card property to the analogous Open Graph property.

    Args:
        key: The Twitter card property (starts with "twitter:").

    Returns:
        The Open Graph property (starts with "og:") or None to have this property
        be ignored.
    """
    if key == "twitter:card" or key == "twitter:creator":
        return None
    if key == "twitter:site":
        return "og:site_name"
    return "og" + key[7:]


def parse_html_to_open_graph(tree: "etree._Element") -> Dict[str, Optional[str]]:
    """
    Parse the HTML document into an Open Graph response.

    This uses lxml to search the HTML document for Open Graph data (or
    synthesizes it from the document).

    Args:
        tree: The parsed HTML document.

    Returns:
        The Open Graph response as a dictionary.
    """


    og = _get_meta_tags(tree, "property", "og")
    twitter = _get_meta_tags(tree, "name", "twitter", _map_twitter_to_open_graph)
    for key, value in twitter.items():
        if key not in og:
            og[key] = value

    if "og:title" not in og:
        title = cast(
            List["etree._ElementUnicodeResult"],
            tree.xpath("((//title)[1] | (//h1)[1] | (//h2)[1] | (//h3)[1])/text()"),
        )
        if title:
            og["og:title"] = title[0].strip()
        else:
            og["og:title"] = None

    if "og:image" not in og:
        meta_image = cast(
            List["etree._ElementUnicodeResult"],
            tree.xpath(
                "//*/meta[translate(@itemprop, 'IMAGE', 'image')='image'][not(@content='')]/@content[1]"
            ),
        )

        if meta_image:
            og["og:image"] = meta_image[0]
        else:

            images = cast(
                List["etree._Element"],
                tree.xpath("//img[@src][number(@width)>10][number(@height)>10]"),
            )
            images = sorted(
                images,
                key=lambda i: (
                    -1 * float(i.attrib["width"]) * float(i.attrib["height"])
                ),
            )
            if not images:
                images = cast(List["etree._Element"], tree.xpath("//img[@src][1]"))
            if images:
                og["og:image"] = cast(str, images[0].attrib["src"])

            else:
                favicons = cast(
                    List["etree._ElementUnicodeResult"],
                    tree.xpath("//link[@href][contains(@rel, 'icon')]/@href[1]"),
                )
                if favicons:
                    og["og:image"] = favicons[0]

    if "og:description" not in og:
        meta_description = cast(
            List["etree._ElementUnicodeResult"],
            tree.xpath(
                "//*/meta[translate(@name, 'DESCRIPTION', 'description')='description'][not(@content='')]/@content[1]"
            ),
        )

        if meta_description:
            og["og:description"] = meta_description[0]
        else:
            og["og:description"] = parse_html_description(tree)
    elif og["og:description"]:
        # This must be a non-empty string at this point.
        assert isinstance(og["og:description"], str)
        og["og:description"] = summarize_paragraphs([og["og:description"]])

    return og


def parse_html_description(tree: "etree._Element") -> Optional[str]:
    """
    Calculate a text description based on an HTML document.

    Grabs any text nodes which are inside the <body/> tag, unless they are within
    an HTML5 semantic markup tag (<header/>, <nav/>, <aside/>, <footer/>), or
    if they are within a <script/>, <svg/> or <style/> tag, or if they are within
    a tag whose content is usually only shown to old browsers
    (<iframe/>, <video/>, <canvas/>, <picture/>).

    This is a very very very coarse approximation to a plain text render of the page.

    Args:
        tree: The parsed HTML document.

    Returns:
        The plain text description, or None if one cannot be generated.
    """

    from lxml import etree

    TAGS_TO_REMOVE = {
        "header",
        "nav",
        "aside",
        "footer",
        "script",
        "noscript",
        "style",
        "svg",
        "iframe",
        "video",
        "canvas",
        "img",
        "picture",
        etree.Comment,
    }

    text_nodes = (
        re.sub(r"\s+", "\n", el).strip()
        for el in _iterate_over_text(tree.find("body"), TAGS_TO_REMOVE)
    )
    return summarize_paragraphs(text_nodes)


def _iterate_over_text(
    tree: Optional["etree._Element"],
    tags_to_ignore: Set[object],
    stack_limit: int = 1024,
) -> Generator[str, None, None]:
    """Iterate over the tree returning text nodes in a depth first fashion,
    skipping text nodes inside certain tags.

    Args:
        tree: The parent element to iterate. Can be None if there isn't one.
        tags_to_ignore: Set of tags to ignore
        stack_limit: Maximum stack size limit for depth-first traversal.
            Nodes will be dropped if this limit is hit, which may truncate the
            textual result.
            Intended to limit the maximum working memory when generating a preview.
    """

    if tree is None:
        return

    elements: List[Union[str, "etree._Element"]] = [tree]
    while elements:
        el = elements.pop()

        if isinstance(el, str):
            yield el
        elif el.tag not in tags_to_ignore:
            if el.get("role") in ARIA_ROLES_TO_IGNORE:
                continue

            if el.text:
                yield el.text

            for child in el.iterchildren(reversed=True):
                if len(elements) > stack_limit:
                    break

                if child.tail:
                    elements.append(child.tail)

                elements.append(child)


def summarize_paragraphs(
    text_nodes: Iterable[str], min_size: int = 200, max_size: int = 500
) -> Optional[str]:
    """
    Try to get a summary respecting first paragraph and then word boundaries.

    Args:
        text_nodes: The paragraphs to summarize.
        min_size: The minimum number of words to include.
        max_size: The maximum number of words to include.

    Returns:
        A summary of the text nodes, or None if that was not possible.
    """

    description = ""

    for text_node in text_nodes:
        if len(description) < min_size:
            text_node = re.sub(r"[\t \r\n]+", " ", text_node)
            description += text_node + "\n\n"
        else:
            break

    description = description.strip()
    description = re.sub(r"[\t ]+", " ", description)
    description = re.sub(r"[\t \r\n]*[\r\n]+", "\n\n", description)

    if len(description) > max_size:
        new_desc = ""

        for match in re.finditer(r"\s*\S+", description):
            word = match.group()

            if len(word) + len(new_desc) < max_size:
                new_desc += word
            else:
                if len(new_desc) < min_size:
                    new_desc += word
                break

        if len(new_desc) > max_size:
            new_desc = new_desc[:max_size]

        description = new_desc.strip() + "…"
    return description if description else None
