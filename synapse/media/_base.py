import logging
import os
import urllib
from abc import ABC, abstractmethod
from types import TracebackType
from typing import Awaitable, Dict, Generator, List, Optional, Tuple, Type

import attr

from twisted.internet.interfaces import IConsumer
from twisted.protocols.basic import FileSender
from twisted.web.server import Request

from synapse.api.errors import Codes, cs_error
from synapse.http.server import finish_request, respond_with_json
from synapse.http.site import SynapseRequest
from synapse.logging.context import make_deferred_yieldable
from synapse.util.stringutils import is_ascii

logger = logging.getLogger(__name__)

TEXT_CONTENT_TYPES = [
    "text/css",
    "text/csv",
    "text/html",
    "text/calendar",
    "text/plain",
    "text/javascript",
    "application/json",
    "application/ld+json",
    "application/rtf",
    "image/svg+xml",
    "text/xml",
]

INLINE_CONTENT_TYPES = [
    "text/css",
    "text/plain",
    "text/csv",
    "application/json",
    "application/ld+json",
    "image/jpeg",
    "image/gif",
    "image/png",
    "image/apng",
    "image/webp",
    "image/avif",
    "video/mp4",
    "video/webm",
    "video/ogg",
    "video/quicktime",
    "audio/mp4",
    "audio/webm",
    "audio/aac",
    "audio/mpeg",
    "audio/ogg",
    "audio/wave",
    "audio/wav",
    "audio/x-wav",
    "audio/x-pn-wav",
    "audio/flac",
    "audio/x-flac",
]

DEFAULT_MAX_TIMEOUT_MS = 20_000

MAXIMUM_ALLOWED_MAX_TIMEOUT_MS = 60_000


def respond_404(request: SynapseRequest) -> None:
    assert request.path is not None
    respond_with_json(
        request,
        404,
        cs_error("Not found '%s'" % (request.path.decode(),), code=Codes.NOT_FOUND),
        send_cors=True,
    )


async def respond_with_file(
    request: SynapseRequest,
    media_type: str,
    file_path: str,
    file_size: Optional[int] = None,
    upload_name: Optional[str] = None,
) -> None:
    logger.debug("Responding with %r", file_path)

    if os.path.isfile(file_path):
        if file_size is None:
            stat = os.stat(file_path)
            file_size = stat.st_size

        add_file_headers(request, media_type, file_size, upload_name)

        with open(file_path, "rb") as f:
            await make_deferred_yieldable(FileSender().beginFileTransfer(f, request))

        finish_request(request)
    else:
        respond_404(request)


def add_file_headers(
    request: Request,
    media_type: str,
    file_size: Optional[int],
    upload_name: Optional[str],
) -> None:
    """Adds the correct response headers in preparation for responding with the
    media.

    Args:
        request
        media_type: The media/content type.
        file_size: Size in bytes of the media, if known.
        upload_name: The name of the requested file, if any.
    """

    def _quote(x: str) -> str:
        return urllib.parse.quote(x.encode("utf-8"))

    if media_type.lower() in TEXT_CONTENT_TYPES:
        content_type = media_type + "; charset=UTF-8"
    else:
        content_type = media_type

    request.setHeader(b"Content-Type", content_type.encode("UTF-8"))

    if media_type.lower().split(";", 1)[0] in INLINE_CONTENT_TYPES:
        disposition = "inline"
    else:
        disposition = "attachment"

    if upload_name:
        if _can_encode_filename_as_token(upload_name):
            disposition = "%s; filename=%s" % (
                disposition,
                upload_name,
            )
        else:
            disposition = "%s; filename*=utf-8''%s" % (
                disposition,
                _quote(upload_name),
            )

    request.setHeader(b"Content-Disposition", disposition.encode("ascii"))

    request.setHeader(b"Cache-Control", b"public,max-age=86400,s-maxage=86400")
    if file_size is not None:
        request.setHeader(b"Content-Length", b"%d" % (file_size,))

    request.setHeader(b"X-Robots-Tag", "noindex, nofollow, noarchive, noimageindex")


_FILENAME_SEPARATOR_CHARS = {
    "(",
    ")",
    "<",
    ">",
    "@",
    ",",
    ";",
    ":",
    "\\",
    '"',
    "/",
    "[",
    "]",
    "?",
    "=",
    "{",
    "}",
}


def _can_encode_filename_as_token(x: str) -> bool:
    for c in x:
        if ord(c) >= 127 or ord(c) <= 32 or c in _FILENAME_SEPARATOR_CHARS:
            return False
    return True


async def respond_with_responder(
    request: SynapseRequest,
    responder: "Optional[Responder]",
    media_type: str,
    file_size: Optional[int],
    upload_name: Optional[str] = None,
) -> None:
    """Responds to the request with given responder. If responder is None then
    returns 404.

    Args:
        request
        responder
        media_type: The media/content type.
        file_size: Size in bytes of the media. If not known it should be None
        upload_name: The name of the requested file, if any.
    """
    if not responder:
        respond_404(request)
        return

    with responder:
        if request._disconnected:
            logger.warning(
                "Not sending response to request %s, already disconnected.", request
            )
            return

        logger.debug("Responding to media request with responder %s", responder)
        add_file_headers(request, media_type, file_size, upload_name)
        try:
            await responder.write_to_consumer(request)
        except Exception as e:
            logger.warning("Failed to write to consumer: %s %s", type(e), e)

            if request.producer:
                request.unregisterProducer()

    finish_request(request)


class Responder(ABC):
    """Represents a response that can be streamed to the requester.

    Responder is a context manager which *must* be used, so that any resources
    held can be cleaned up.
    """

    @abstractmethod
    def write_to_consumer(self, consumer: IConsumer) -> Awaitable:
        """Stream response into consumer

        Args:
            consumer: The consumer to stream into.

        Returns:
            Resolves once the response has finished being written
        """
        raise NotImplementedError()

    def __enter__(self) -> None:  # noqa: B027
        pass

    def __exit__(  # noqa: B027
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        pass


@attr.s(slots=True, frozen=True, auto_attribs=True)
class ThumbnailInfo:
    """Details about a generated thumbnail."""

    width: int
    height: int
    method: str
    type: str
    length: int


@attr.s(slots=True, frozen=True, auto_attribs=True)
class FileInfo:
    """Details about a requested/uploaded file."""

    server_name: Optional[str]
    file_id: str
    url_cache: bool = False
    thumbnail: Optional[ThumbnailInfo] = None

    @property
    def thumbnail_width(self) -> Optional[int]:
        if not self.thumbnail:
            return None
        return self.thumbnail.width

    @property
    def thumbnail_height(self) -> Optional[int]:
        if not self.thumbnail:
            return None
        return self.thumbnail.height

    @property
    def thumbnail_method(self) -> Optional[str]:
        if not self.thumbnail:
            return None
        return self.thumbnail.method

    @property
    def thumbnail_type(self) -> Optional[str]:
        if not self.thumbnail:
            return None
        return self.thumbnail.type

    @property
    def thumbnail_length(self) -> Optional[int]:
        if not self.thumbnail:
            return None
        return self.thumbnail.length


def get_filename_from_headers(headers: Dict[bytes, List[bytes]]) -> Optional[str]:
    """
    Get the filename of the downloaded file by inspecting the
    Content-Disposition HTTP header.

    Args:
        headers: The HTTP request headers.

    Returns:
        The filename, or None.
    """
    content_disposition = headers.get(b"Content-Disposition", [b""])

    if not content_disposition[0]:
        return None

    _, params = _parse_header(content_disposition[0])

    upload_name = None

    upload_name_utf8 = params.get(b"filename*", None)
    if upload_name_utf8:
        if upload_name_utf8.lower().startswith(b"utf-8''"):
            upload_name_utf8 = upload_name_utf8[7:]
            try:
                upload_name = urllib.parse.unquote(
                    upload_name_utf8.decode("ascii"), errors="strict"
                )
            except UnicodeDecodeError:
                pass

    if not upload_name:
        upload_name_ascii = params.get(b"filename", None)
        if upload_name_ascii and is_ascii(upload_name_ascii):
            upload_name = upload_name_ascii.decode("ascii")

    return upload_name


def _parse_header(line: bytes) -> Tuple[bytes, Dict[bytes, bytes]]:
    """Parse a Content-type like header.

    Cargo-culted from `cgi`, but works on bytes rather than strings.

    Args:
        line: header to be parsed

    Returns:
        The main content-type, followed by the parameter dictionary
    """
    parts = _parseparam(b";" + line)
    key = next(parts)
    pdict = {}
    for p in parts:
        i = p.find(b"=")
        if i >= 0:
            name = p[:i].strip().lower()
            value = p[i + 1 :].strip()

            # strip double-quotes
            if len(value) >= 2 and value[0:1] == value[-1:] == b'"':
                value = value[1:-1]
                value = value.replace(b"\\\\", b"\\").replace(b'\\"', b'"')
            pdict[name] = value

    return key, pdict


def _parseparam(s: bytes) -> Generator[bytes, None, None]:
    """Generator which splits the input on ;, respecting double-quoted sequences

    Cargo-culted from `cgi`, but works on bytes rather than strings.

    Args:
        s: header to be parsed

    Returns:
        The split input
    """
    while s[:1] == b";":
        s = s[1:]

        end = s.find(b";")

        while end > 0 and (s.count(b'"', 0, end) - s.count(b'\\"', 0, end)) % 2:
            end = s.find(b";", end + 1)

        if end < 0:
            end = len(s)
        f = s[:end]
        yield f.strip()
        s = s[end:]
