from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from collections.abc import Iterable

import numpy as np
from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image as RLImage, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from rp_restore.core.layers import Layer, LayerRole
from rp_restore.core.project_model import Project


@dataclass
class ReportMetadata:
    """Voliteľné údaje zadané používateľom pred vytvorením reportu"""
    restorer_name: str = ""
    artwork_title: str = ""
    artwork_author: str = ""
    user_notes: str = ""

@dataclass
class _ReportFonts:
    regular: str
    bold: str

_FONT_CACHE: _ReportFonts | None = None

def generate_report(project: Project, pdf_path: str | Path, metadata: ReportMetadata | None = None) -> None:
    """
    Vygeneruje PDF report aktuálneho stavu projektu
    Report obsahuje:
    -základné údaje o projekte a diele
    -poznámky užívateľa
    -vstupné dáta
    -výsledný zložený obraz
    -samostatné pracovné vrstvy
    """
    metadata = metadata or ReportMetadata()

    pdf_path = Path(pdf_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    fonts = _register_report_fonts()
    styles = _build_styles(fonts)

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=1.6 * cm,
        leftMargin=1.6 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="Report - digitální rekonstrukce obrazu",
    )

    story: list = []
    _add_title_page(story, project, metadata, styles)
    _add_input_data_section(story, project, styles)
    _add_result_section(story, project, styles)
    _add_layers_section(story, project, styles)

    doc.build(
        story,
        onFirstPage=lambda c, d: _draw_footer(c, d, fonts),
        onLaterPages=lambda c, d: _draw_footer(c, d, fonts),
    )


def _register_report_fonts() -> _ReportFonts:
    """
    Zaregistruje font s podporou českých znakov
    Windows používa Arial alebo Segoe UI, Linux DejaVu alebo Liberation
    """
    global _FONT_CACHE
    if _FONT_CACHE is not None:
        return _FONT_CACHE

    regular_candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
        Path("/Library/Fonts/Arial.ttf"),
    ]
    bold_candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/segoeuib.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
        Path("/Library/Fonts/Arial Bold.ttf"),
    ]

    regular_path = next((p for p in regular_candidates if p.exists()), None)
    bold_path = next((p for p in bold_candidates if p.exists()), None)

    if regular_path is None:
        _FONT_CACHE = _ReportFonts(regular="Helvetica", bold="Helvetica-Bold")
        return _FONT_CACHE

    pdfmetrics.registerFont(TTFont("ReportRegular", str(regular_path)))

    if bold_path is not None:
        pdfmetrics.registerFont(TTFont("ReportBold", str(bold_path)))
        bold_name = "ReportBold"
    else:
        bold_name = "ReportRegular"

    _FONT_CACHE = _ReportFonts(regular="ReportRegular", bold=bold_name)
    return _FONT_CACHE


def _build_styles(fonts: _ReportFonts) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()

    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontName=fonts.bold,
            fontSize=20,
            leading=24,
            alignment=TA_CENTER,
            spaceAfter=14,
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle",
            parent=base["Normal"],
            fontName=fonts.regular,
            fontSize=10,
            leading=14,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#444444"),
            spaceAfter=18,
        ),
        "h1": ParagraphStyle(
            "ReportHeading1",
            parent=base["Heading1"],
            fontName=fonts.bold,
            fontSize=14,
            leading=18,
            spaceBefore=14,
            spaceAfter=8,
            textColor=colors.HexColor("#222222"),
        ),
        "h2": ParagraphStyle(
            "ReportHeading2",
            parent=base["Heading2"],
            fontName=fonts.bold,
            fontSize=11,
            leading=14,
            spaceBefore=8,
            spaceAfter=5,
            textColor=colors.HexColor("#333333"),
        ),
        "body": ParagraphStyle(
            "ReportBody",
            parent=base["BodyText"],
            fontName=fonts.regular,
            fontSize=9,
            leading=12,
            alignment=TA_LEFT,
            spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "ReportSmall",
            parent=base["BodyText"],
            fontName=fonts.regular,
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#555555"),
        ),
        "table_label": ParagraphStyle(
            "ReportTableLabel",
            parent=base["BodyText"],
            fontName=fonts.bold,
            fontSize=8.5,
            leading=11,
        ),
        "table_value": ParagraphStyle(
            "ReportTableValue",
            parent=base["BodyText"],
            fontName=fonts.regular,
            fontSize=8.5,
            leading=11,
        ),
    }


def _draw_footer(canvas, doc, fonts: _ReportFonts) -> None:
    """Nakreslí číslo strany"""
    canvas.saveState()
    canvas.setFont(fonts.regular, 8)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawRightString(A4[0] - 1.6 * cm, 0.9 * cm, f"{doc.page}")
    canvas.restoreState()


#sekcie reportu
def _add_title_page(story: list, project: Project, metadata: ReportMetadata, styles: dict[str, ParagraphStyle]) -> None:
    story.append(Paragraph("Report - digitální rekonstrukce obrazu", styles["title"]))
    story.append(Paragraph("Dokumentace aktuálního stavu projektu v okamžiku exportu.", styles["subtitle"]))

    basic_rows = [
        ("Název projektu", project.project_name),
        ("Datum vytvoření reportu", datetime.now().strftime("%d.%m.%Y %H:%M")),
        ("Restaurátor", metadata.restorer_name),
        ("Název díla", metadata.artwork_title),
        ("Autor díla", metadata.artwork_author),
    ]

    basic_rows.extend(_layer_count_rows(project))

    story.append(Paragraph("Základní údaje", styles["h1"]))
    story.append(_info_table(basic_rows, styles))

    notes = metadata.user_notes.strip()
    if notes:
        story.append(Spacer(1, 0.2 * cm))
        story.append(Paragraph("Poznámky", styles["h1"]))
        story.append(Paragraph(_escape_paragraph(notes).replace("\n", "<br/>"), styles["body"]))

    story.append(PageBreak())


def _add_input_data_section(story: list, project: Project, styles: dict[str, ParagraphStyle]) -> None:
    story.append(Paragraph("Vstupní data", styles["h1"]))
    story.append(Paragraph("Původní obraz a maska poškození, ze kterých návrh rekonstrukce vychází.", styles["body"]))

    original = _project_original_rgb(project)
    damage = _damage_original_mask(project)

    images: list[tuple[str, np.ndarray]] = []
    if original is not None:
        images.append(("Původní obraz", original))

    if damage is not None:
        images.append(("Maska poškození", _mask_to_rgb(damage)))

    if original is not None and damage is not None and damage.shape == original.shape[:2]:
        images.append(("Původní obraz se zvýrazněným poškozením", _apply_overlay(original, damage, alpha=0.35)))

    _add_image_grid(story, images, styles)
    story.append(PageBreak())


def _add_result_section(story: list, project: Project, styles: dict[str, ParagraphStyle]) -> None:
    story.append(Paragraph("Výsledný stav", styles["h1"]))
    story.append(Paragraph("Výsledný stav odpovídá aktuálně viditelným vrstvám v projektu.", styles["body"]))

    composited = _safe_composited_image(project)
    remaining_visible = _remaining_damage_mask(project, visible_only=True)

    images: list[tuple[str, np.ndarray]] = []
    if composited is not None:
        images.append(("Aktuální obraz", composited))

    if composited is not None and remaining_visible is not None and remaining_visible.shape == composited.shape[:2]:
        images.append(("Aktuální obraz se zvýrazněným poškozením", _apply_overlay(composited, remaining_visible, alpha=0.35)))
        images.append(("Zbývající maska poškození", _mask_to_rgb(remaining_visible)))

    _add_image_grid(story, images, styles)

    damage = _damage_original_mask(project)
    if damage is not None:
        filled_visible = _filled_mask_from_layers(project, visible_only=True)
        if filled_visible is None:
            filled_visible = np.zeros_like(damage, dtype=bool)

        damage_pixels = int(damage.sum())
        filled_pixels = int((damage & filled_visible).sum())
        remaining_pixels = max(0, damage_pixels - filled_pixels)
        coverage = (filled_pixels / damage_pixels * 100.0) if damage_pixels > 0 else 0.0

        rows = [
            ("Celková plocha masky poškození", f"{damage_pixels} px"),
            ("Vyplněná část ve viditelných vrstvách malby", f"{filled_pixels} px"),
            ("Zbývající nevyplněná část", f"{remaining_pixels} px"),
            ("Pokrytí masky poškození", f"{coverage:.1f} %"),
        ]
        story.append(_info_table(rows, styles))

    story.append(PageBreak())

def _add_layers_section(story: list, project: Project, styles: dict[str, ParagraphStyle]) -> None:
    layers = _ordered_report_layers(project)

    story.append(Paragraph("Samostatné vrstvy", styles["h1"]))
    if not layers:
        story.append(Paragraph("Projekt neobsahuje žádné pracovní vrstvy.", styles["body"]))
        return

    for layer in layers:
        story.extend(_layer_block(layer, styles))


#obrázky a masky
def _project_original_rgb(project: Project) -> np.ndarray | None:
    try:
        original = project.get_original_image()
    except Exception:
        original = None

    if original is None:
        return None

    return _to_rgb(original)


def _safe_composited_image(project: Project) -> np.ndarray | None:
    try:
        composited = project.get_current_composited_image()
    except Exception:
        try:
            composited = project.composited_image()
        except Exception:
            return None
    return _to_rgb(composited)

def _damage_original_mask(project: Project) -> np.ndarray | None:
    mask = getattr(project, "damage_original_mask", None)
    if mask is None:
        return None
    mask = np.asarray(mask)
    if mask.ndim == 3:
        mask = mask[..., 0]
    if mask.ndim != 2:
        return None

    return mask.astype(bool)


def _filled_mask_from_layers(project: Project, visible_only: bool) -> np.ndarray | None:
    damage = _damage_original_mask(project)
    if damage is None:
        return None

    h, w = damage.shape
    filled = np.zeros((h, w), dtype=bool)

    for layer in project.get_paint_layers():
        if visible_only and not layer.meta.visible:
            continue
        if layer.image.shape[:2] != (h, w):
            continue

        filled |= (layer.image[..., 3] > 0) & damage

    return filled & damage


def _remaining_damage_mask(project: Project, visible_only: bool) -> np.ndarray | None:
    damage = _damage_original_mask(project)
    if damage is None:
        return None

    filled = _filled_mask_from_layers(project, visible_only=visible_only)
    if filled is None:
        return damage.copy()

    return damage & ~filled


def _to_rgb(arr: np.ndarray) -> np.ndarray:
    arr = np.asarray(arr)

    if arr.ndim == 2:
        out = np.stack([arr, arr, arr], axis=-1)
        return _as_uint8(out)

    if arr.ndim == 3 and arr.shape[2] == 3:
        return _as_uint8(arr)

    if arr.ndim == 3 and arr.shape[2] == 4:
        rgba = _as_uint8(arr).astype(np.float32)
        rgb = rgba[..., :3]
        alpha = rgba[..., 3:4] / 255.0
        bg = np.full_like(rgb, 255.0)
        out = rgb * alpha + bg * (1.0 - alpha)
        return np.clip(out, 0, 255).astype(np.uint8)

    raise ValueError("Unsupported image shape for report")


def _as_uint8(arr: np.ndarray) -> np.ndarray:
    arr = np.asarray(arr)
    if arr.dtype == np.uint8:
        return arr.copy()
    return np.clip(arr, 0, 255).astype(np.uint8)


def _mask_to_rgb(mask: np.ndarray) -> np.ndarray:
    mask = np.asarray(mask).astype(bool)
    out = np.zeros((mask.shape[0], mask.shape[1], 3), dtype=np.uint8)
    out[mask] = np.array([255, 255, 255], dtype=np.uint8)
    return out


def _apply_overlay(rgb: np.ndarray, mask: np.ndarray, alpha: float = 0.35) -> np.ndarray:
    rgb = _to_rgb(rgb).astype(np.float32)
    mask = np.asarray(mask).astype(bool)

    if mask.shape != rgb.shape[:2]:
        return rgb.astype(np.uint8)

    overlay_color = np.array([255, 255, 255], dtype=np.float32)
    out = rgb.copy()
    out[mask] = out[mask] * (1.0 - alpha) + overlay_color * alpha
    return np.clip(out, 0, 255).astype(np.uint8)


def _layer_preview_rgb(layer: Layer) -> np.ndarray:
    rgba = layer.image.astype(np.float32)
    rgb = rgba[..., :3]
    alpha = rgba[..., 3:4] / 255.0
    bg = _checkerboard(layer.image.shape[0], layer.image.shape[1]).astype(np.float32)
    out = rgb * alpha + bg * (1.0 - alpha)
    return np.clip(out, 0, 255).astype(np.uint8)


def _checkerboard(h: int, w: int, cell: int = 18) -> np.ndarray:
    yy, xx = np.indices((h, w))
    board = ((xx // cell + yy // cell) % 2).astype(np.uint8)
    light = np.array([230, 230, 230], dtype=np.uint8)
    dark = np.array([200, 200, 200], dtype=np.uint8)
    return np.where(board[..., None] == 0, light, dark)


def _image_flowable(arr: np.ndarray, max_width: float, max_height: float) -> RLImage:
    img = PILImage.fromarray(_to_rgb(arr), mode="RGB")
    iw, ih = img.size
    scale = min(max_width / iw, max_height / ih, 1.0)

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    flowable = RLImage(buf, width=iw * scale, height=ih * scale)
    flowable._rp_restore_buffer = buf  #udrží BytesIO počas generovania PDF
    return flowable


def _add_image_grid(story: list, images: list[tuple[str, np.ndarray]], styles: dict[str, ParagraphStyle]) -> None:
    if not images:
        story.append(Paragraph("Pro tuto část nejsou dostupná žádná obrazová data.", styles["body"]))
        return

    page_width = A4[0] - 3.2 * cm
    col_width = (page_width - 0.5 * cm) / 2
    max_img_h = 7.2 * cm

    rows = []
    current_row = []

    for title, arr in images:
        block = [
            Paragraph(_escape_paragraph(title), styles["h2"]),
            _image_flowable(arr, max_width=col_width, max_height=max_img_h),
        ]
        current_row.append(block)

        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []

    if current_row:
        current_row.append("")
        rows.append(current_row)

    table = Table(rows, colWidths=[col_width, col_width], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    story.append(table)


#vrstvy
def _ordered_report_layers(project: Project) -> list[Layer]:
    paint_layers = sorted(project.get_paint_layers(), key=lambda l: l.meta.order)
    visible_paint = [layer for layer in paint_layers if layer.meta.visible]
    hidden_paint = [layer for layer in paint_layers if not layer.meta.visible]

    edge_layers = _get_edge_layers(project)
    edge_layers = sorted(edge_layers, key=lambda l: l.meta.order)

    return visible_paint + hidden_paint + edge_layers


def _get_edge_layers(project: Project) -> list[Layer]:
    get_one = getattr(project, "get_edge_layer", None)
    if callable(get_one):
        edge = get_one()
        return [edge] if edge is not None else []

    get_many = getattr(project, "get_edge_layers", None)
    if callable(get_many):
        return list(get_many())

    return [layer for layer in getattr(project, "layers", []) if layer.meta.role == LayerRole.EDGE]


def _layer_block(layer: Layer, styles: dict[str, ParagraphStyle]) -> list:
    visibility = "viditelná" if layer.meta.visible else "skrytá"
    title = f"{layer.meta.name} ({_layer_role_label(layer.meta.role)})"

    rows = [
        ("Typ", _layer_role_label(layer.meta.role)),
        ("Viditelnost", visibility),
        ("Krytí", f"{float(layer.meta.opacity) * 100:.0f} %"),
    ]

    info = _info_table(rows, styles, col_widths=[3.8 * cm, 4.2 * cm])
    preview = _image_flowable(_layer_preview_rgb(layer), max_width=8.2 * cm, max_height=7.0 * cm)

    table = Table([[info, preview]], colWidths=[8.2 * cm, 8.4 * cm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )

    return [KeepTogether([Paragraph(_escape_paragraph(title), styles["h2"]), table, Spacer(1, 0.25 * cm)])]

def _layer_role_label(role: LayerRole) -> str:
    if role == LayerRole.BACKGROUND:
        return "Původní obraz"
    if role == LayerRole.PAINT:
        return "Malba"
    if role == LayerRole.EDGE:
        return "Hrany"
    return str(role.value)

def _layer_count_rows(project: Project) -> list[tuple[str, str]]:
    return [("Počet vrstev celkem", str(len(project.layers)))]

def _info_table(rows: Iterable[tuple[str, object]], styles: dict[str, ParagraphStyle], col_widths: list[float] | None = None) -> Table:
    data = []
    for label, value in rows:
        value_str = str(value).strip() if value is not None else ""
        if value_str == "":
            value_str = "neuvedeno"
        data.append(
            [
                Paragraph(_escape_paragraph(str(label)), styles["table_label"]),
                Paragraph(_escape_paragraph(value_str), styles["table_value"]),
            ]
        )

    if col_widths is None:
        col_widths = [5.6 * cm, 11.0 * cm]

    table = Table(data, colWidths=col_widths, hAlign="LEFT")
    table.setStyle(_default_table_style())
    return table

def _default_table_style() -> TableStyle:
    return TableStyle(
        [
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D0D0D0")),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F0F0F0")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
    )

def _escape_paragraph(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
