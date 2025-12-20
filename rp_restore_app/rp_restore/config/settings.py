from __future__ import annotations

from dataclasses import dataclass, field
from typing import List
from pathlib import Path
import json

@dataclass
class AppSettings:
    """
    nastavenia
    zatiaľ len:
      - recent_projects: posledné otvorené projekty (zoznam ciest)
    """

    #ukladanie nastavení (aj pre nedávno otvorené projekty)
    SETTINGS_DIR: Path = Path.home() / ".rp_restore"
    SETTINGS_FILE: Path = SETTINGS_DIR / "settings.json"

    recent_projects: List[str] = field(default_factory=list)

    def add_recent_project(self, path: str) -> None:
        """pridá cestu medzi naposledy otvorené"""
        if path in self.recent_projects:
            self.recent_projects.remove(path)
        self.recent_projects.insert(0, path)
        #limit na 10 položiek
        self.recent_projects = self.recent_projects[:10]

        self.save()

    def get_recent_projects(self) -> List[str]:
        """vráti kópiu zoznamu recent projektov"""
        return list(self.recent_projects)
    
    def save(self) -> None:
        """Uloží nastavenia do JSON súboru"""
        try:
            self.SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "recent_projects": self.recent_projects,
            }
            self.SETTINGS_FILE.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            #pri problémoch ignorujeme
            pass

    @classmethod
    def load_default(cls) -> "AppSettings":
        """
        načítanie default nastavení
        neskôr pridáme čítanie zo súboru, teraz len vráti prázdne nastavenia
        """
        try:
            settings_file = cls.SETTINGS_FILE
            if settings_file.is_file():
                raw = settings_file.read_text(encoding="utf-8")
                data = json.loads(raw)
                return cls(recent_projects=data.get("recent_projects", []))
        except Exception:
            #ak sa niečo pokazí, použijeme default
            pass
        return cls()
