
# Copyright (c) 2026 Yen-Chieh Huang
# SPDX-License-Identifier: MIT


from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import RectangleObject, NameObject, NumberObject, ArrayObject, FloatObject
from collections import Counter

def print_pdf_page_info(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    total = len(reader.pages)

    stats = Counter()
    needs_fix_landscape = 0
    needs_fix_portrait = 0
    for page in reader.pages:
        w = float(page.mediabox.width)
        h = float(page.mediabox.height)
        orient = "Landscape" if w > h else "Portrait"
        rot = page.get("/Rotate", 0)
        stats[(orient, rot)] += 1

        if rot == 270 and h > w:
            needs_fix_landscape += 1
        elif rot == 90 and w > h:
            needs_fix_portrait += 1

    combos = [
        ("Portrait", 0), ("Portrait", 90), ("Portrait", 180), ("Portrait", 270),
        ("Landscape", 0), ("Landscape", 90), ("Landscape", 180), ("Landscape", 270),
    ]

    lines = []
    lines.append(f"PDF has {total} pages\n")
    lines.append("Orientation / Rotation statistics:")

    for orient, rot in combos:
        count = stats.get((orient, rot), 0)
        lines.append(f"  {orient:10s} / {rot:3d}° : {count} pages")

    # 是否全部一致
    non_zero = [(k, v) for k, v in stats.items() if v > 0]
    if len(non_zero) == 1:
        (orient, rot), cnt = non_zero[0]
        lines.append("")
        lines.append("All pages share the same geometry:")
        lines.append(f"  {orient} / {rot}° ({cnt} pages)")
        lines.append("This PDF does NOT require geometry normalization.")

    if needs_fix_landscape or needs_fix_portrait:
        lines.append("")
        lines.append("Suggested action:")
        if needs_fix_landscape:
            lines.append(
                f"  {needs_fix_landscape} page(s) look like fake landscape "
                "(Portrait MediaBox + /Rotate 270) -> call fix_fake_landscape() "
                "/ `main.py fix-fake-landscape`"
            )
        if needs_fix_portrait:
            lines.append(
                f"  {needs_fix_portrait} page(s) look like fake portrait "
                "(Landscape MediaBox + /Rotate 90) -> call fix_fake_portrait() "
                "/ `main.py fix-fake-portrait`"
            )

    return "\n".join(lines)


def print_page1_stamps(pdf_path: str):
    reader = PdfReader(pdf_path)
    page = reader.pages[0]  # 只讀第 1 頁
    
    annots = page.get("/Annots")
    if not annots:
        print("Page 1 has no annotations.")
        return
    
    print(f"Stamps on Page 1 of {pdf_path}:\n")
    for i, annot_ref in enumerate(annots, start=1):
        annot = annot_ref.get_object()
        subtype = annot.get("/Subtype")
        if subtype == "/Stamp":
            rect = annot.get("/Rect")
            name = annot.get("/Name")
            contents = annot.get("/Contents")
            ap = annot.get("/AP")
            matrix = None
            if ap and ap.get("/N") and ap.get("/N").get("/Matrix"):
                matrix = ap.get("/N").get("/Matrix")
            
            print(f"Stamp {i}:")
            print(f"  Rect     : {rect}")
            print(f"  Name     : {name}")
            print(f"  Contents : {contents}")
            print(f"  Matrix   : {matrix}")
            print()



def transform_rect(rect, M):
    """套用仿射矩陣到矩形"""
    x0, y0, x1, y1 = rect
    pts = [(x0, y0), (x1, y1)]
    new_pts = []
    for (x, y) in pts:
        new_x = M[0]*x + M[2]*y + M[4]
        new_y = M[1]*x + M[3]*y + M[5]
        new_pts.append((new_x, new_y))
    (nx0, ny0), (nx1, ny1) = new_pts
    return [min(nx0, nx1), min(ny0, ny1), max(nx0, nx1), max(ny0, ny1)]

def compose_matrix(m1, m2):
    """m1 applied first, then m2 (PDF row-vector convention)."""
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (
        a1*a2 + b1*c2,
        a1*b2 + b1*d2,
        c1*a2 + d1*c2,
        c1*b2 + d1*d2,
        e1*a2 + f1*c2 + e2,
        e1*b2 + f1*d2 + f2,
    )


def fix_stamp_ap_by_inverting_matrix(annot, page_M):
    """Stamp appearance streams are positioned via /Rect + /Matrix + /BBox and
    never go through the page content stream's CTM, so they don't inherit the
    page_M rotation baked into the content (see fix_fake_landscape_safe).
    Previously that rotation came "for free" from the viewer applying /Rotate
    to the whole page (content + annotations) at render time; once /Rotate is
    zeroed out, the same page_M must be composed into the stamp's own /Matrix
    instead: StampLocalCTM_new = StampLocalCTM_old · M (same M used for /Rect,
    not its inverse -- composing with the inverse leaves the stamp rotated an
    extra 180°, i.e. upside down)."""
    ap = annot.get("/AP")
    if not ap:
        return False
    normal = ap.get("/N")

    if not normal:
        return False
    matrix = normal.get("/Matrix")
    if not matrix:
        return False

    try:
        old_matrix = tuple(float(v) for v in matrix)
        new_matrix = compose_matrix(old_matrix, page_M)

        normal_obj = normal.get_object()
        normal_obj[NameObject("/Matrix")] = ArrayObject(FloatObject(v) for v in new_matrix)
        return True
    except Exception as e:
        print("fix_stamp_ap error:", e)
        return False

def _bake_page_rotation(page, tf, M, new_mediabox):
    """Apply a content transform that bakes the page's /Rotate into the
    content stream (setting /Rotate back to 0), and keep annotation /Rect
    and Stamp AP /Matrix in sync with the same M. Returns the number of
    Stamp annotations whose AP /Matrix was fixed."""
    page.add_transformation(tf)
    page.mediabox = RectangleObject(new_mediabox)
    page.rotation = 0

    annots = page.get("/Annots", []) or []
    for aref in annots:
        annot = aref.get_object()
        rect = annot.get("/Rect")
        if rect:
            old = [float(rect[i]) for i in range(4)]
            new = transform_rect(old, M)
            annot[NameObject("/Rect")] = RectangleObject([NumberObject(v) for v in new])

    fixed = 0
    for aref in annots:
        annot = aref.get_object()
        if annot.get("/Subtype") == NameObject("/Stamp"):
            if fix_stamp_ap_by_inverting_matrix(annot, M):
                fixed += 1
    return fixed


def fix_fake_landscape_safe(input_path, output_path):
    """Fix Portrait MediaBox (h>w) + /Rotate=270, i.e. a page that displays
    as landscape only because of the /Rotate flag."""
    reader = PdfReader(input_path)
    writer = PdfWriter()

    for pageno, page in enumerate(reader.pages, start=1):
        rot = page.rotation or 0
        w = float(page.mediabox.width)
        h = float(page.mediabox.height)

        orientation = "Landscape" if w > h else "Portrait"
        print(f"[Page {pageno}] orientation={orientation}, rotation={rot}, size={int(w)}x{int(h)}")

        if rot == 270 and h > w:
            print(f"  → normalize orientation + fix annots/stamps")

            tf = Transformation().rotate(90).translate(h, 0)
            M = (0, 1, -1, 0, h, 0)  # 同步矩陣
            fixed = _bake_page_rotation(page, tf, M, [0, 0, h, w])
            print(f"    → Stamp AP fixed: {fixed}")

            w2 = float(page.mediabox.width)
            h2 = float(page.mediabox.height)
            orientation2 = "Landscape" if w2 > h2 else "Portrait"
            print(f"    → after fix: orientation={orientation2}, rotation={page.rotation}, size={int(w2)}x{int(h2)}")

        writer.add_page(page)

    with open(output_path, "wb") as f:
        writer.write(f)
    print("✅ 完成，輸出：", output_path)


def fix_fake_portrait_safe(input_path, output_path):
    """Fix Landscape MediaBox (w>h) + /Rotate=90, i.e. a page that displays
    as portrait only because of the /Rotate flag. Mirror image of
    fix_fake_landscape_safe."""
    reader = PdfReader(input_path)
    writer = PdfWriter()

    for pageno, page in enumerate(reader.pages, start=1):
        rot = page.rotation or 0
        w = float(page.mediabox.width)
        h = float(page.mediabox.height)

        orientation = "Landscape" if w > h else "Portrait"
        print(f"[Page {pageno}] orientation={orientation}, rotation={rot}, size={int(w)}x{int(h)}")

        if rot == 90 and w > h:
            print(f"  → normalize orientation + fix annots/stamps")

            tf = Transformation().rotate(-90).translate(0, w)
            M = (0, -1, 1, 0, 0, w)  # 同步矩陣
            fixed = _bake_page_rotation(page, tf, M, [0, 0, h, w])
            print(f"    → Stamp AP fixed: {fixed}")

            w2 = float(page.mediabox.width)
            h2 = float(page.mediabox.height)
            orientation2 = "Landscape" if w2 > h2 else "Portrait"
            print(f"    → after fix: orientation={orientation2}, rotation={page.rotation}, size={int(w2)}x{int(h2)}")

        writer.add_page(page)

    with open(output_path, "wb") as f:
        writer.write(f)
    print("✅ 完成，輸出：", output_path)




# input_pdf    = r"C:\Users\user\Desktop\PDFTEST\WrongOrientSinglePage.pdf"
# output_pdf   = r"C:\Users\user\Desktop\PDFTEST\WrongOrientSinglePage_today.pdf"

# print_pdf_page_info(input_pdf)
# #print_page1_stamps(input_pdf)
# fix_fake_landscape_safe(input_pdf, output_pdf)
# print_pdf_page_info(output_pdf)


#API
def analyze(pdf_path: str) -> str:

    return print_pdf_page_info(pdf_path)

def fix_fake_landscape(input_pdf: str, output_pdf: str):
    fix_fake_landscape_safe(input_pdf, output_pdf)

def fix_fake_portrait(input_pdf: str, output_pdf: str):
    fix_fake_portrait_safe(input_pdf, output_pdf)