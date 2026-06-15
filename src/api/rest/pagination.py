"""Reusable list pagination — offset/limit with disclosure headers (SPEC-API-003 / ADR-0078).

Keeps the response **body** an array (backward-compatible) and puts pagination metadata in headers:
``X-Total-Count`` and an RFC-5988 ``Link`` header with ``rel="next"``/``"prev"``. Validation of the
query params is done by FastAPI ``Query`` constraints at the call site (out-of-range ⇒ 422
``VALIDATION_ERROR`` via the SPEC-API-001 envelope).

Use from any list endpoint:

    page = paginate(items, limit=limit, offset=offset, request=request, response=response)
"""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import Response

from src.shared.config import settings


def effective_limit(requested: int | None, default: int) -> int:
    """Resolve the page size: the requested value, else the endpoint default — capped at the max."""
    chosen = requested if requested is not None else default
    return max(1, min(chosen, settings.pagination_max_limit))


def paginate[T](
    items: list[T],
    *,
    limit: int,
    offset: int,
    request: Request,
    response: Response,
) -> list[T]:
    """Return ``items[offset:offset+limit]`` and set ``X-Total-Count`` + ``Link`` headers.

    The total is always disclosed via ``X-Total-Count`` so truncation is never silent (FR-03).
    """
    total = len(items)
    page = items[offset : offset + limit]
    response.headers["X-Total-Count"] = str(total)

    base = str(request.url.remove_query_params(["limit", "offset"]))
    sep = "&" if "?" in base else "?"
    links: list[str] = []
    if offset + limit < total:
        links.append(f'<{base}{sep}limit={limit}&offset={offset + limit}>; rel="next"')
    if offset > 0:
        prev = max(0, offset - limit)
        links.append(f'<{base}{sep}limit={limit}&offset={prev}>; rel="prev"')
    if links:
        response.headers["Link"] = ", ".join(links)
    return page
