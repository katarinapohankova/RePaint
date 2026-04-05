from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import cv2

import numpy as np
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog, QMessageBox

from rp_restore.core.color_correction import COLORCHECKER_SRGB_24, estimate_correction_matrix_affine, rms_rgb
from rp_restore.io.image_io import load_image


@dataclass
class ColorCheckerResult:
    matrix: np.ndarray  #(3,4)
    rms_error: float    #RMS v RGB


class _ClickImageLabel(QLabel):
    """
    okno pre obrázok na zakliknutie rohov colorcheckeru
    -ukladáme body v image súradniciach
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("border: 1px solid #555; background: #222;")
        self._qimage: QImage | None = None
        self._pixmap: QPixmap | None = None

        self.points: list[tuple[int, int]] = []  #image coords
        self._last_drawn_pixmap: QPixmap | None = None

    def set_image(self, qimage: QImage) -> None:
        self._qimage = qimage
        self.points = []
        self._update_pixmap()

    def _update_pixmap(self) -> None:
        if self._qimage is None:
            self.clear()
            return
        pix = QPixmap.fromImage(self._qimage)
        pix = pix.scaled(self.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self._pixmap = pix
        self._redraw_with_points()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_pixmap()

    def mousePressEvent(self, event) -> None:
        if self._qimage is None or self._pixmap is None:
            return
        if event.button() != Qt.LeftButton:
            return

        #map widget click -> pixmap coords -> image coords
        w = self.width()
        h = self.height()
        pw = self._pixmap.width()
        ph = self._pixmap.height()

        #pixmap je centrovaný
        x0 = (w - pw) // 2
        y0 = (h - ph) // 2

        mx = int(event.position().x()) - x0
        my = int(event.position().y()) - y0

        if mx < 0 or my < 0 or mx >= pw or my >= ph:
            return

        #scale pixmap->image
        iw = self._qimage.width()
        ih = self._qimage.height()
        ix = int(round(mx * (iw / pw)))
        iy = int(round(my * (ih / ph)))

        self.points.append((ix, iy))
        self._redraw_with_points()

    def _redraw_with_points(self) -> None:
        if self._pixmap is None:
            return
        pix = QPixmap(self._pixmap)
        self.setPixmap(pix)


class ColorCheckerDialog(QDialog):
    """
    Dialóg:
      -načíta kalibračnú fotku s ColorChecker tabuľkou
      -po kliknutí na 4 rohy (LH, PH, PD, LD) spočíta korekciu 
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("ColorChecker – kalibrace")

        self._image_path: str | None = None
        self._image_rgb: np.ndarray | None = None 
        self._result: ColorCheckerResult | None = None

        layout = QVBoxLayout(self)

        info = QLabel(
            "Postup:\n"
            "1) Načtěte fotku s ColorChecker tabulkou\n"
            "2) Klikněte na 4 rohy v tomto pořadí: levý horní, pravý horní, pravý dolní, levý dolní\n"
            "3) Dejte spočítet korekci a použijte ji v projektu"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        row = QHBoxLayout()
        self.btn_load = QPushButton("Načíst kalibrační fotografii…")
        self.btn_load.clicked.connect(self._on_load_image)
        row.addWidget(self.btn_load)

        self.btn_compute = QPushButton("Spočítat korekci")
        self.btn_compute.setEnabled(False)
        self.btn_compute.clicked.connect(self._on_compute)
        row.addWidget(self.btn_compute)

        layout.addLayout(row)

        self.viewer = _ClickImageLabel()
        self.viewer.setMinimumHeight(360)
        layout.addWidget(self.viewer)

        self.points_label = QLabel("Body: ")
        layout.addWidget(self.points_label)

        self.error_label = QLabel("RMS chyba: ")
        layout.addWidget(self.error_label)

        row2 = QHBoxLayout()
        self.btn_apply = QPushButton("Použít")
        self.btn_apply.setEnabled(False)
        self.btn_apply.clicked.connect(self.accept)
        row2.addWidget(self.btn_apply)

        self.btn_cancel = QPushButton("Zrušit")
        self.btn_cancel.clicked.connect(self.reject)
        row2.addWidget(self.btn_cancel)
        layout.addLayout(row2)

        #timer na refresh label bodov
        self.startTimer(200)

    def timerEvent(self, event) -> None:
        pts = self.viewer.points
        self.points_label.setText(f"Body ({len(pts)}/4): {pts}")
        self.btn_compute.setEnabled(self._image_rgb is not None and len(pts) >= 4)

    def get_result(self) -> ColorCheckerResult | None:
        return self._result

    def _on_load_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Vyberte kalibrační fotografii",
            "",
            "Obrázky (*.png *.jpg *.jpeg *.tif *.tiff);;Všechny soubory (*.*)",
        )
        if not path:
            return

        try:
            arr = load_image(path)

            if arr.ndim == 2:
                arr = np.stack([arr, arr, arr], axis=-1)
            if arr.shape[2] == 4:
                arr = arr[..., :3]

            if arr.dtype != np.uint8:
                #downcast na uint8 pre výpočet
                if arr.dtype == np.uint16:
                    arr = (arr / 256).astype(np.uint8)
                else:
                    arr = np.clip(arr, 0, 255).astype(np.uint8)

            self._image_path = path
            self._image_rgb = arr

            arr = np.ascontiguousarray(arr)
            qimg = QImage(arr.data, arr.shape[1], arr.shape[0], arr.shape[1] * 3, QImage.Format_RGB888).copy()
            self.viewer.set_image(qimg)

            self._result = None
            self.error_label.setText("RMS chyba: -")
            self.btn_apply.setEnabled(False)

        except Exception as e:
            QMessageBox.critical(self, "Chyba", str(e))

    def _on_compute(self) -> None:
        if self._image_rgb is None:
            return
        pts = self.viewer.points
        if len(pts) < 4:
            return

        corners = pts[:4]  #LH, PH, PD, LD
        try:
            measured = self._measure_colorchecker_patches(self._image_rgb, corners)
            ref = COLORCHECKER_SRGB_24
            M = estimate_correction_matrix_affine(measured, ref)
            err = rms_rgb(measured @ M[:, :3].T + M[:, 3], ref)

            self._result = ColorCheckerResult(matrix=M, rms_error=err)
            self.error_label.setText(f"RMS chyba: {err:.2f}")
            self.btn_apply.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "Chyba výpočtu", str(e))

    def _measure_colorchecker_patches(self, image_rgb: np.ndarray, corners: list[tuple[int, int]]) -> np.ndarray:
        """
        Z rohov spraví warp na normovaný grid 6x4 a zmeria 24 patchov
        vráti measured_colors (24,3) float32 v 0..255
        """
        #cieľová veľkosť "narovnanej" tabuľky
        out_w = 600
        out_h = 400

        src = np.array(corners, dtype=np.float32)  #LH, PH, PD, LD
        dst = np.array([(0, 0), (out_w - 1, 0), (out_w - 1, out_h - 1), (0, out_h - 1)], dtype=np.float32)

        H = cv2.getPerspectiveTransform(src, dst)
        warped = cv2.warpPerspective(image_rgb, H, (out_w, out_h), flags=cv2.INTER_LINEAR)

        #6x4 grid
        cols = 6
        rows = 4
        cell_w = out_w / cols
        cell_h = out_h / rows

        measured = []
        for r in range(rows):
            for c in range(cols):
                #berieme strednú časť patchu, aby sme ignorovali okraje
                x0 = int((c + 0.2) * cell_w)
                x1 = int((c + 0.8) * cell_w)
                y0 = int((r + 0.2) * cell_h)
                y1 = int((r + 0.8) * cell_h)

                patch = warped[y0:y1, x0:x1, :]
                if patch.size == 0:
                    measured.append([0, 0, 0])
                    continue

                #medián kvôli šumu
                pix = patch.reshape(-1, 3).astype(np.float32)
                med = np.median(pix, axis=0)
                measured.append(med.tolist())

        return np.array(measured, dtype=np.float32)