from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class AppSettings:
    """
    nastavenia
    zatiaľ len:
      - recent_projects: posledné otvorené projekty (zoznam ciest)
    """

    recent_projects: List[str] = field(default_factory=list)

    def add_recent_project(self, path: str) -> None:
        """pridá cestu medzi naposledy otvorené"""
        if path in self.recent_projects:
            self.recent_projects.remove(path)
        self.recent_projects.insert(0, path)
        #limit na 10 položiek
        self.recent_projects = self.recent_projects[:10]

    def get_recent_projects(self) -> List[str]:
        """vráti kópiu zoznamu recent projektov"""
        return list(self.recent_projects)

    @classmethod
    def load_default(cls) -> "AppSettings":
        """
        načítanie default nastavení
        neskôr pridáme čítanie zo súboru, teraz len vráti prázdne nastavenia
        """
        return cls()
