"""Bounded request validation performed before a workspace is allocated."""

from __future__ import annotations

import math
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable

MAX_REQUEST_TEXT_BYTES = 64 * 1024
MAX_FORBIDDEN_ITEMS = 64
MAX_FORBIDDEN_ITEM_BYTES = 1024
MAX_REFERENCE_IMAGE_BYTES = 16 * 1024 * 1024
MAX_REFERENCE_IMAGE_DIMENSION = 8192
MAX_REFERENCE_IMAGE_PIXELS = 40_000_000
SUPPORTED_IMAGE_EXTENSIONS = {".jpeg", ".jpg", ".png", ".webp"}
MEDIA_TYPE_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


class InputValidationError(ValueError):
    """Raised when immutable request input exceeds the current boundary."""


@dataclass(frozen=True)
class ValidatedImage:
    suffix: str
    media_type: str
    payload: bytes
    width: int
    height: int

    @property
    def pixels(self) -> int:
        return self.width * self.height


def _utf8_size(value: str, *, label: str) -> int:
    try:
        return len(value.encode("utf-8"))
    except UnicodeEncodeError as error:
        raise InputValidationError(f"{label} is not valid UTF-8 text") from error


def normalize_request_text(
    prompt: str, forbidden: Iterable[str]
) -> tuple[str, list[str]]:
    """Normalize prompt/forbidden text and enforce one combined byte budget."""

    if not isinstance(prompt, str) or not prompt.strip():
        raise InputValidationError("prompt must be non-empty")
    normalized_prompt = prompt.strip() + "\n"
    items: list[str] = []
    for index, item in enumerate(forbidden):
        if not isinstance(item, str) or not item.strip():
            raise InputValidationError("forbidden items must be non-empty strings")
        normalized = item.strip()
        size = _utf8_size(normalized, label=f"forbidden[{index}]")
        if size > MAX_FORBIDDEN_ITEM_BYTES:
            raise InputValidationError(
                f"forbidden[{index}] exceeds {MAX_FORBIDDEN_ITEM_BYTES} bytes"
            )
        if normalized not in items:
            items.append(normalized)
    if len(items) > MAX_FORBIDDEN_ITEMS:
        raise InputValidationError(
            f"forbidden contains more than {MAX_FORBIDDEN_ITEMS} unique items"
        )
    total = _utf8_size(normalized_prompt, label="prompt") + sum(
        _utf8_size(item, label="forbidden item") for item in items
    )
    if total > MAX_REQUEST_TEXT_BYTES:
        raise InputValidationError(
            "prompt and forbidden text exceed the combined "
            f"{MAX_REQUEST_TEXT_BYTES} byte limit"
        )
    return normalized_prompt, items


def normalize_dimensions(
    dimensions: dict[str, float] | None,
) -> dict[str, float]:
    if dimensions is None:
        return {}
    if not isinstance(dimensions, dict):
        raise InputValidationError("explicit dimensions must be a JSON object")
    unexpected = sorted(set(dimensions) - {"width", "depth", "height"})
    if unexpected:
        raise InputValidationError(
            "unsupported explicit dimensions: " + ", ".join(unexpected)
        )
    result: dict[str, float] = {}
    for name, value in dimensions.items():
        try:
            finite = math.isfinite(value) if isinstance(value, (int, float)) else False
        except OverflowError:
            finite = False
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not finite
            or value <= 0
        ):
            raise InputValidationError(
                f"explicit dimension {name} must be a finite JSON number greater than zero"
            )
        result[name] = float(value)
    return result


def _read_bounded(path: Path) -> bytes:
    try:
        size = path.stat().st_size
        if size < 1:
            raise InputValidationError("reference image is empty")
        if size > MAX_REFERENCE_IMAGE_BYTES:
            raise InputValidationError(
                f"reference image exceeds {MAX_REFERENCE_IMAGE_BYTES} bytes"
            )
        return path.read_bytes()
    except InputValidationError:
        raise
    except OSError as error:
        raise InputValidationError(f"cannot read reference image: {error}") from error


def validate_reference_image(
    path: Path | str, *, expected_media_type: str | None = None
) -> ValidatedImage:
    """Fully decode a bounded PNG/JPEG/WebP and return frozen metadata."""

    source = Path(path)
    suffix = source.suffix.casefold()
    if suffix not in SUPPORTED_IMAGE_EXTENSIONS:
        raise InputValidationError("reference image must be PNG, JPEG, or WebP")
    payload = _read_bounded(source)
    try:
        from PIL import Image, UnidentifiedImageError

        with Image.open(BytesIO(payload)) as image:
            detected = image.format
            width, height = image.size
            frames = getattr(image, "n_frames", 1)
            if frames != 1:
                raise InputValidationError("reference image must contain exactly one frame")
            expected_format = {
                ".png": "PNG",
                ".jpg": "JPEG",
                ".jpeg": "JPEG",
                ".webp": "WEBP",
            }[suffix]
            if detected != expected_format:
                raise InputValidationError(
                    "reference image content does not match its extension"
                )
            if (
                width < 1
                or height < 1
                or width > MAX_REFERENCE_IMAGE_DIMENSION
                or height > MAX_REFERENCE_IMAGE_DIMENSION
                or width * height > MAX_REFERENCE_IMAGE_PIXELS
            ):
                raise InputValidationError(
                    "reference image dimensions exceed the configured limits"
                )
            image.verify()
        with Image.open(BytesIO(payload)) as decoded:
            decoded.load()
    except InputValidationError:
        raise
    except (OSError, SyntaxError, ValueError, UnidentifiedImageError) as error:
        raise InputValidationError(
            f"reference image cannot be fully decoded: {type(error).__name__}: {error}"
        ) from error
    media_type = MEDIA_TYPE_BY_SUFFIX[suffix]
    if expected_media_type is not None and media_type != expected_media_type:
        raise InputValidationError("reference image media type does not match request.json")
    return ValidatedImage(suffix, media_type, payload, width, height)


def require_finite_numbers(value: Any, *, path: str = "request") -> None:
    """Reject non-finite numeric values anywhere in a request structure."""

    if isinstance(value, bool) or value is None or isinstance(value, str):
        return
    if isinstance(value, (int, float)):
        try:
            finite = math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite:
            raise InputValidationError(f"{path} contains a non-finite number")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            require_finite_numbers(item, path=f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            require_finite_numbers(item, path=f"{path}[{index}]")
