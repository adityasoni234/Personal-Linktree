"""SVG sanitisation.

Uploaded SVGs are XML documents that browsers execute: they can carry
`<script>`, event handlers, external entity references and `url(javascript:...)`
payloads. Nothing uploaded is ever served back verbatim — every SVG is parsed
with a hardened parser, rebuilt from an element/attribute allowlist, and
re-serialised.
"""

from __future__ import annotations

import re
from xml.etree import ElementTree as ET

from defusedxml.ElementTree import ParseError as DefusedParseError
from defusedxml.ElementTree import fromstring as safe_fromstring

from app.core.errors import ValidationError

SVG_NS = "http://www.w3.org/2000/svg"

MAX_SVG_BYTES = 512 * 1024
MAX_ELEMENTS = 4_000
MAX_DEPTH = 32

ALLOWED_ELEMENTS = frozenset(
    {
        "svg", "g", "defs", "title", "desc", "symbol", "use",
        "path", "rect", "circle", "ellipse", "line", "polyline", "polygon",
        "text", "tspan",
        "linearGradient", "radialGradient", "stop",
        "clipPath", "mask",
    }
)

ALLOWED_ATTRIBUTES = frozenset(
    {
        "id", "class", "viewBox", "width", "height", "version",
        "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry",
        "d", "points", "transform", "gradientTransform", "gradientUnits",
        "spreadMethod", "offset", "preserveAspectRatio",
        "fill", "fill-opacity", "fill-rule",
        "stroke", "stroke-width", "stroke-opacity", "stroke-linecap",
        "stroke-linejoin", "stroke-dasharray", "stroke-dashoffset", "stroke-miterlimit",
        "opacity", "color", "stop-color", "stop-opacity",
        "clip-path", "clip-rule", "mask", "mask-type",
        "font-family", "font-size", "font-weight", "font-style",
        "text-anchor", "dominant-baseline", "letter-spacing",
        "style",
    }
)

# CSS properties permitted inside a `style` attribute. Anything else is dropped.
ALLOWED_STYLE_PROPERTIES = frozenset(
    {
        "fill", "fill-opacity", "fill-rule", "stroke", "stroke-width",
        "stroke-opacity", "stroke-linecap", "stroke-linejoin", "stroke-dasharray",
        "opacity", "color", "stop-color", "stop-opacity", "font-family",
        "font-size", "font-weight", "font-style", "text-anchor", "display",
        "visibility", "mix-blend-mode",
    }
)

_UNSAFE_VALUE = re.compile(
    r"(javascript:|vbscript:|data:|expression\s*\(|behaviou?r\s*:|@import|<|&#)",
    re.IGNORECASE,
)
_CSS_URL = re.compile(r"url\s*\(", re.IGNORECASE)
_DOCTYPE_OR_PI = re.compile(r"<!DOCTYPE|<\?xml-stylesheet|<!ENTITY", re.IGNORECASE)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _attribute_name(name: str) -> str:
    """Return the local name, keeping the namespace visible for href checks."""
    if name.startswith("{"):
        namespace, local = name[1:].split("}", 1)
        if "xlink" in namespace:
            return f"xlink:{local}"
        return local
    return name


def _sanitize_style(value: str) -> str | None:
    declarations: list[str] = []
    for declaration in value.split(";"):
        if ":" not in declaration:
            continue
        prop, _, raw_value = declaration.partition(":")
        prop = prop.strip().lower()
        raw_value = raw_value.strip()
        if prop not in ALLOWED_STYLE_PROPERTIES:
            continue
        if _UNSAFE_VALUE.search(raw_value):
            continue
        # `url(#id)` is legitimate (gradients); any other url() can fetch or
        # execute, so drop the whole declaration.
        if _CSS_URL.search(raw_value) and not raw_value.lstrip().lower().startswith("url(#"):
            continue
        declarations.append(f"{prop}:{raw_value}")
    return ";".join(declarations) or None


def _sanitize_attributes(element: ET.Element) -> None:
    cleaned: dict[str, str] = {}
    for raw_name, raw_value in element.attrib.items():
        name = _attribute_name(raw_name)
        lowered = name.lower()

        if lowered.startswith("on"):
            continue  # event handlers
        if lowered in {"href", "xlink:href"}:
            # Only same-document references survive.
            if raw_value.strip().startswith("#"):
                cleaned["href"] = raw_value.strip()
            continue
        if lowered.startswith("xmlns"):
            continue  # re-added at serialisation time
        if name not in ALLOWED_ATTRIBUTES:
            continue

        value = raw_value.strip()
        if name == "style":
            sanitised = _sanitize_style(value)
            if sanitised:
                cleaned["style"] = sanitised
            continue
        if _UNSAFE_VALUE.search(value):
            continue
        if _CSS_URL.search(value) and not value.lower().startswith("url(#"):
            continue
        cleaned[name] = value

    element.attrib.clear()
    element.attrib.update(cleaned)


def _sanitize_tree(element: ET.Element, depth: int, budget: list[int]) -> None:
    if depth > MAX_DEPTH:
        raise ValidationError("SVG structure is nested too deeply")

    _sanitize_attributes(element)

    for child in list(element):
        budget[0] -= 1
        if budget[0] < 0:
            raise ValidationError("SVG contains too many elements")

        name = _local_name(child.tag)
        if name not in ALLOWED_ELEMENTS:
            # Drops <script>, <foreignObject>, <image>, <animate>, <style>,
            # <set>, <handler> and anything else not explicitly permitted.
            element.remove(child)
            continue
        # Namespace normalisation: everything we keep lives in the SVG namespace.
        child.tag = f"{{{SVG_NS}}}{name}"
        _sanitize_tree(child, depth + 1, budget)


def sanitize_svg(raw: bytes) -> bytes:
    """Return a safe SVG document, or raise `ValidationError`."""
    if len(raw) > MAX_SVG_BYTES:
        raise ValidationError(
            f"SVG must be smaller than {MAX_SVG_BYTES // 1024} KB",
            details={"field": "file"},
        )

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError("SVG file is not valid UTF-8 text") from exc

    if _DOCTYPE_OR_PI.search(text):
        # Belt and braces: the hardened parser rejects these too.
        raise ValidationError("SVG must not declare a DOCTYPE, entities or stylesheets")

    try:
        root = safe_fromstring(
            text, forbid_dtd=True, forbid_entities=True, forbid_external=True
        )
    except DefusedParseError as exc:
        raise ValidationError("SVG file could not be parsed safely") from exc
    except Exception as exc:  # noqa: BLE001 - any parser complaint is a rejection
        raise ValidationError("SVG file could not be parsed safely") from exc

    if _local_name(root.tag) != "svg":
        raise ValidationError("File is not an SVG document")

    root.tag = f"{{{SVG_NS}}}svg"
    _sanitize_tree(root, depth=0, budget=[MAX_ELEMENTS])

    # A viewBox is required so the logo can be scaled into the QR reserve area.
    if "viewBox" not in root.attrib:
        width = root.attrib.get("width", "").rstrip("px") or "100"
        height = root.attrib.get("height", "").rstrip("px") or "100"
        try:
            root.attrib["viewBox"] = f"0 0 {float(width)} {float(height)}"
        except ValueError:
            root.attrib["viewBox"] = "0 0 100 100"

    ET.register_namespace("", SVG_NS)
    serialised = ET.tostring(root, encoding="utf-8", xml_declaration=False)
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + serialised


def svg_dimensions(svg: bytes) -> tuple[int, int]:
    """Best-effort intrinsic size, used only for reporting."""
    try:
        root = safe_fromstring(svg.decode("utf-8"), forbid_dtd=True)
    except Exception:  # noqa: BLE001
        return (0, 0)
    view_box = root.attrib.get("viewBox")
    if view_box:
        parts = re.split(r"[ ,]+", view_box.strip())
        if len(parts) == 4:
            try:
                return (int(float(parts[2])), int(float(parts[3])))
            except ValueError:
                pass
    return (0, 0)
