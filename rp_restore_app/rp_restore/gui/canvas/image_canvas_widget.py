from __future__ import annotations

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QImage, QPainter, QPaintEvent, QTransform, QWheelEvent, QPen
from PySide6.QtWidgets import QWidget

from typing import List, Optional, TYPE_CHECKING

import numpy as np

from .overlay_highlight import draw_region_highlights, draw_selection_highlight

if TYPE_CHECKING:
    from rp_restore.core.warnings import RegionReference
from rp_restore.core.regions import RegionMap

class ImageCanvasWidget(QWidget):
    """
    reprezentuje hlavnú kresliacu plochu
    zatiaľ:
      - drží aktuálny QImage
      - vykreslí ho v paintEvent
      - bez myšovej interakcie, zoomu a posúvania
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.current_image: QImage | None = None

        #zatiaľ len tak
        self.zoom_factor: float = 1.0
        self.pan_x: int = 0
        self.pan_y: int = 0
        self._panning: bool = False
        self._last_mouse_pos: QPoint | None = None

        self.controller = None

        self.selection_mask: np.ndarray | None = None
        self._highlight_regions: List["RegionReference"] = []

        self.setMinimumSize(400, 300)
        self.setAutoFillBackground(True)
        self.auto_fill_preview_region_map: RegionMap | None = None
        self.auto_fill_preview_region_ids: set[int] = set()
        self.auto_fill_preview_excluded_region_ids: set[int] = set()

        self.lasso_preview_points: list[tuple[int, int]] = []
        self.show_lasso_preview: bool = False

    def set_image(self, image: QImage) -> None:
        """Nastaví nový obraz a prekreslí widget."""
        self.current_image = image
        self.update()

    def set_controller(self, controller) -> None:
        """nastaví controller, ktorému budeme posielať udalosti myši"""
        self.controller = controller

    def set_selection_mask(self, mask: np.ndarray | None) -> None:
        """
        Nastaví masku selection (v image súradniciach)
        """
        self.selection_mask = mask
        self.update()

    def set_highlight_for_regions(self, regions: Optional[List["RegionReference"]]) -> None:
        """
        Nastaví zoznam regionov na zvýraznenie -podľa warningu...
        """
        self._highlight_regions = regions or []
        self.update()

    def patch_region(self, patch: QImage, x: int, y: int) -> None:
        """
        nahrá do current_image malý patch na pozíciu (x, y) v obrazových súradniciach a potom prekreslí widget (so zoom/pan)
        """
        if self.current_image is None or self.current_image.isNull():
            return
        if patch is None or patch.isNull():
            return

        painter = QPainter(self.current_image)
        try:
            painter.drawImage(x, y, patch)
        finally:
            painter.end()
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None: 
        painter = QPainter(self)

        #vyplníme pozadie -čiernou
        painter.fillRect(self.rect(), Qt.black)

        if self.current_image is None or self.current_image.isNull():
            return
        
        img = self.current_image
        img_w = img.width()
        img_h = img.height()

        #stred
        w = self.width()
        h = self.height()
        cx = w / 2
        cy = h / 2

        transform = QTransform()
        transform.translate(cx, cy)
        transform.scale(self.zoom_factor, self.zoom_factor)
        transform.translate(-img_w / 2 + self.pan_x, -img_h / 2 + self.pan_y)

        painter.setTransform(transform)

        #zatiaľ bez zoomu 
        #nakreslíme obraz do ľavého horného rohu
        painter.drawImage(0, 0, img)

        #auto-fill preview overlay
        if self.auto_fill_preview_region_map is not None and self.auto_fill_preview_region_ids:
            label_image = self.auto_fill_preview_region_map.label_image
            painter.setPen(Qt.NoPen)
            #polopriehľadná tyrkysová
            active_color = Qt.cyan
            excluded_color = Qt.darkGray

            h, w = label_image.shape
            for y in range(h):
                for x in range(w):
                    region_id = int(label_image[y, x])
                    if region_id in self.auto_fill_preview_region_ids:
                        color = excluded_color if region_id in self.auto_fill_preview_excluded_region_ids else active_color
                        painter.fillRect(x, y, 1, 1, color)
        
        #selection overlay –polopriehľadná maska
        if self.selection_mask is not None:
            draw_selection_highlight(painter, self.selection_mask)
        
        #overlay highlight (warningy / selection)
        if self._highlight_regions:
            draw_region_highlights(painter, self._highlight_regions)

        #lasso overlay
        if self.show_lasso_preview and len(self.lasso_preview_points) >= 2:
            pen = QPen(Qt.yellow)
            pen.setWidth(2)
            painter.setPen(pen)

            pts = self.lasso_preview_points

            for i in range(1, len(pts)):
                x0, y0 = pts[i - 1]
                x1, y1 = pts[i]
                painter.drawLine(x0, y0, x1, y1)

            last_x, last_y = pts[-1]
            painter.setBrush(Qt.yellow)
            painter.drawEllipse(last_x - 2, last_y - 2, 4, 4)


    def get_current_transform(self) -> QTransform:
        """
        vráti transformáciu ktorou sa kreslí obraz (widget -> image)
        """
        if self.current_image is None:
            return QTransform()

        img_w = self.current_image.width()
        img_h = self.current_image.height()

        w = self.width()
        h = self.height()
        cx = w / 2
        cy = h / 2

        t = QTransform()
        t.translate(cx, cy)
        t.scale(self.zoom_factor, self.zoom_factor)
        t.translate(-img_w / 2 + self.pan_x, -img_h / 2 + self.pan_y)
        return t

    def widget_to_image(self, x: float, y: float) -> tuple[float, float]:
        """
        prevedie widget súradnice (x, y) na image súradnice
        Vráti (ix, iy) v image priestore (float)
        """
        t = self.get_current_transform()
        inv, ok = t.inverted()
        if not ok:
            return -1.0, -1.0

        ix, iy = inv.map(x, y)
        return ix, iy

    #--------myš--------
    def _map_widget_to_image(self, x: int, y: int) -> tuple[int, int] | None:
        """
        prepočet súradníc z widgetu na obrázok
        zatiaľ:
          - žiadny zoom
          - obraz je v ľavom hornom rohu
          - ak klikne mimo obrázok, vráti None
        """
        if self.current_image is None:
            return None

        img_w = self.current_image.width()
        img_h = self.current_image.height()

        if x < 0 or y < 0 or x >= img_w or y >= img_h:
            return None

        return int(x), int(y)

    def mousePressEvent(self, event):  
        if self.controller is None or self.current_image is None:
            return
        
        if event.button() in (Qt.MiddleButton, Qt.RightButton):
            self._panning = True
            self._last_mouse_pos = event.pos()
            return

        xw = event.position().x()
        yw = event.position().y()
        ix, iy = self.widget_to_image(xw, yw)
        self.controller.on_canvas_mouse_press(int(ix), int(iy), event.buttons(), event.modifiers())

    def mouseMoveEvent(self, event): 
        if self.controller is None or self.current_image is None:
            return

        if self._panning and self._last_mouse_pos is not None:
            dx = event.position().x() - self._last_mouse_pos.x()
            dy = event.position().y() - self._last_mouse_pos.y()

            #prevedieme posun z widget priestoru do image priestoru 
            if self.zoom_factor != 0:
                self.pan_x += dx / self.zoom_factor
                self.pan_y += dy / self.zoom_factor

            self._last_mouse_pos = event.pos()
            self.update()
            return

        xw = event.position().x()
        yw = event.position().y()
        ix, iy = self.widget_to_image(xw, yw)
        self.controller.on_canvas_mouse_move(int(ix), int(iy), event.buttons(), event.modifiers())

    def mouseReleaseEvent(self, event):  
        if self.controller is None or self.current_image is None:
            return
        
        if self._panning and (event.button() == Qt.MiddleButton or event.button() == Qt.LeftButton):
            self._panning = False
            self._last_mouse_pos = None
            return

        xw = event.position().x()
        yw = event.position().y()
        ix, iy = self.widget_to_image(xw, yw)
        self.controller.on_canvas_mouse_release(int(ix), int(iy), event.buttons(), event.modifiers())

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self.current_image is None:
            return

        #zoom okolo kurzoru
        angle = event.angleDelta().y()
        if angle == 0:
            return

        #starý zoom
        old_zoom = self.zoom_factor
        #krok –napr. 1.1
        factor = 1.1 if angle > 0 else 1 / 1.1
        #limit
        new_zoom = max(0.1, min(old_zoom * factor, 20.0))

        #dynamické min/max podľa veľkosti obrázka a okna
        img_w = self.current_image.width()
        img_h = self.current_image.height()
        w = self.width()
        h = self.height()

        if img_w > 0 and img_h > 0 and w > 0 and h > 0:
            #scale, pri ktorom sa obraz práve zmestí do okna
            fit = min(w / img_w, h / img_h)

            #bude sa dať odzoomovať (4x)
            min_zoom = fit * 0.25
            #a priblížiť (20x)
            max_zoom = fit * 20.0
        else:
            min_zoom = 0.01
            max_zoom = 100.0

        new_zoom = max(min_zoom, min(old_zoom * factor, max_zoom))

        #nechceme zoomovať, ak by sa nič nezmenilo
        if abs(new_zoom - old_zoom) < 1e-6:
            return

        #chceme, aby bod pod kurzorom zostal na rovnakom mieste
        xw = event.position().x()
        yw = event.position().y()

        #image coords pred zoomom
        ix_before, iy_before = self.widget_to_image(xw, yw)

        self.zoom_factor = new_zoom
        #po zmene zoomu počítame späť nové image coords
        ix_after, iy_after = self.widget_to_image(xw, yw)
        #rozdiel kompenzujeme panom
        self.pan_x += (ix_after - ix_before)
        self.pan_y += (iy_after - iy_before)

        self.update()

    def fit_to_window(self) -> None:
        """
        nastaví zoom tak, aby sa obrázok vošiel do okna a bol vycentrovaný
        """
        if self.current_image is None:
            return

        img_w = self.current_image.width()
        img_h = self.current_image.height()
        if img_w == 0 or img_h == 0:
            return

        w = self.width()
        h = self.height()
        if w == 0 or h == 0:
            return

        #scale tak, aby sa zmestil celý obraz
        sx = w / img_w
        sy = h / img_h
        self.zoom_factor = min(sx, sy)

        #pan nastavený na 0 = stred obrázku do stredu okna
        self.pan_x = 0.0
        self.pan_y = 0.0

        self.update()

    def set_auto_fill_preview_regions(self, region_map: RegionMap | None, region_ids: set[int], excluded_region_ids: set[int] | None = None) -> None:
        """
        Nastaví oblasti, ktoré sa majú zvýrazniť ako kandidáti pre auto-fill
        """
        self.auto_fill_preview_region_map = region_map
        self.auto_fill_preview_region_ids = set(region_ids)
        self.auto_fill_preview_excluded_region_ids = (set(excluded_region_ids) if excluded_region_ids is not None else set())
        self.update()

    def clear_auto_fill_preview_regions(self) -> None:
        """
        Zruší zvýraznenie kandidátov pre auto-fill
        """
        self.auto_fill_preview_region_map = None
        self.auto_fill_preview_region_ids.clear()
        self.auto_fill_preview_excluded_region_ids.clear()
        self.update()

    def set_lasso_preview_points(self, points: list[tuple[int, int]]) -> None:
        """
        Nastaví body dočasného lasa, ktoré sa kreslí počas ťahu myšou
        """
        self.lasso_preview_points = list(points)
        self.show_lasso_preview = len(self.lasso_preview_points) >= 1
        self.update()

    def clear_lasso_preview(self) -> None:
        """
        Zruší dočasný preview obrys lasa
        """
        self.lasso_preview_points = []
        self.show_lasso_preview = False
        self.update()