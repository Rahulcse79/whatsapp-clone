from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional, Tuple

from twisted.web.server import Request

from synapse.http.server import DirectServeJsonResource

if TYPE_CHECKING:
    from synapse.server import HomeServer


class AdditionalResource(DirectServeJsonResource):
    """Resource wrapper for additional_resources

    If the user has configured additional_resources, we need to wrap the
    handler class with a Resource so that we can map it into the resource tree.

    This class is also where we wrap the request handler with logging, metrics,
    and exception handling.
    """

    def __init__(
        self,
        hs: "HomeServer",
        handler: Callable[[Request], Awaitable[Optional[Tuple[int, Any]]]],
    ):
        """Initialise AdditionalResource

        The ``handler`` should return a deferred which completes when it has
        done handling the request. It should write a response with
        ``request.write()``, and call ``request.finish()``.

        Args:
            hs: homeserver
            handler: function to be called to handle the request.
        """
        super().__init__()
        self._handler = handler

    async def _async_render(self, request: Request) -> Optional[Tuple[int, Any]]:
        return await self._handler(request)
