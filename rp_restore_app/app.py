import sys
import ctypes
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from rp_restore.gui.main_window import MainWindow
from rp_restore.config.settings import AppSettings


def main() -> None:
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "KatarinaPohankova.RePaint"
        )

    app = QApplication(sys.argv)
    app.setApplicationName("RePaint")
    app.setApplicationDisplayName("RePaint")

    icon_path = (
        Path(__file__).resolve().parent
        / "rp_restore"
        / "resources"
        / "RePaint_icon.png"
    )
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))

    app_settings = AppSettings.load_default()

    window = MainWindow(app_settings=app_settings)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
