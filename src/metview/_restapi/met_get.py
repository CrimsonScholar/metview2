"""A really thin wrap around the Met Museum (JSON-based) REST-API."""

import os
import typing
from urllib import parse

import requests

from . import met_get_type

# Reference: https://datatracker.ietf.org/doc/html/rfc3986
_BASE = os.getenv("MET_MUSEUM_API_DOMAIN", "https://collectionapi.metmuseum.org")

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


def _join(text: typing.Iterable[str]) -> str:
    """Join ``text`` in a way that the Met's REST API can understand.

    Args:
        text: All items to join.

    Returns:
        The formatted, joined output.

    """
    return "|".join(text)


def search_objects(
    text: str | None = "",
    classifications: typing.Iterable[str] | None = None,
    has_image: bool = False,
) -> list[int]:
    """Search The Met's database according too all input arguments.

    Args:
        text: Some Artwork name to search by, if any.
        classifications: The allowed types / presentation of the Artwork.
        has_image: If ``True``, only results with images are returned.

    Raises:
        ConnectionError: If no search could be done.

    Returns:
        The found IDs.

    """
    parameters: dict[str, str] = {}

    # NOTE: We don't care about the false case so we just don't check for it here.
    if has_image:
        parameters["hasIamges"] = "true"

    if classifications:
        parameters["classifications"] = _join(classifications)

    parameters["q"] = text or ""
    # Example: https://collectionapi.metmuseum.org/public/collection/v1/search?hasImages=true&medium=Brass&q=%22%22
    response = requests.get(
        parse.urljoin(_BASE, "public/collection/v1/search"),
        params=parameters,
    )

    if response.status_code != 200:
        raise ConnectionError(
            f'URL / parameters "{_BASE} / {parameters}" is unreadable. '
            f'Got "{response}" response.'
        )

    data = typing.cast(_SearchResponse, response.json())

    return data["objectIDs"]
