"""
Helpers for shaping listing payloads returned to the frontend.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


def hydrate_listing_images(listing: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert embedded listing_photos rows into the image array expected by the UI.
    """
    row = dict(listing or {})
    photos = row.pop("listing_photos", None)

    images: List[str] = []
    if isinstance(photos, list):
        ordered = sorted(
            [photo for photo in photos if isinstance(photo, dict)],
            key=lambda photo: (photo.get("sort_order") is None, photo.get("sort_order", 0)),
        )
        images = [photo["photo_url"] for photo in ordered if photo.get("photo_url")]

    row["images"] = images
    return row


def hydrate_listing_image_collection(listings: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [hydrate_listing_images(listing) for listing in listings]
