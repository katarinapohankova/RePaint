from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple


class WarningType(str, Enum):

    EDGE_MODIFIED_TOUCHING_FILLS = "edge_modified_touching_fills"
    EDGE_DELETED_REGIONS_MERGED = "edge_deleted_regions_merged"

    #neskôr budú ďalšie


@dataclass
class RegionReference:
    """
    Odkaz na konkrétnu oblasť obrazu, ktorej sa warning týka
    layer_id -na ktorej vrstve
    bbox -(x, y, w, h) – oblasť, ktorú by sme mali zvýrazniť
    region_id -id oblasti z RegionMap (potom)
    seed_point -bod, z ktorého bola oblasť vyplnená 
    """

    layer_id: str
    bbox: Tuple[int, int, int, int]
    region_id: Optional[int] = None
    seed_point: Optional[Tuple[int, int]] = None


@dataclass
class UserWarning:
    """
    jeden warning, ktorý sa zobrazí v log paneli
    id -interné ID warningu (string alebo číslo pre jednoznačnú identifikáciu)
    """

    id: int
    warning_type: WarningType
    message: str    #krátka správa pre užívateľa
    details: str = ""   #detailný popis

    affected_regions: List[RegionReference] = field(default_factory=list)

    #stav warningu
    active: bool = True
    dismissed: bool = False
    downgraded_to_info: bool = False

    def mark_dismissed(self) -> None:
        self.active = False
        self.dismissed = True

    def downgrade_to_info(self) -> None:
        #keď užívateľ upraví oblasť (na ktorej vznikol warning), warning už nemusí byť červený, ale ho ponecháme ako info
        self.downgraded_to_info = True


class LogManager:
    """
    Správa warningov pre jeden Project
    ukladá UserWarning-y, umožňuje ich pridávať, získať aktívne, dismiss alebo downgrade
    """

    def __init__(self) -> None:
        self._warnings: List[UserWarning] = []
        self._next_id: int = 1

    #tvorba warningov

    def add_warning(
        self,
        warning_type: WarningType,
        message: str,
        details: str = "",
        affected_regions: Optional[List[RegionReference]] = None,
    ) -> UserWarning:
        """
        vytvorí nový warning, priradí mu ID a uloží ho do zoznamu
        """
        if affected_regions is None:
            affected_regions = []

        warning = UserWarning(
            id=self._next_id,
            warning_type=warning_type,
            message=message,
            details=details,
            affected_regions=affected_regions,
        )
        self._warnings.append(warning)
        self._next_id += 1
        return warning

    #prístup k warningom

    def get_all_warnings(self) -> List[UserWarning]:
        """vráti všetky warningy (aktívne aj neaktívne)"""
        return list(self._warnings)

    def get_active_warnings(self) -> List[UserWarning]:
        """
        Vráti warningy, ktoré sú "aktívne" (teda ešte neboli dismissnuté)
        """
        return [w for w in self._warnings if w.active and not w.dismissed]

    def find_by_id(self, warning_id: int) -> Optional[UserWarning]:
        """nájde warning podľa ID"""
        for w in self._warnings:
            if w.id == warning_id:
                return w
        return None

    #zmena stavu

    def dismiss_warning(self, warning_id: int) -> None:
        """označí warning ako dismissnutý (užívateľ ho zakrížikoval)"""
        w = self.find_by_id(warning_id)
        if w is not None:
            w.mark_dismissed()

    def downgrade_warning_to_info(self, warning_id: int) -> None:
        """
        downgrad warningu na info 
        """
        w = self.find_by_id(warning_id)
        if w is not None:
            w.downgrade_to_info()
