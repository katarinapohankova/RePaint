from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRect, Qt, Signal
from PySide6.QtGui import QImage, QPainter, QPen
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QSizePolicy, QVBoxLayout, QWidget

def numpy_to_qimage(arr: np.ndarray) -> QImage:
    """
    Konvertuje numpy obraz na QImage vo formáte RGB888
    """
    if arr.ndim == 2:
        #grayscale -> pseudo-RGB
        h, w = arr.shape
        rgb = np.stack([arr] * 3, axis=-1)
    elif arr.ndim == 3:
        h, w, c = arr.shape
        if c == 3:
            rgb = arr
        elif c == 4:
            #zahodíme alfu, stačí nám RGB
            rgb = arr[..., :3]
        else:
            raise ValueError(f"Unsupported channel count: {c}")
    else:
        raise ValueError("Array must be 2D grayscale or 3D RGB/RGBA")

    #zaistíme typ uint8
    if rgb.dtype != np.uint8:
        rgb = np.clip(rgb, 0, 255).astype(np.uint8)

    rgb = np.ascontiguousarray(rgb)
    h, w, _ = rgb.shape

    bytes_per_line = 3 * w
    qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
    return qimg.copy()

#základný klikací widget pre náhľad
class ClickableImageWidget(QWidget):
    """
    Widget, ktorý zobrazí QImage, nechá do neho klikať a zbiera body v súradniciach obrázku
    - používa sa v hlavnom MaskAlignmentDialogu (hrubé kliky)
    - aj v zoom výrezoch (presné kliky)
    """

    point_clicked = Signal(float, float)  #img_x, img_y

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image: QImage | None = None
        self._draw_rect: QRect | None = None
        self._points: list[QPointF] = []

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_image(self, image: QImage) -> None:
        """Nastaví obrázok a zruší predchádzajúce body"""
        self._image = image
        self._points.clear()
        self._draw_rect = None
        self.update()

    def clear_points(self) -> None:
        """Vymaže všetky zobrazené body"""
        self._points.clear()
        self.update()

    def add_point(self, x: float, y: float) -> None:
        """Pridá bod v súradniciach obrázka"""
        self._points.append(QPointF(x, y))
        self.update()

    def _compute_draw_rect(self) -> QRect | None:
        """Vypočíta obdĺžnik, do ktorého sa obrázok vykreslí vo widgete"""
        if self._image is None:
            return None

        widget_rect = self.rect()
        img_size = self._image.size()
        scaled_size = img_size
        scaled_size.scale(widget_rect.size(), Qt.KeepAspectRatio)

        x = widget_rect.x() + (widget_rect.width() - scaled_size.width()) // 2
        y = widget_rect.y() + (widget_rect.height() - scaled_size.height()) // 2

        return QRect(x, y, scaled_size.width(), scaled_size.height())

    def _widget_to_image(self, x: int, y: int) -> tuple[float, float] | None:
        """Prevedie súradnice widgetu na súradnice obrázka"""
        if self._image is None or self._draw_rect is None:
            return None

        rect = self._draw_rect
        if not rect.contains(x, y):
            return None

        u = (x - rect.left()) / rect.width()
        v = (y - rect.top()) / rect.height()

        img_x = u * self._image.width()
        img_y = v * self._image.height()

        img_x = max(0.0, min(float(self._image.width() - 1), img_x))
        img_y = max(0.0, min(float(self._image.height() - 1), img_y))
        return img_x, img_y

    def _image_to_widget(self, img_x: float, img_y: float) -> tuple[int, int] | None:
        """Prevedie súradnice obrázka na súradnice widgetu"""
        if self._image is None or self._draw_rect is None:
            return None

        rect = self._draw_rect

        u = img_x / self._image.width()
        v = img_y / self._image.height()

        x = rect.left() + int(round(u * rect.width()))
        y = rect.top() + int(round(v * rect.height()))
        return x, y

    def paintEvent(self, event) -> None: 
        """Vykreslí obrázok a označené body"""
        painter = QPainter(self)

        if self._image is None:
            painter.fillRect(self.rect(), Qt.black)
            return

        self._draw_rect = self._compute_draw_rect()
        assert self._draw_rect is not None

        painter.fillRect(self.rect(), Qt.black)
        painter.drawImage(self._draw_rect, self._image)

        #body
        pen = QPen(Qt.red)
        pen.setWidth(3)
        painter.setPen(pen)

        for p in self._points:
            pos = self._image_to_widget(p.x(), p.y())
            if pos is None:
                continue
            x, y = pos
            painter.drawEllipse(x - 4, y - 4, 8, 8)

    def mousePressEvent(self, event) -> None:
        """Spracuje kliknutie do obrázka a odošle obrazové súradnice"""
        if event.button() != Qt.LeftButton:
            return
        if self._image is None:
            return

        if self._draw_rect is None:
            self._draw_rect = self._compute_draw_rect()
        if self._draw_rect is None:
            return

        img_pos = self._widget_to_image(int(event.position().x()), int(event.position().y()))

        if img_pos is None:
            return

        img_x, img_y = img_pos
        #zapamätáme si bod na vizuálne zvýraznenie
        self._points.append(QPointF(img_x, img_y))
        self.update()

        #pošleme súradnice
        self.point_clicked.emit(img_x, img_y)


#dialóg na spoločné spresnenie jedného páru bodov
class PairRefinementDialog(QDialog):
    """
    Dialóg, ktorý zobrazí dva priblížené výrezy:
    - vľavo z obrazu
    - vpravo z masky
    užívateľ klikne presný bod v oboch a potvrdí OK
    """

    def __init__(self, image_q: QImage, mask_q: QImage, approx_image_point: tuple[float, float], approx_mask_point: tuple[float, float], crop_half_size: int = 50, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Upřesnit pár bodů")

        self._image_q = image_q
        self._mask_q = mask_q
        self._approx_image_point = approx_image_point
        self._approx_mask_point = approx_mask_point
        self._crop_half_size = crop_half_size

        #výsledné body v súradniciach pôvodných obrázkov
        self._refined_image_point: tuple[float, float] | None = None
        self._refined_mask_point: tuple[float, float] | None = None

        self._build_ui()

    def _crop_around(self, img: QImage, approx_x: float, approx_y: float) -> tuple[QImage, int, int]:
        """Vráti výrez obrázka okolo približne označeného bodu"""
        img_w = img.width()
        img_h = img.height()

        cx = int(round(approx_x))
        cy = int(round(approx_y))

        x0 = max(0, cx - self._crop_half_size)
        y0 = max(0, cy - self._crop_half_size)
        x1 = min(img_w, cx + self._crop_half_size)
        y1 = min(img_h, cy + self._crop_half_size)

        w = max(1, x1 - x0)
        h = max(1, y1 - y0)

        cropped = img.copy(x0, y0, w, h)
        return cropped, x0, y0

    def _build_ui(self) -> None:
        """Vytvorí obsah dialógu pre spresnenie páru bodov"""
        layout = QVBoxLayout(self)

        info_label = QLabel(
            "Klikněte na stejný detail v levém výřezu (obraz) a v pravém výřezu (maska)\n"
            "Oba kliky musí být provedeny, než potvrdíte OK"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        images_layout = QHBoxLayout()
        layout.addLayout(images_layout)

        #obraz – orez
        img_crop, self._img_x0, self._img_y0 = self._crop_around(self._image_q, self._approx_image_point[0], self._approx_image_point[1])
        self.img_widget = ClickableImageWidget(self)
        self.img_widget.set_image(img_crop)
        images_layout.addWidget(self.img_widget)

        #maska – orez
        mask_crop, self._mask_x0, self._mask_y0 = self._crop_around(self._mask_q, self._approx_mask_point[0], self._approx_mask_point[1])
        self.mask_widget = ClickableImageWidget(self)
        self.mask_widget.set_image(mask_crop)
        images_layout.addWidget(self.mask_widget)

        #stavové labely
        status_layout = QHBoxLayout()
        layout.addLayout(status_layout)
        self.img_status = QLabel("Bod na obraze: nevybrán")
        self.mask_status = QLabel("Bod na masce: nevybrán")
        status_layout.addWidget(self.img_status)
        status_layout.addWidget(self.mask_status)

        #tlačidlá
        buttons_layout = QHBoxLayout()
        layout.addLayout(buttons_layout)

        cancel_button = QPushButton("Zrušit")
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_button)

        buttons_layout.addStretch(1)

        self.ok_button = QPushButton("OK")
        self.ok_button.setEnabled(False)
        self.ok_button.clicked.connect(self.accept)
        buttons_layout.addWidget(self.ok_button)

        #signály
        self.img_widget.point_clicked.connect(self._on_img_click)
        self.mask_widget.point_clicked.connect(self._on_mask_click)

        self.resize(800, 500)

    def _on_img_click(self, local_x: float, local_y: float) -> None:
        """Uloží spresnený bod na obraze"""
        #mapujeme späť do súradníc pôvodného obrazu
        self._refined_image_point = (self._img_x0 + local_x, self._img_y0 + local_y)
        self.img_status.setText("Bod na obraze: vybrán")
        self._update_ok_enabled()

    def _on_mask_click(self, local_x: float, local_y: float) -> None:
        """Uloží spresnený bod na maske"""
        self._refined_mask_point = (self._mask_x0 + local_x, self._mask_y0 + local_y)
        self.mask_status.setText("Bod na masce: vybrán")
        self._update_ok_enabled()

    def _update_ok_enabled(self) -> None:
        """Povolí OK až po výbere oboch bodov"""
        self.ok_button.setEnabled(self._refined_image_point is not None and self._refined_mask_point is not None)

    def get_refined_points(self) -> tuple[tuple[float, float] | None, tuple[float, float] | None]:
        """Vráti spresnený bod na obraze a na maske"""
        return self._refined_image_point, self._refined_mask_point


#hlavný dialóg na výber viacerých párov bodov
class MaskAlignmentDialog(QDialog):
    """
    Dialóg na zarovnanie masky k obrazu pomocou párov bodov
    - používateľ klikne hrubý bod na obraze vľavo
    - klikne hrubý bod na maske vpravo
    - v otvorenom okne vyberie presný bod v oboch výrezoch a potvrdí OK
    - po potvrdení vznikne jeden pár bodov
    počet párov musí byť aspoň 4 a počet bodov na obraze aj maske musí byť rovnaký
    """

    def __init__(self, image_arr: np.ndarray, mask_arr: np.ndarray, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Zarovnání masky k obrazu")

        self.image_q = numpy_to_qimage(image_arr)
        self.mask_q = numpy_to_qimage(mask_arr)

        #finálne body (po spresnení)
        self.image_points: list[tuple[float, float]] = []
        self.mask_points: list[tuple[float, float]] = []

        #dočasné hrubé kliky
        self.pending_image_point: tuple[float, float] | None = None
        self.pending_mask_point: tuple[float, float] | None = None

        self.min_points: int = 4
        self.max_points: int = 20

        self._build_ui()

    def _build_ui(self) -> None:
        """Vytvorí hlavné rozhranie dialógu"""
        layout = QVBoxLayout(self)

        info_label = QLabel(
            "Vyberte 4-20 dobře rozpoznatelných bodů (detaily) na obraze a na masce.\n"
            "Postup pro každý bod:\n"
            "   1) Klikněte na detail na levém obrázku (obraz)\n"
            "   2) Klikněte na stejný detail na pravém obrázku (maska)\n"
            "   3) V otevřeném okně vyberte přesný bod v obou výřezech a potvrďte OK\n"
            "Počet bodů musí být stejný na obraze i masce (minimálně 4 páry)"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        images_layout = QHBoxLayout()
        layout.addLayout(images_layout)

        #ľavý obrázok
        left_layout = QVBoxLayout()
        images_layout.addLayout(left_layout)

        self.image_widget = ClickableImageWidget(self)
        self.image_widget.set_image(self.image_q)
        left_layout.addWidget(self.image_widget)

        self.image_status = QLabel("Páry bodů: 0")
        left_layout.addWidget(self.image_status)

        #pravá maska
        right_layout = QVBoxLayout()
        images_layout.addLayout(right_layout)

        self.mask_widget = ClickableImageWidget(self)
        self.mask_widget.set_image(self.mask_q)
        right_layout.addWidget(self.mask_widget)

        self.mask_status = QLabel("Páry bodů: 0")
        right_layout.addWidget(self.mask_status)

        #spodné tlačidlá
        buttons_layout = QHBoxLayout()
        layout.addLayout(buttons_layout)

        self.clear_button = QPushButton("Vymazat všechny body")
        self.clear_button.clicked.connect(self._on_clear_points)
        buttons_layout.addWidget(self.clear_button)

        self.remove_last_button = QPushButton("Vymazat poslední bod")
        self.remove_last_button.clicked.connect(self._on_remove_last_point)
        buttons_layout.addWidget(self.remove_last_button)

        buttons_layout.addStretch(1)

        self.cancel_button = QPushButton("Zrušit")
        self.cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_button)

        self.ok_button = QPushButton("OK")
        self.ok_button.setEnabled(False)
        self.ok_button.clicked.connect(self.accept)
        buttons_layout.addWidget(self.ok_button)

        #signály
        self.image_widget.point_clicked.connect(self._on_image_coarse_click)
        self.mask_widget.point_clicked.connect(self._on_mask_coarse_click)

        self.resize(1000, 650)

    def _redraw_points(self) -> None:
        """
        Znovu nakreslí body v náhľadoch podľa potvrdených párov
        """
        self.image_widget.clear_points()
        self.mask_widget.clear_points()

        for pt in self.image_points:
            self.image_widget.add_point(pt[0], pt[1])

        for pt in self.mask_points:
            self.mask_widget.add_point(pt[0], pt[1])

    #pre hrubé kliky
    def _on_image_coarse_click(self, x: float, y: float) -> None:
        """Uloží hrubý bod na obraze"""
        #ak už máme pending bod na obraze, nahradíme ho novým
        self.pending_image_point = (x, y)
        self._redraw_points()
        self.image_widget.add_point(x, y)

        #ak už bol pending mask bod, otvoríme refine dialóg
        if self.pending_mask_point is not None:
            self._open_pair_refine_dialog()

    def _on_mask_coarse_click(self, x: float, y: float) -> None:
        """Uloží hrubý bod na maske alebo upozorní na zlé poradie kliknutia"""
        if self.pending_image_point is None:
            QMessageBox.information(self, "Info",
                "Nejprve klikněte na stejný detail na levém obrázku (obraz), potom na pravém obrázku (maska)",
            )
            #hrubý klik na maske ignorujeme, dokým nemáme bod na obraze
            self._redraw_points()
            return

        self.pending_mask_point = (x, y)
        #máme oba hrubé body ->otvoríme refine
        self._open_pair_refine_dialog()

    def _open_pair_refine_dialog(self) -> None:
        """Otvorí dialóg na presné určenie jedného páru bodov"""
        if self.pending_image_point is None or self.pending_mask_point is None:
            return

        dlg = PairRefinementDialog(image_q=self.image_q, mask_q=self.mask_q, approx_image_point=self.pending_image_point, approx_mask_point=self.pending_mask_point, crop_half_size=50, parent=self)
        result = dlg.exec()

        if result == QDialog.Accepted:
            img_pt, mask_pt = dlg.get_refined_points()
            if img_pt is not None and mask_pt is not None:
                if len(self.image_points) >= self.max_points:
                    QMessageBox.warning(self, "Varování",
                        f"Bylo dosaženo maximálního počtu bodů ({self.max_points})",
                    )
                else:
                    self.image_points.append(img_pt)
                    self.mask_points.append(mask_pt)
                    self._update_status_labels()
        #vyčistíme pending body bez ohľadu na to, či používateľ dal OK alebo Cancel
        self.pending_image_point = None
        self.pending_mask_point = None

        self._redraw_points()
        self._update_ok_enabled()


    def _on_clear_points(self) -> None:
        """Vymaže všetky potvrdené aj rozpracované body"""
        self.image_points = []
        self.mask_points = []
        self.pending_image_point = None
        self.pending_mask_point = None

        self._redraw_points()
        self._update_status_labels()
        self._update_ok_enabled()

    def _on_remove_last_point(self) -> None:
        """
        Vymaže posledný potvrdený pár bodov
        """
        if not self.image_points or not self.mask_points:
            return

        #odstránime posledný pár
        self.image_points.pop()
        self.mask_points.pop()

        #treba prekresliť body a aktualizovať stav
        self._redraw_points()
        self._update_status_labels()
        self._update_ok_enabled()

    def _update_status_labels(self) -> None:
        """Aktualizuje počet potvrdených párov bodov"""
        n_pairs = len(self.image_points)
        self.image_status.setText(f"Páry bodů: {n_pairs}")
        self.mask_status.setText(f"Páry bodů: {n_pairs}")

    def _update_ok_enabled(self) -> None:
        """Povolí OK až pri dostatočnom počte párov bodov"""
        n_img = len(self.image_points)
        n_mask = len(self.mask_points)
        enabled = n_img >= self.min_points and n_mask >= self.min_points and n_img == n_mask
        self.ok_button.setEnabled(enabled)

    def get_points(self) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
        """
        Vráti body na obraze a na maske v poradí, v akom boli potvrdené
        poradie bodov je dôležité, lebo podľa neho sa počíta homografia
        """
        return list(self.image_points), list(self.mask_points)