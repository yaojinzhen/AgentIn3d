"""Static file checks and fresh runtime evidence for current saved artifacts."""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, UnidentifiedImageError

from inf_agent.workspace.contracts import ContractError, load_json
from inf_agent.execution.gltf_validation import validate_mesh_document
from inf_agent.execution.gltf_materials import validate_material_document
from inf_agent.execution.binary_reader import BinaryChunk

ARTIFACT_VALIDATION_SCHEMA_VERSION = "1.1"
GLB_JSON_CHUNK = 0x4E4F534A
GLB_BIN_CHUNK = 0x004E4942
MAX_GLB_JSON_BYTES = 16 * 1024 * 1024


class ArtifactValidationError(ValueError):
    """Raised when a final artifact cannot be completely parsed or reopened."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _binary_mask(image):
    luminance = image.convert("L").point(lambda x: 255 if x >= 128 else 0)
    alpha = (
        image.convert("RGBA").getchannel("A").point(lambda x: 255 if x >= 128 else 0)
    )
    return ImageChops.multiply(luminance, alpha)


def validate_png(
    path: Path, *, expected_resolution: tuple[int, int], mask: bool = False
) -> dict[str, Any]:
    """Verify and fully decode a PNG with exact expected dimensions."""

    try:
        with Image.open(path) as image:
            if image.format != "PNG":
                raise ArtifactValidationError(f"{path.name} is not a PNG")
            size = tuple(image.size)
            image.verify()
        with Image.open(path) as image:
            image.load()
            decoded_size = tuple(image.size)
            foreground = (
                sum(pixel > 0 for pixel in _binary_mask(image).getdata())
                if mask
                else None
            )
    except (
        OSError,
        UnidentifiedImageError,
        SyntaxError,
        ValueError,
        Image.DecompressionBombError,
    ) as error:
        raise ArtifactValidationError(
            f"cannot completely decode {path.name}: {error}"
        ) from error
    if size != expected_resolution or decoded_size != expected_resolution:
        raise ArtifactValidationError(
            f"{path.name} dimensions {size} do not match {expected_resolution}"
        )
    return {
        "path": path.as_posix(),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
        "width": size[0],
        "height": size[1],
        "decoded": True,
        "foreground_pixels": foreground,
    }


def validate_glb(path: Path) -> dict[str, Any]:
    """Read bounded JSON and stream only referenced BIN data plus the file hash."""

    def fail(message):
        raise ArtifactValidationError(message)

    try:
        size = path.stat().st_size
        with path.open("rb") as stream:
            header = stream.read(12)
            if len(header) != 12:
                fail("GLB header is truncated")
            magic, version, declared_size = struct.unpack("<4sII", header)
            if magic != b"glTF" or version != 2 or declared_size != size:
                fail("GLB header or declared length is invalid")
            consumed = 12
            chunks = []
            document = None
            binary = None
            while consumed < size:
                chunk_header = stream.read(8)
                if len(chunk_header) != 8:
                    fail("GLB chunk header is truncated")
                length, kind = struct.unpack("<II", chunk_header)
                if length % 4 or length > size - consumed - 8:
                    fail("GLB chunk length is invalid")
                expected = GLB_JSON_CHUNK if not chunks else GLB_BIN_CHUNK
                if kind not in (GLB_JSON_CHUNK, GLB_BIN_CHUNK):
                    fail("GLB contains an unsupported chunk type")
                if len(chunks) >= 2 or kind != expected:
                    fail(
                        "GLB mesh profile requires exactly one JSON followed by one BIN chunk"
                    )
                if kind == GLB_JSON_CHUNK:
                    if length > MAX_GLB_JSON_BYTES:
                        fail("GLB JSON chunk exceeds 16 MiB")
                    payload = stream.read(length)
                    if len(payload) != length:
                        fail("GLB JSON chunk payload is truncated")
                    document = json.loads(payload.decode("utf-8").rstrip(" \t\r\n\x00"))
                else:
                    binary = BinaryChunk(stream, stream.tell(), length)
                    stream.seek(length, 1)
                chunks.append(kind)
                consumed += 8 + length
            if consumed != size or len(chunks) != 2:
                fail("GLB mesh profile requires exactly one JSON and one BIN chunk")
            if not isinstance(document, dict):
                fail("GLB JSON root must be an object")
            asset = document.get("asset")
            if not isinstance(asset, dict) or asset.get("version") != "2.0":
                fail("GLB JSON asset.version must equal 2.0")
            semantic = validate_mesh_document(document, binary, fail)
            material_info = validate_material_document(document, binary, fail)
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        struct.error,
        ValueError,
    ) as error:
        if isinstance(error, ArtifactValidationError):
            raise
        raise ArtifactValidationError(
            f"cannot completely parse {path.name}: {error}"
        ) from error
    return {
        "path": path.as_posix(),
        "bytes": size,
        "sha256": _sha256(path),
        "chunks": len(chunks),
        "scenes": len(document["scenes"]),
        "nodes": len(document["nodes"]),
        "meshes": len(document["meshes"]),
        "parsed": True,
        **semantic,
        **material_info,
    }


def validate_blend_header(path: Path) -> dict[str, Any]:
    """Validate the complete Blender file header before runtime reopen."""

    try:
        size = path.stat().st_size
        with path.open("rb") as stream:
            header = stream.read(12)
    except OSError as error:
        raise ArtifactValidationError(f"cannot read {path.name}: {error}") from error
    if (
        len(header) != 12
        or header[:7] != b"BLENDER"
        or header[7:8] not in {b"_", b"-"}
        or header[8:9] not in {b"v", b"V"}
        or not header[9:12].isdigit()
    ):
        raise ArtifactValidationError("BLEND header is invalid")
    return {
        "path": path.as_posix(),
        "bytes": size,
        "sha256": _sha256(path),
        "pointer_size": 64 if header[7:8] == b"-" else 32,
        "endianness": "little" if header[8:9] == b"v" else "big",
        "blender_version": header[9:12].decode("ascii"),
        "header_valid": True,
        "coverage": "header_only",
        "reopened": False,
    }


def _verify_reopen_report(path: Path, files: dict[str, Any]) -> dict[str, Any]:
    try:
        report = load_json(path)
    except ContractError as error:
        raise ArtifactValidationError(
            f"cannot read Blender reopen report: {error}"
        ) from error
    details = report.get("errors", [])
    if not isinstance(details, list) or any(not isinstance(x, str) for x in details):
        raise ArtifactValidationError("Blender reopen report errors must be strings")
    if (
        report.get("schema_version") != ARTIFACT_VALIDATION_SCHEMA_VERSION
        or report.get("success") is not True
    ):
        raise ArtifactValidationError("Blender reopen failed: " + "; ".join(details))
    for kind in ("blend", "glb"):
        if kind not in files:
            continue
        proof = report.get(kind)
        if (
            not isinstance(proof, dict)
            or proof.get("sha256") != files[kind]["sha256"]
            or proof.get("reopened") is not True
            or any(
                not isinstance(proof.get(key), int)
                or isinstance(proof[key], bool)
                or proof[key] < 1
                for key in ("mesh_objects", "vertices", "faces")
            )
        ):
            raise ArtifactValidationError(
                f"Blender reopen proof for {kind} is missing, stale or has no target mesh faces"
            )
    return report


def validate_final_artifacts(
    output_dir: Path,
    *,
    expected_resolution: tuple[int, int],
    expected_outputs: list[dict[str, Any]],
) -> dict[str, Any]:
    """Keep file parsing, sampled focus evidence and actual reopen facts distinct."""
    files, masks = {}, {}
    errors = []
    file_errors = []
    for item in expected_outputs:
        path = output_dir / item["path"]
        kind, name = item["kind"], item["id"]
        try:
            if kind in ("png", "mask"):
                files[name] = validate_png(
                    path, expected_resolution=expected_resolution, mask=kind == "mask"
                )
                if kind == "mask":
                    masks.setdefault(item["view_id"], {})[item["mask"]] = files[name]
            elif kind == "glb":
                files[name] = validate_glb(path)
            elif kind == "blend":
                files[name] = validate_blend_header(path)
        except (ArtifactValidationError, OSError) as error:
            file_errors.append(f"{item['path']}: {error}")
    errors.extend(file_errors)
    focus = []
    view_ids = {item["view_id"] for item in expected_outputs if item["kind"] == "mask"}
    for view_id in sorted(view_ids):
        pair = masks.get(view_id, {})
        visible = pair.get("visible", {}).get("foreground_pixels", 0) or 0
        potential = pair.get("potential", {}).get("foreground_pixels", 0) or 0
        outside = None
        if 0 < visible <= potential:
            try:
                with (
                    Image.open(pair["visible"]["path"]) as v,
                    Image.open(pair["potential"]["path"]) as p,
                ):
                    outside = sum(
                        pixel > 0
                        for pixel in ImageChops.subtract(
                            _binary_mask(v), _binary_mask(p)
                        ).getdata()
                    )
            except (OSError, ValueError):
                outside = None
        passed = 0 < visible <= potential and outside == 0
        focus.append(
            dict(
                view_id=view_id,
                passed=passed,
                visible_pixels=visible,
                potential_pixels=potential,
                visible_outside_potential_pixels=outside,
                visible_fraction=visible / potential if potential else None,
            )
        )
        if not passed:
            errors.append(
                f"focus {view_id} has missing, empty or inconsistent visible/potential mask evidence"
            )
    reopen = None
    requested_3d = [
        item["id"] for item in expected_outputs if item["kind"] in ("blend", "glb")
    ]
    if requested_3d and all(kind in files for kind in requested_3d):
        try:
            reopen = _verify_reopen_report(output_dir / "artifact_reopen.json", files)
            for kind in requested_3d:
                files[kind].update(
                    reopened=True,
                    coverage="static_checks_and_runtime_reopen",
                    file_usable=True,
                )
        except ArtifactValidationError as error:
            errors.append(str(error))
    return {
        "schema_version": ARTIFACT_VALIDATION_SCHEMA_VERSION,
        "success": not errors,
        "files_usable": not file_errors and (not requested_3d or reopen is not None),
        "render_status": "VALIDATED"
        if any(i["kind"] == "png" for i in expected_outputs)
        else "NOT_REQUESTED",
        "expected_outputs": expected_outputs,
        "files": files,
        "focus_evidence": {"success": all(i["passed"] for i in focus), "views": focus},
        "blender_reopen": reopen,
        "errors": errors,
    }
