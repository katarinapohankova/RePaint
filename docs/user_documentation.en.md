# RePaint – User Documentation

**Language / Jazyk:** [English](user_documentation.en.md) | [Čeština](user_documentation.cs.md) | [Slovenčina](user_documentation.md)

## Contents

* [Installation and launch](#installation-and-launch)
* [1. Creating a new project](#1-creating-a-new-project)
* [2. Aligning the damage mask](#2-aligning-the-damage-mask)
* [3. Opening an existing project](#3-opening-an-existing-project)
* [4. Workspace](#4-workspace)
* [5. Navigating the image](#5-navigating-the-image)
* [6. Layers](#6-layers)
  * [Historical copy](#historical-copy)
* [7. Damage mask and highlighting damaged areas](#7-damage-mask-and-highlighting-damaged-areas)
* [8. Color palette](#8-color-palette)
* [9. Materials and brush settings](#9-materials-and-brush-settings)
* [10. Textures](#10-textures)
* [11. Tools](#11-tools)

  * [Štětec (Brush)](#štětec-brush)
  * [Guma (Eraser)](#guma-eraser)
  * [Rozmazání (Smudge)](#rozmazání-smudge)
  * [Výplň (Fill)](#výplň-fill)
  * [Vybrat (Select)](#vybrat-select)
  * [Laso (Lasso)](#laso-lasso)
  * [Hrana (Edge)](#hrana-edge)
  * [Zjemnit hranu (Soften edge)](#zjemnit-hranu-soften-edge)
  * [Pipeta (Eyedropper)](#pipeta-eyedropper)
  * [Auto-výplň malých oblastí (Auto-fill small areas)](#auto-výplň-malých-oblastí-auto-fill-small-areas)
* [12. External algorithms](#12-external-algorithms)

  * [Realistické doplnění (Realistic inpainting)](#realistické-doplnění-realistic-inpainting)
  * [Texturové doplnění (Texture inpainting)](#texturové-doplnění-texture-inpainting)
* [13. ColorChecker correction](#13-colorchecker-correction)
* [14. Undo and Redo](#14-undo-and-redo)
* [15. Saving a project](#15-saving-a-project)
  * [Creating a new proposal from an existing project](#creating-a-new-proposal-from-an-existing-project)
* [16. Exporting the resulting image](#16-exporting-the-resulting-image)
* [17. Exporting a PDF report](#17-exporting-a-pdf-report)
* [18. Keyboard shortcuts](#18-keyboard-shortcuts)
* [19. Recommended workflow](#19-recommended-workflow)
* [20. Troubleshooting](#20-troubleshooting)

## Installation and launch

There are two ways to use the application.

### Installation with the installer

The following file is intended for regular users:

```text
RePaint-Setup-1.1.0.exe
```

The installer is intended for 64-bit Windows. Run it and follow the installation wizard. The application will be installed in your user directory and added to the Start menu. You can optionally create a desktop shortcut.

The installed version already includes Python, the required libraries, and the local texture inpainting algorithm. No additional software needs to be installed.

When you first use realistic inpainting, the application asks for the remote service's endpoint URL and API key. These credentials are stored in the operating system's credential store. You can change them later via **Nastavení → Remote realistické doplnění...** (Settings → Remote realistic inpainting...).

### Running from source code

Python 3.13 and Git are required to run the application from source.

```powershell
git clone https://github.com/katarinapohankova/RePaint.git
cd RePaint\rp_restore_app

python3 -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python app.py
```

After activating the virtual environment, the `python` command refers to the interpreter inside that environment. Installing from source may require access permissions for external package repositories listed in `requirements.txt`.
The realistic inpainting client is installed from a private GitHub repository, so you need the appropriate access permissions. Regular users are advised to use the provided Windows installer.

## 1. Creating a new project

You can create a project from the start screen using **Nový projekt** (New project), or via **Soubor → Nový projekt z obrázku...** (File → New project from image...).

First, select the original image. Common image formats are supported, including PNG, JPG, JPEG, TIFF, and TIF.

After selecting the image, you can also choose a damage mask. The mask defines which areas are damaged and where reconstruction tools can be applied. If you do not want to use a mask, you can close the mask selection dialog and continue without one.

If you select a mask, the application opens a dialog to align it with the original image.

## 2. Aligning the damage mask

When aligning the mask, you select corresponding points on the original image and on the mask. The aim is to determine how the mask should be transformed so it matches the image accurately.

Procedure:

1. Click a point on the original image.
2. Click the corresponding point on the mask.
3. A magnified view of both locations appears in the next dialog.
4. Adjust the positions of the points on the image and mask as precisely as possible.
5. Confirm the point pair.
6. Repeat the procedure to add more points.

At least four pairs of points are required. You can select additional points, up to a set limit. The more accurately the points are placed and the more evenly they are distributed across the image, the more reliably the alignment can be calculated. Using more correctly matched points may improve alignment accuracy.

The dialog also allows you to remove the last point or all points and start over.

## 3. Opening an existing project

You can open an existing project via **Soubor → Otevřít projekt...** (File → Open project...) or by clicking **Otevřít projekt** (Open project) on the start screen.

Projects are stored as `.zip` files. Each file contains the layers, masks, color palette, textures, and other settings needed to continue working.

The start screen also displays a list of recently opened projects. You can open a project from this list by double-clicking it.

## 4. Workspace

When a project opens, the main workspace is displayed. The image being edited is in the center, surrounded by panels and a toolbar.

The main parts of the workspace are:

* the toolbar on the left,
* the **Vrstvy** (Layers) panel
* the **Paleta** (Palette) panel
* the **Externí algoritmy** (External algorithms) panel
* the **Hrany** (Edges) panel
* the **Materiály** (Materials) panel
* the application menu at the top
* the status bar at the bottom of the window

Panels can be shown or hidden via **Zobrazení** (View). If you close a panel, you can reopen it from this menu.

## 5. Navigating the image

You can zoom in, zoom out, and pan the image.

Basic controls:

* use the mouse wheel to zoom in or out
* use the right or middle mouse button to pan the image
* use the left mouse button to draw and operate tools

When you open a project, the image is automatically fitted to the window. You can zoom in up to 100 times.

## 6. Layers

The application works with several layer types:

* **Původní obraz** (Original image) – the original loaded image; it cannot be edited
* **Historická kopie** (Historical copy) – an optional reference layer for comparing the current painting with its historical appearance
* **Malba** (Paint) – working layers used to reconstruct damaged areas
* **Hrany** (Edges) – a layer containing boundaries that divide damaged areas into separate regions

Most editing is done on **Malba** (Paint) layers. You can use them to paint, fill regions, apply textures, smudge, and insert algorithm results.

In the **Vrstvy** (Layers) panel, you can:

* select the active layer
* show or hide a layer using the icon on the left
* create a new paint layer
* rename a layer
* remove a paint layer
* change the opacity of the active layer
* display a preview of the active layer

Only paint layers can be removed.
The historical copy layer appears in the panel only after you load a reference image. It cannot be painted on, but its visibility and opacity can be adjusted independently.

### Layer preview

The **Vrstvy** (Layers) panel includes a preview of the active layer. This helps you inspect its contents without hiding other layers.

Clicking the layer preview displays an enlarged preview on the main canvas. Clicking the smaller preview again hides it and returns to the normal image view.

### Historical copy

The application allows you to use a historical copy of a painting as a reference when planning a reconstruction. The copy is loaded into an existing project and aligned with the original image.

#### Loading and alignment

1. Open a project containing the original image.
2. Select **Soubor → Načíst historickou kopii...** (File → Load historical copy...).
3. Choose the historical copy image.
4. In the alignment dialog, mark corresponding points on the original image and the historical copy.
5. You can refine each pair of points in magnified views.
6. Confirm the alignment after selecting at least four pairs of points.

The application calculates a homography and aligns the historical copy with the coordinate system of the original image. You can use up to 20 pairs of points to improve alignment.

After alignment, a **Historická kopie** (Historical copy) layer appears in the **Vrstvy** (Layers) panel. If the project already contains a historical copy, you can replace it with another image.

#### Displaying the historical copy

The display depends on whether the **Původní obraz** (Original image) and **Historická kopie** (Historical copy) layers are visible:

* **Original image only:** the original image is shown across the entire canvas.
* **Both layers:** the original image is shown in undamaged areas, while the historical copy is shown in damaged areas.
* **Historical copy only:** the historical copy is shown across the entire canvas.
* **Both layers hidden:** no background image is shown.

The regions in which the historical copy is used are determined by the original damage mask, not by the remaining unfilled areas.

The historical copy layer supports transparency. Its opacity can be adjusted with a slider, just like other layers. When its opacity is reduced, the original image does not appear underneath it in damaged areas.

The damage mask overlay and other layers are displayed independently of the historical copy's visibility.

The historical copy serves only as a reference. It is not included in the exported resulting image.

## 7. Damage mask and highlighting damaged areas

The damage mask identifies which pixels are considered damaged. Most tools are restricted to these areas.
When preparing a mask, a black-and-white image is recommended: white pixels represent damaged areas and black pixels represent undamaged areas.

After loading, the mask is converted to a binary representation
used internally by the application.

You can highlight damaged areas via **Zobrazení → Zobrazit poškozené oblasti** (View → Show damaged areas). The same menu also contains a slider for adjusting the highlight opacity.

The highlighting reflects the currently visible layers. If a paint layer is hidden, its contents are not counted as filled when displaying the remaining damage.

## 8. Color palette

The **Paleta** (Palette) panel is used to select the current color and store frequently used colors.

In the panel, you can:

* change the current color
* add the current color to the palette
* select a color from the palette
* remove a color from the palette

Adding a color that is already in the palette does not create a duplicate.

The current color is used for painting, filling, and texture color settings.

## 9. Materials and brush settings

The **Materiály** (Materials) panel contains settings for the brush, eraser, smudging, and textures.

For the brush, eraser, and smudging tools, you can configure:

* brush size
* hardness
* opacity
* density
* whether a stroke can build up opacity
* smudge strength
* smudge source

**Tvrdost** (Hardness) affects the edge of a brush mark. Lower values produce softer edges, while higher values produce sharper edges.

**Krytí** (Opacity) specifies the maximum opacity of a brush mark.

**Hustota** (Density) controls how quickly paint or erasing is applied during a stroke.

**Vrstvit v tahu** (Build up within a stroke) determines whether repeated application during a single mouse drag can gradually increase the mark's opacity, up to the selected opacity limit.

## 10. Textures

In the **Materiály** (Materials) panel, you can switch from **Štětec** (Brush) to **Textura** (Texture). In texture mode, the selected texture is used instead of a solid color.

Texture settings include:

* selected texture
* texture density
* texture strength
* rotation
* texture style
* width and height deformation

Two texture styles are available:

* **Transparentní** (Transparent) – texture brightness controls the transparency of a pattern tinted with the current color
* **Barevná** (Colored) – texture brightness creates lighter and darker shades of the current color

Textures created by the external texture algorithm retain their generated colors. The **Transparentní/Barevná** (Transparent/Colored) style setting is not used for these textures; their colors are adjusted separately using **Upravit barvy…** (Edit colors...).

In **Deformace textury** (Texture deformation), you can change the texture's width and height. The deformation is reflected in the preview and the next time the texture is used.

If you want to reuse the currently deformed texture, click **Přidat mezi textury** (Add to textures). The application creates a new texture derived from the original and adds it to the list. If an identical deformed version already exists, it is not added again.

You can also add your own texture from an image file to the project.

## 11. Tools

Tools are selected from the toolbar on the left. The active tool is highlighted.

### Štětec (Brush)

The **Štětec** (Brush) tool is used to manually reconstruct damaged areas using a color or texture. It uses the current color from the palette and settings from the **Materiály** (Materials) panel.

Draw by dragging with the left mouse button.

The brush can only be used on a paint layer. If another layer is active, the application attempts to switch to a suitable paint layer automatically.

---

### Guma (Eraser)

The **Guma** (Eraser) tool removes content from a paint layer. It erases only content added to the working layer, not the original image.

The eraser uses the size, hardness, opacity, and density settings from the **Materiály** (Materials) panel.

---

### Rozmazání (Smudge)

The **Rozmazání** (Smudge) tool is used to gently smudge reconstructed areas. It operates within damaged regions and uses settings from the **Materiály** (Materials) panel.

You can choose the smudge source:

* **Vrstva malby** (Paint layer) – only content from the active paint layer is used
* **Původní obraz + vrstva malby** (Original image + paint layer) – the original image underneath the paint layer is also considered

This tool is useful for softening manually reconstructed areas or overly sharp transitions.

---

### Výplň (Fill)

The **Výplň** (Fill) tool fills a damaged region with the current color or texture.

If no area is selected, click inside a damaged region. The application fills the entire region defined by the damage mask and any drawn boundaries.

If a selection is active, the fill is applied to the selected areas.

The fill is applied only where the active paint layer has not yet been filled.

---

### Vybrat (Select)

The **Vybrat** (Select) tool is used to select damaged regions.

Click to select one region. Hold **Ctrl** while clicking to add more regions to the selection or remove them from it.

Selected areas are shown with a gray highlight.

Selections can be used before running the texture algorithm or filling several regions at once.

---

### Laso (Lasso)

The **Laso** (Lasso) tool selects multiple damaged regions by drawing a freehand outline. While you drag the mouse, the lasso outline is shown. When you release the button, the application selects damaged regions inside the drawn shape.

Hold **Ctrl** while using the lasso to add the new selection to the existing one.

The lasso is useful for quickly selecting several nearby damaged areas.

---

### Hrana (Edge)

The **Hrana** (Edge) tool draws boundaries in damaged areas. These boundaries divide the damaged region into smaller regions that can then be filled separately.

Draw boundaries only where the damaged area needs to be divided. This tool is not intended as a general-purpose painting brush.

Edge controls:

* the left mouse button draws an edge
* the right mouse button or **Shift + left mouse button** erases an edge

The edge color and blending width can be set in the **Hrany** (Edges) panel.

---

### Zjemnit hranu (Soften edge)

The **Zjemnit hranu** (Soften edge) tool softens the transition between two regions separated by a drawn edge. Use it when an edge has divided a damaged area into two filled regions and the transition between them is too sharp.

Drag across an existing edge with the left mouse button. The application removes the affected part of the edge and creates a smoother transition between the reconstructed regions.

The tool works only where a drawn edge exists. If there is nothing to soften, the application displays a warning.

Set the blending width in the **Hrany** (Edges) panel using **Zjemnění (px)** (Softening width in pixels).

---

### Pipeta (Eyedropper)

The **Pipeta** (Eyedropper) tool samples a color from the image. Clicking a point sets the sampled color as the current color in the palette.

It is useful when manually filling damaged areas and matching surrounding colors.

---

### Auto-výplň malých oblastí (Auto-fill small areas)

The **Auto-výplň malých oblastí** (Auto-fill small areas) tool automatically fills small damaged regions based on a configurable maximum area in pixels.

Next to the tool is a slider and a numeric value for setting the maximum area. When this value changes, the application highlights eligible areas in turquoise.

Click a highlighted region to exclude it from automatic filling or include it again.

Click **Auto-výplň malých oblastí** (Auto-fill small areas) to fill the selected small regions using a color calculated from their surroundings.

If a manual selection of regions is active, auto-fill is applied to that selection.

Press this button only when you are ready to fill the selected areas; it does not behave as a continuously active drawing tool.

---

## 12. External algorithms

The **Externí algoritmy** (External algorithms) panel contains tools for automatically reconstructing damaged areas using external algorithms.

* **Realistické doplnění** (Realistic inpainting)
* **Texturové doplnění** (Texture inpainting)

### Realistické doplnění (Realistic inpainting)

Realistic inpainting automatically reconstructs damaged areas within a selected rectangular window. The algorithm runs on a remote service, so an internet connection and a valid API key are required.

When used for the first time, the application asks for access credentials. You can change them later via **Nastavení → Remote realistické doplnění...** (Settings → Remote realistic inpainting...).

After clicking **Realistické doplnění** (Realistic inpainting), a dialog opens with two options for choosing the window:

* use the bounding rectangle of the current selection
* select a window manually on the image

The maximum window size is 1440 × 1440 pixels. The window must include at least part of the remaining damage mask.

Two modes are available:

* **Základní** (Basic) – for ordinary realistic inpainting of damaged areas; allows adjustment of the amount of regeneration
* **Vedené podle náčrtu** (Sketch-guided) – allows you to guide inpainting with manually drawn lines. These should be dark and thin, ideally about one pixel wide. This mode is considerably slower.

In either mode, you can independently choose the source image used by the algorithm:

* **Původní obraz** (Original image) – uses the original image.
* **Historická kopie** (Historical copy) – uses the historical copy across the entire input window.
* **Původní obraz + kopie v poškozených místech** (Original image + copy in damaged areas) – uses the original image outside the damaged areas and the historical copy within them.

The last two options are available only if a historical copy has been loaded into the project.

If the historical copy contains transparent areas, the algorithm automatically substitutes the corresponding pixels from the original image. Where the historical copy is partially transparent, the two images are blended smoothly.

The source image is chosen independently of the layer visibility on the canvas and the historical copy's opacity setting.

The **Použít viditelné vrstvy malby a hran** (Use visible paint and edge layers) option allows existing visible working layers to be included in the input image. It is disabled by default in Basic mode and enabled by default in Sketch-guided mode. You can change this setting.

In Basic mode, you can set **Míra dogenerování** (Amount of regeneration). Lower values preserve more of the underlying image structure, while a value of 1 means full regeneration. If there are no useful original pixels under the mask, a value of 1 is recommended.

The optional **seed** setting lets you repeat the computation with the same random seed.

If regions are selected, the result is applied only within that selection. Otherwise, the remaining damage mask within the selected window is used. The result is inserted into the active paint layer only at pixels not yet filled on that layer.

The realistic inpainting model is primarily intended for restoring works by Albrecht Dürer.

### Texturové doplnění (Texture inpainting)

Texture inpainting uses a local algorithm to generate textured content. The dialog offers two output modes:

* **Doplnit vybranou oblast obrazu** (Fill selected image area) – inserts the result directly into selected damaged regions
* **Vygenerovat samostatnou texturu a přidat ji do materiálů** (Generate a separate texture and add it to materials) – creates a standalone texture image and adds it to the current project's textures

To fill part of the image directly, first select a damaged area with **Vybrat** (Select) or **Laso** (Lasso). Even without an active selection, you can generate a separate texture and add it to the Materials panel.

The dialog provides settings for:

* texture model
* one to three colors
* strength of each color layer
* scale along the X and Y axes
* density along the X and Y axes for models that support it
* rotation
* overall scale
* opaque or transparent background
* brightness of an opaque background
* seed
* width and height of a separately generated texture

Each model has an input preview. Click **Vygenerovat náhled** (Generate preview) to create a reduced-size preview of the resulting texture with the current parameters.

When filling a selected area, the result is inserted into the active paint layer only where the current selection is still damaged and has not yet been filled on that layer.

A separately generated texture is added to the Materials panel and retains its generated colors. It can be used with the texture brush or the fill tool. Selecting it displays its original colors and their strengths; use **Upravit barvy…** (Edit colors...) to change the colors and regenerate the texture.

## 13. ColorChecker correction

The application supports color correction using a ColorChecker chart. Open the dialog via **Úpravy → ColorChecker...** (Edit → ColorChecker...).

Procedure:

1. Load a calibration photograph containing a ColorChecker chart.
2. Click the chart's four corners in the order specified in the dialog.
3. Click **Spočítat korekci** (Calculate correction).
4. Once the correction has been calculated, apply it using **Použít** (Apply).

After calculating the correction, you can toggle its display via **Zobrazení → Použít ColorChecker korekci** (View → Apply ColorChecker correction).

The calibration photograph should be taken under the same lighting conditions as the working photograph of the painting. Ideally, it should be captured during the initial documentation of the artwork.

It is recommended to decide whether to use ColorChecker correction at the beginning of the project. Enabling it after manual reconstruction may change the appearance of the colors you have already added.

## 14. Undo and Redo

The application supports undoing and redoing edits.

* **Úpravy → Zpět** (Edit → Undo) or **Ctrl+Z** undoes the last edit
* **Úpravy → Znovu** (Edit → Redo) or **Ctrl+Y** / **Ctrl+Shift+Z** restores an undone edit

Undo and Redo work across all layers. When undoing an edit performed on a different layer, the application activates the corresponding layer.

## 15. Saving a project

Save a project via **Soubor → Uložit projekt** (File → Save project) or **Ctrl+S**.

If the project does not yet have a file path, the **Uložit projekt jako...** (Save project as...) dialog opens. The project is saved as a `.zip` file.

Menu options:

* **Uložit projekt** (Save project) – saves to the current path
* **Uložit projekt jako...** (Save project as...) – saves the project to a new `.zip` file
* **Zavřít projekt** (Close project) – closes the current project
* **Ukončit** (Exit) – exits the application

If the project contains unsaved changes, the application asks whether to save them when the project is closed.

### Creating a new proposal from an existing project

You can create an independent reconstruction proposal from the current project without loading and aligning the input images again.

Select **Soubor → Vytvořit nový návrh z aktuálního projektu...** (File → Create new proposal from current project...).

The application offers two options:

* **Ponechat malbu a hrany** (Keep paint and edges) – creates a complete project copy, including the existing working layers.
* **Začít s čistou malbou** (Start with empty paint layers) – keeps the original image, damage mask, historical copy, palette, and textures, but creates empty paint and edge layers. All originally damaged areas are treated as unfilled again.

Next, choose a name and location for the new project.

If the original project contains unsaved changes, the application offers **Uložit** (Save), **Neukládat** (Don't save), or **Zrušit** (Cancel).

Choosing **Neukládat** (Don't save) leaves the original project file unchanged, but the new proposal still includes the currently unsaved edits.

After successful creation, the new proposal opens automatically and the application displays its name.

Each proposal is a separate ZIP project. Edits made in a new proposal do not affect the original project.

## 16. Exporting the resulting image

Export the resulting image via **Soubor → Exportovat obraz…** (File → Export image...).

The exported image always contains the original image as a background, with visible paint and edge layers composited on top.

The visibility of the original image on the canvas does not affect the export.
The historical copy is never included in the resulting image, even when it is currently visible on the canvas.

Hidden paint and edge layers are not included in the export.

Supported export formats:

* TIFF
* PNG
* JPEG

## 17. Exporting a PDF report

Export a PDF report via **Soubor → Exportovat report…** (File → Export report...).

Before the report is created, a dialog opens where you can optionally enter:

* restorer's name
* artwork title
* artwork author
* notes

The report contains:

* basic project information
* report creation date
* optional notes
* original image
* damage mask
* current reconstructed result
* remaining damage mask
* statistics on coverage of damaged areas
* individual working layers
* historical copy as a separate reference layer, if one is loaded in the project

The resulting image in the report is composed of the original image and visible working layers. The historical copy is documented separately and is not part of the reconstructed result.

## 18. Keyboard shortcuts

### Project

* **Ctrl+N** – new project from image
* **Ctrl+O** – open project
* **Ctrl+S** – save project
* **Ctrl+Shift+S** – save project as
* **Ctrl+W** – close project
* **Ctrl+Q** – exit the application

### Editing

* **Ctrl+Z** – undo
* **Ctrl+Y** – redo
* **Ctrl+Shift+Z** – redo
* **+** or **=** – increase brush size
* **-** – decrease brush size

### Tools

* **B** – Štětec (Brush)
* **E** – Guma (Eraser)
* **D** – Rozmazání (Smudge)
* **F** – Výplň (Fill)
* **S** – Vybrat (Select)
* **L** – Laso (Lasso)
* **G** – Hrana (Edge)
* **M** – Zjemnit hranu (Soften edge)
* **I** – Pipeta (Eyedropper)

## 19. Recommended workflow

Recommended steps:

1. Create a new project from the original image.
2. Load and align the damage mask.
3. Check that the damage overlay is correctly aligned with the image.  
    Apply ColorChecker correction if needed.
4. If a historical copy is available, load it, align it with the original image, and use it as a reference as needed.
5. Create additional paint layers if necessary.
6. Divide large or logically distinct damaged areas using edges.
7. Fill smaller areas automatically or manually.
8. Fill larger regions with a color, texture, or an external algorithm.
9. Soften sharp transitions with **Rozmazání** (Smudge) or **Zjemnit hranu** (Soften edge).
10. Save the project regularly.
11. Export the resulting image or a PDF report when finished.

Using multiple paint layers is recommended for different reconstruction variants. You can show or hide layers and adjust their opacity, making it easier to compare different proposals.

When comparing several variants, you can also create separate proposals from an existing project. Each can contain a different reconstruction while sharing the same original image, mask, and aligned historical copy.

## 20. Troubleshooting

### A tool does not draw

Check that the active layer is **Malba** (Paint). Most tools cannot draw on the original image, historical copy, or edge layer.

Also make sure you are clicking within an area defined by the damage mask. The tools are restricted to damaged areas.

### Fill does not work

The area may already be filled on the active paint layer. Try selecting another paint layer or creating a new one.

### Damaged areas are not visible

Make sure **Zobrazení → Zobrazit poškozené oblasti** (View → Show damaged areas) is enabled. You can adjust the overlay opacity with the slider in the **Zobrazení** (View) menu.

If a paint layer is hidden, its reconstructed content may appear as damaged again in the overlay because only currently visible layers are considered.

### The application is slower with large images

Large TIFF images or masks may slow down region selection, filling, or external algorithms. Save the project regularly when working with large images.

### The historical copy is not visible

Check that the historical copy has been loaded and its layer is visible in the **Vrstvy** (Layers) panel.

If the original image is also visible, the historical copy appears only in areas marked as damaged in the original damage mask.

To show the historical copy across the entire canvas, hide the **Původní obraz** (Original image) layer.

### The historical copy has empty areas

Empty areas created during alignment or editing may remain transparent. When realistic inpainting is used, the corresponding pixels of the original image are automatically substituted in these areas.

If you also need to preserve transparency in the input historical-copy file, use a format that supports an alpha channel, such as PNG.
