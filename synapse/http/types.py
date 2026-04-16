from typing import Iterable, Mapping, Union

QueryParamValue = Union[str, bytes, Iterable[Union[str, bytes]]]
QueryParams = Union[Mapping[str, QueryParamValue], Mapping[bytes, QueryParamValue]]

__all__ = ["QueryParams"]
