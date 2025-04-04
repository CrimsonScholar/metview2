"""A really thin wrap around the Met Museum (JSON-based) REST-API."""

import functools
import logging
import os
import typing
from urllib import parse

import requests

from . import met_get_type

_ARTIST_NAME_NOT_FOUND = "<No artist name>"
_TITLE_NOT_FOUND = "<No title>"

# Reference: https://datatracker.ietf.org/doc/html/rfc3986
_BASE = os.getenv("MET_MUSEUM_API_DOMAIN", "https://collectionapi.metmuseum.org")
_SCHEME_SEPARATOR = ":"

_LOGGER = logging.getLogger(__name__)

KNOWN_CLASSIFICATIONS = [
    "Albums",
    "Archery Equipment-Bows",
    "Books",
    "Ceramics-Porcelain",
    "Codices",
    "Drawings",
    "Ephemera",
    "Glass",
    "Glass-Painted",
    "Jewelry",
    "Musical instruments",
    "Ornament & Architecture",
    "Paintings",
    "Paper",
    "Periodicals",
    "Photographs",
    "Portfolios",
    "Posters",
    "Printed matter",
    "Prints",
    "Sculpture",
    "Sword Furniture-Tsuba",
    "Textiles-Embroidered",
    "Tools",
]


class _ObjectDetailsResponse(typing.TypedDict):
    """The raw Met Museum response to a ``../v1/objects/{objectID}`` API call."""

    artistDisplayName: str
    classification: str | None
    medium: str | None
    objectBeginDate: int
    objectEndDate: int
    primaryImageSmall: str | None
    title: str


class _ObjectsResponse(typing.TypedDict):
    """The raw Met Museum response to a ``public/collection/v1/objects`` API call."""

    limit: int
    objectIDs: list[int]


class _SearchResponse(typing.TypedDict):
    """The result of a .../v1/search?... query."""

    total: int
    objectIDs: list[int]


class ObjectDetails(typing.NamedTuple):
    """The formatted Met Museum data.

    Attributes:
        artist: The name, group, or entity that created the Artwork.
        classification: The type of artwork.
        datetime_range: The start and end date(s) assoicated with the Artwork.
        medium: The material or method used to create the Artwork.
        thumbnail_url: The https / http URL to the Artwork, if any.
        title: The name of the Artwork. If no name, a default "no title found" is given.

    """

    artist: str
    classification: str | None
    datetime_range: met_get_type.DatetimeRange
    medium: str | None
    thumbnail_url: str | None
    title: str


def _get_datetime(year: int | None) -> met_get_type.Datetime | None:
    """Convert ``year`` to a datetime object.

    Args:
        year: Some B.C / A.D. year, if any. e.g. ``2025``.

    Returns:
        The converted datetime, if any.

    """
    if not year:
        return None

    try:
        # NOTE: The Met Museum only tracks year so we just fill in
        # a placeholder for the month and day.
        #
        return met_get_type.Datetime(year)
    except (ValueError, TypeError):
        _LOGGER.error('Value "%s" could not be converted into a datetime.', year)

        return None


def _join(text: typing.Iterable[str]) -> str:
    """Join ``text`` in a way that the Met's REST API can understand.

    Args:
        text: All items to join.

    Returns:
        The formatted, joined output.

    """
    return "|".join(text)


@functools.lru_cache()
def get_all_identifiers() -> list[int]:
    """Find all Met Museum Artwork IDs."""
    url = parse.urljoin(_BASE, "public/collection/v1/objects")
    response = requests.get(url)

    if response.status_code != 200:
        raise ConnectionError(f'URL "{url}" is unreadable. Got "{response}" response.')

    data = typing.cast(_ObjectsResponse, response.json())

    return data["objectIDs"]


def get_identifier_data(identifier: str | int) -> ObjectDetails:
    """Read all data from Artwork ``identifier``.

    Args:
        identifier: Some Met Museum Artwork ID to check.

    Raises:
        ConnectionError: If no data could be found for ``identifier``.

    Returns:
        All found data.

    """
    url = parse.urljoin(_BASE, f"public/collection/v1/objects/{identifier}")
    response = requests.get(url)

    if response.status_code != 200:
        raise ConnectionError(f'URL "{url}" is unreadable. Got "{response}" response.')

    data = typing.cast(_ObjectDetailsResponse, response.json())

    return ObjectDetails(
        artist=data.get("artistDisplayName", _ARTIST_NAME_NOT_FOUND),
        classification=data.get("classification") or None,
        datetime_range=(
            _get_datetime(data.get("objectBeginDate")),
            _get_datetime(data.get("objectEndDate")),
        ),
        medium=data.get("medium") or None,
        thumbnail_url=data.get("primaryImageSmall") or None,
        title=data.get("title", _TITLE_NOT_FOUND),
    )


@functools.lru_cache()  # IMPORTANT: This could cause space issues in the future. Audit!
def search_objects(
    text: str | None = "",
    classification: str | None = None,
    has_image: bool = False,
) -> list[int]:
    """Search The Met's database according too all input arguments.

    Args:
        text: Some Artwork name to search by, if any.
        classification: The allowed types / presentation of the Artwork.
        has_image: If ``True``, only results with images are returned.

    Raises:
        ConnectionError: If no search could be done.

    Returns:
        The found IDs.

    """
    parameters: dict[str, str] = {}

    # NOTE: We don't care about the false case so we just don't check for it here.
    if has_image:
        parameters["hasImages"] = str(has_image).lower()

    if classification:
        parameters["classification"] = classification

    if not parameters and not text:
        # PERF: This query is more efficient and if we don't have any search terms, we
        # might as well get the savings.
        #
        return get_all_identifiers()

    parameters["q"] = text or '""'
    parsed_url = parse.urlparse(_BASE)
    path = "/public/collection/v1/search"
    # Example: https://collectionapi.metmuseum.org/public/collection/v1/search?hasImages=true&medium=Brass&q=%22%22
    url = parse.urlunparse(
        (
            parsed_url.scheme,
            parsed_url.netloc,
            path,
            "",
            parse.urlencode(parameters),
            "",
        )
    )
    _LOGGER.info('Searching "%s" url.', url)
    response = requests.get(url)

    if response.status_code != 200:
        raise ConnectionError(
            f'URL / parameters "{_BASE} / {parameters}" is unreadable. '
            f'Got "{response}" response.'
        )

    data = typing.cast(_SearchResponse, response.json())

    return data["objectIDs"]
