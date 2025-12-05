import numpy as np

from rp_restore.core.layers import Layer, LayerMeta, LayerRole
from rp_restore.core.project_model import Project


def main() -> None:
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


if __name__ == "__main__":
    main()
