from rp_restore.core.warnings import (LogManager, WarningType, RegionReference,)


def main() -> None:
    log = LogManager()

    #pridáme prvý warning
    w1 = log.add_warning(
        warning_type=WarningType.EDGE_MODIFIED_TOUCHING_FILLS,
        message="hrany boli upravené a dotýkajú sa vyplnených oblastí",
        details="zasiahnuté sú 2 oblasti na vrstve paint_1",
        affected_regions=[
            RegionReference(layer_id="paint_1", bbox=(10, 10, 50, 30)),
            RegionReference(layer_id="paint_1", bbox=(100, 40, 20, 20)),
        ],
    )

    #pridáme druhý warning
    w2 = log.add_warning(
        warning_type=WarningType.EDGE_DELETED_REGIONS_MERGED,
        message="odstránená hrana zjednotila dve oblasti",
        details="oblasti A a B boli zlúčené",
    )

    print("všetky warningy:")
    for w in log.get_all_warnings():
        print(f"- id={w.id}, type={w.warning_type}, message={w.message!r}")

    print("\naktívne warningy pred dismiss:")
    for w in log.get_active_warnings():
        print(f"- id={w.id}, active={w.active}, dismissed={w.dismissed}")

    #dismiss prvý warning
    log.dismiss_warning(w1.id)

    print("\naktívne warningy po dismiss w1:")
    active_after = log.get_active_warnings()
    for w in active_after:
        print(f"- id={w.id}, active={w.active}, dismissed={w.dismissed}")

    #má tam zostať len w2
    assert len(active_after) == 1, "po dismiss w1 by mal zostať len 1 aktívny warning"
    assert active_after[0].id == w2.id, "aktívny by mal byť len druhý warning"

    print("\ntest logmanager ok")


if __name__ == "__main__":
    main()
