import numpy as np

from rp_restore.core.layers import Layer, LayerMeta, LayerRole
from rp_restore.core.project_model import Project
from rp_restore.core.history import UndoAction

def test_composited_image() -> None:
    #rozmery testovacieho obrázka
    width, height = 200, 100

    #Background vrstva (biela)
    bg_image = np.zeros((height, width, 4), dtype=np.uint8)
    bg_image[..., :3] = 255  # R,G,B = 255 (biela)
    bg_image[..., 3] = 255   # A = 255 (plne nepriehľadné)

    bg_meta = LayerMeta(
        id="background",
        name="Background",
        role=LayerRole.BACKGROUND,
    )
    bg_layer = Layer(bg_meta, bg_image)

    #Paint vrstva (červený obdĺžnik uprostred)
    paint_image = np.zeros((height, width, 4), dtype=np.uint8)
    paint_meta = LayerMeta(
        id="paint_1",
        name="Paint 1",
        role=LayerRole.PAINT,
    )

    #červený obdĺžnik
    y0, y1 = 25, 75
    x0, x1 = 50, 150
    paint_image[y0:y1, x0:x1, 0] = 255  # R = 255
    paint_image[y0:y1, x0:x1, 3] = 255  # A = 255 (nepriehľadné)

    paint_layer = Layer(paint_meta, paint_image)

    #project + kompozícia
    project = Project("Test Project")
    project.add_layer(bg_layer)
    project.add_layer(paint_layer)

    composited = project.composited_image()

    #skontrolujeme tvar
    assert composited.shape == (height, width, 3)
    print("composited shape:", composited.shape)

    # skúsime skontrolovať pár pixelov:
    #  - pixel uprostred červeného obdĺžnika by mal byť červený
    center_y = (y0 + y1) // 2
    center_x = (x0 + x1) // 2
    center_pixel = composited[center_y, center_x, :]
    print("center pixel:", center_pixel)

    #  - pixel úplne v ľavom hornom rohu by mal zostať biely
    corner_pixel = composited[0, 0, :]
    print("corner pixel:", corner_pixel)




def test_undo_basic() -> None:
    """
    Otestujeme základné undo/redo:
    - zmeníme malú oblasť v background vrstve na čiernu
    - uložíme UndoAction
    - undo_global() vráti pôvodnú bielu
    - redo_global() znovu vráti čiernu
    """
    width, height = 50, 30

    #Background: biela
    bg_image = np.zeros((height, width, 4), dtype=np.uint8)
    bg_image[..., :3] = 255
    bg_image[..., 3] = 255

    bg_meta = LayerMeta(
        id="background",
        name="Background",
        role=LayerRole.BACKGROUND,
    )
    bg_layer = Layer(bg_meta, bg_image)

    project = Project("Undo Test")
    project.add_layer(bg_layer)

    #BBOX, ktorý budeme meniť
    bbox = (10, 5, 20, 10)  #x, y, w, h

    #before – uložíme si pôvodné pixely
    before = bg_layer.clone_subregion(*bbox)

    #zmena -vyplníme tú oblasť čiernou
    x, y, w, h = bbox
    bg_layer.image[y:y + h, x:x + w, :3] = 0    # RGB = 0,0,0
    bg_layer.image[y:y + h, x:x + w, 3] = 255   # A = 255

    #after – aktuálny stav oblasti
    after = bg_layer.clone_subregion(*bbox)

    #vytvoríme UndoAction a pushneme ho do managera
    action = UndoAction(
        description="Fill black rectangle",
        layer_id=bg_meta.id,
        layer_role=bg_meta.role,
        bbox=bbox,
        before=before,
        after=after,
    )

    project.undo_manager.push_action(action)

    #overíme, že teraz je pixel uprostred bboxu čierny
    center_y = y + h // 2
    center_x = x + w // 2
    center_pixel = bg_layer.image[center_y, center_x, :3]
    print("before undo, center pixel:", center_pixel)
    assert np.array_equal(center_pixel, np.array([0, 0, 0], dtype=np.uint8))

    #--------undo--------
    undo_action = project.undo_global()
    assert undo_action is not None

    #po undo by mal byť ten pixel zasa biely
    center_pixel_after_undo = bg_layer.image[center_y, center_x, :3]
    print("after undo, center pixel:", center_pixel_after_undo)
    assert np.array_equal(center_pixel_after_undo, np.array([255, 255, 255], dtype=np.uint8))

    #--------redo--------
    redo_action = project.redo_global()
    assert redo_action is not None

    center_pixel_after_redo = bg_layer.image[center_y, center_x, :3]
    print("after redo, center pixel:", center_pixel_after_redo)
    assert np.array_equal(center_pixel_after_redo, np.array([0, 0, 0], dtype=np.uint8))


if __name__ == "__main__":
    print("test_composited_image")
    test_composited_image()
    print("\ntest_undo_basic")
    test_undo_basic()
# if __name__ == "__main__":
#     main()
