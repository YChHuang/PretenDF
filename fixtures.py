
# Copyright (c) 2026 Yen-Chieh Huang
# SPDX-License-Identifier: MIT

# Generates test-fixture PDFs reproducing the "fake orientation" bugs
# core.py diagnoses/fixes: MediaBox shape + /Rotate flag disagree, with
# stamp/annotation geometry desynced to match.

import math

from pypdf import PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    NumberObject,
    RectangleObject,
    TextStringObject,
)

from core import transform_rect

US_LETTER_PORTRAIT = (612, 792)
US_LETTER_LANDSCAPE = (792, 612)


def _font_resources(writer):
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
        NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
    })
    font_ref = writer._add_object(font)
    return DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})
    })


def _page_content(w, h, label, marker=44):
    # coordinates are logical/correct-orientation; red marker=bottom-left, blue=top-left
    lines = [
        "q",
        "0.85 0.1 0.1 rg",
        f"0 0 {marker} {marker} re f",
        "0.1 0.35 0.9 rg",
        f"0 {h - marker} {marker} {marker} re f",
        "0 0 0 RG 3 w",
        f"3 3 {w - 6} {h - 6} re S",
        "BT /F1 20 Tf 0 0 0 rg",
        f"1 0 0 1 {marker + 14} {h - 34} Tm ({label}) Tj",
        "ET",
        "Q",
    ]
    return "\n".join(lines).encode("latin-1")


def _rotation_matrix(deg):
    rad = math.radians(deg)
    c, s = round(math.cos(rad), 6), round(math.sin(rad), 6)
    return (c, s, -s, c, 0.0, 0.0)


def _add_stamp_annotation(writer, resources, rect, local_rotation_deg):
    # AP carries its own /Matrix rotation, the pattern
    # fix_stamp_ap_by_inverting_matrix() expects to find and neutralize
    bbox_w = bbox_h = 120
    content = (
        f"q 0.95 0.75 0.1 rg 0 0 {bbox_w} {bbox_h} re f "
        f"0 0 0 RG 2 w 1 1 {bbox_w - 2} {bbox_h - 2} re S "
        f"BT /F1 14 Tf 0 0 0 rg 14 {bbox_h // 2 - 7} Td (STAMP) Tj ET Q"
    ).encode("latin-1")

    ap_stream = DecodedStreamObject()
    ap_stream.set_data(content)
    ap_stream[NameObject("/Type")] = NameObject("/XObject")
    ap_stream[NameObject("/Subtype")] = NameObject("/Form")
    ap_stream[NameObject("/FormType")] = NumberObject(1)
    ap_stream[NameObject("/BBox")] = RectangleObject([0, 0, bbox_w, bbox_h])
    ap_stream[NameObject("/Matrix")] = ArrayObject(
        FloatObject(v) for v in _rotation_matrix(local_rotation_deg)
    )
    ap_stream[NameObject("/Resources")] = resources
    ap_ref = writer._add_object(ap_stream)

    annot = DictionaryObject({
        NameObject("/Type"): NameObject("/Annot"),
        NameObject("/Subtype"): NameObject("/Stamp"),
        NameObject("/Rect"): RectangleObject(rect),
        NameObject("/Name"): NameObject("/Approved"),
        NameObject("/Contents"): TextStringObject("Fixture stamp"),
        NameObject("/AP"): DictionaryObject({NameObject("/N"): ap_ref}),
        NameObject("/F"): NumberObject(4),
    })
    return writer._add_object(annot)


def _add_square_annotation(writer, rect):
    annot = DictionaryObject({
        NameObject("/Type"): NameObject("/Annot"),
        NameObject("/Subtype"): NameObject("/Square"),
        NameObject("/Rect"): RectangleObject(rect),
        NameObject("/C"): ArrayObject([FloatObject(0), FloatObject(0), FloatObject(0)]),
        NameObject("/IC"): ArrayObject([FloatObject(1), FloatObject(0.9), FloatObject(0.2)]),
        NameObject("/BS"): DictionaryObject({NameObject("/W"): NumberObject(2)}),
        NameObject("/Contents"): TextStringObject("Fixture annotation"),
        NameObject("/F"): NumberObject(4),
    })
    return writer._add_object(annot)


def _annotation_layout(w, h):
    stamp_rect = [w * 0.72, h * 0.74, w * 0.72 + 120, h * 0.74 + 120]
    square_rect = [w * 0.68, h * 0.06, w * 0.94, h * 0.20]
    return stamp_rect, square_rect


def _generate_fake_page(output_path, correct_w, correct_h, rotate, label, stamp_rotation_deg):
    # Mc maps logical/correct-space coords into the broken MediaBox; it is
    # the algebraic inverse of the M that fix_fake_landscape_safe() applies
    # when un-rotating a real file (see README_chi.md "修正旋轉方向").
    broken_w, broken_h = correct_h, correct_w

    if rotate == 270:
        # inverse of Transformation().rotate(90).translate(h, 0) with h = broken_h
        Mc = (0.0, -1.0, 1.0, 0.0, 0.0, float(broken_h))
    elif rotate == 90:
        Mc = (0.0, 1.0, -1.0, 0.0, float(broken_w), 0.0)
    else:
        raise ValueError("rotate must be 90 or 270")

    writer = PdfWriter()
    page = writer.add_blank_page(width=broken_w, height=broken_h)
    page.rotation = rotate

    resources = _font_resources(writer)
    page[NameObject("/Resources")] = resources

    content_bytes = _page_content(correct_w, correct_h, label)
    cm_prefix = "%.6f %.6f %.6f %.6f %.6f %.6f cm\n" % Mc
    stream = DecodedStreamObject()
    stream.set_data(("q\n" + cm_prefix).encode("latin-1") + content_bytes + b"\nQ")
    page[NameObject("/Contents")] = writer._add_object(stream)

    stamp_rect_logical, square_rect_logical = _annotation_layout(correct_w, correct_h)
    stamp_rect = transform_rect(stamp_rect_logical, Mc)
    square_rect = transform_rect(square_rect_logical, Mc)

    stamp_ref = _add_stamp_annotation(writer, resources, stamp_rect, stamp_rotation_deg)
    square_ref = _add_square_annotation(writer, square_rect)
    page[NameObject("/Annots")] = ArrayObject([stamp_ref, square_ref])

    with open(output_path, "wb") as f:
        writer.write(f)


# API
def generate_fake_landscape(output_path: str):
    # Portrait MediaBox (612x792) + /Rotate=270 -> displays as Landscape.
    # fix(generate_fake_landscape(...)) round-trips back to a clean page.
    broken_w, broken_h = US_LETTER_PORTRAIT
    _generate_fake_page(
        output_path, correct_w=broken_h, correct_h=broken_w, rotate=270,
        label="FAKE LANDSCAPE FIXTURE", stamp_rotation_deg=270,
    )


def generate_fake_portrait(output_path: str):
    # Landscape MediaBox (792x612) + /Rotate=90 -> displays as Portrait.
    # fix_fake_portrait(generate_fake_portrait(...)) round-trips back to a clean page.
    broken_w, broken_h = US_LETTER_LANDSCAPE
    _generate_fake_page(
        output_path, correct_w=broken_h, correct_h=broken_w, rotate=90,
        label="FAKE PORTRAIT FIXTURE", stamp_rotation_deg=90,
    )
