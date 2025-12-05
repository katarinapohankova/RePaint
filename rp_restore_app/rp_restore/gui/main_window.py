from PySide6.QtWidgets import QMainWindow


class MainWindow(QMainWindow):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.setWindowTitle("RP – Reštaurovanie obrazov")

        self.resize(1200, 800)
