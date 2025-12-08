import sys

from PySide6.QtWidgets import QApplication
from rp_restore.gui.main_window import MainWindow
from rp_restore.config.settings import AppSettings


def main() -> None:
    app = QApplication(sys.argv)

    app_settings = AppSettings.load_default()

    window = MainWindow(app_settings=app_settings)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
