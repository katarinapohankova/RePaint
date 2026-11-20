# RePaint – Developer Documentation

**Language / Jazyk:** [English](developer_documentation.en.md) | [Čeština](developer_documentation.cs.md) | [Slovenčina](developer_documentation.md)

## Contents

* [1. Basic project structure](#1-basic-project-structure)
* [2. Main libraries used](#2-main-libraries-used)
* [3. Project data model](#3-project-data-model)
* [4. Layers](#4-layers)
* [5. ProjectController](#5-projectcontroller)
* [6. Canvas](#6-canvas)
* [7. Tools](#7-tools)
* [8. Panels](#8-panels)
* [9. Saving and loading projects](#9-saving-and-loading-projects)
* [10. Loading and saving images](#10-loading-and-saving-images)
* [11. Damage mask and regions](#11-damage-mask-and-regions)
* [12. Undo/Redo](#12-undoredo)
* [13. Texture brush](#13-texture-brush)
* [14. Auto-fill](#14-auto-fill)
* [15. Edges and edge blending](#15-edges-and-edge-blending)
* [16. Smudging](#16-smudging)
* [17. External algorithms](#17-external-algorithms)
* [18. ColorChecker correction](#18-colorchecker-correction)
* [19. Mask and historical copy alignment](#19-mask-and-historical-copy-alignment)
* [20. PDF report](#20-pdf-report)
* [21. Application settings](#21-application-settings)
* [22. Typical code workflow](#22-typical-code-workflow)
* [23. Summary](#23-summary)


The application is written in Python and uses PySide6 for its graphical user interface. NumPy, Pillow, and OpenCV are the main libraries used to process image data.

## 1. Basic project structure

The main application package is located in the `rp_restore` directory.

Simplified structure:

```text
rp_restore_app/rp_restore/
├── config/
│   └── settings.py
├── core/
│   ├── algorithm_runner.py
│   ├── auto_fill.py
│   ├── color_correction.py
│   ├── edge_blend.py
│   ├── history.py
│   ├── layers.py
│   ├── mask_alignment.py
│   ├── project_model.py
│   ├── regions.py
│   ├── remote_restoration_config.py
│   ├── selection.py
│   └── texture_brush.py
├── gui/
│   ├── main_window.py
│   ├── project_controller.py
│   ├── mask_alignment_dialog.py
│   ├── colorchecker_dialog.py
│   ├── realistic_fill_dialog.py
│   ├── remote_restoration_settings_dialog.py
│   ├── texture_fill_dialog.py
│   ├── start_screen_widget.py
│   ├── canvas/
│   ├── panels/
│   └── tools/
├── io/
│   ├── image_io.py
│   └── project_storage.py
├── report/
│   ├── pdf_report.py
│   └── report_dialog.py
└── resources/
```

The code is divided into several parts:

* `core` contains the data model and computational logic
* `gui` contains the graphical interface and application controls
* `gui/tools` contains individual tools
* `gui/panels` contains the side panels
* `io` handles loading and saving images and projects
* `report` handles PDF report generation
* `config` contains application settings
* `resources` contains default textures, model previews, and graphical assets

## 2. Main libraries used

The application primarily uses the following external libraries and packages:

* `PySide6` – graphical user interface
* `numpy` – representation and manipulation of image data
* `Pillow` – loading, converting, and saving images
* `opencv-python` / `cv2` – selected image-processing operations
* `reportlab` – generating PDF reports
* `keyring` – storing the remote service endpoint and API key in the operating system's credential store
* `painting_inpaint.remote` – client for remote realistic inpainting
* `texture_infill` – locally executed texture inpainting algorithm

The texture algorithm is used as an installed Python package. Its source code is not stored in the application's source directory. The model files are included in the `texture_infill` package.

## 3. Project data model

The main data model class is `Project`, located in:

```
rp_restore/core/project_model.py
```

The `Project` class represents a single open project. It contains:

* project name
* path to the original image
* original working image
* list of layers
* original damage mask
* masks indicating filled damage
* historical copy of the image
* color palette
* brush settings
* textures
* ColorChecker correction settings
* Undo/Redo manager

Important methods of the `Project` class:

* `add_layer()` – adds a layer
* `remove_layer()` – removes a Paint layer
* `get_background_layer()` – returns the original image layer
* `get_paint_layers()` – returns all Paint layers
* `get_edge_layer()` – returns the edge layer
* `composited_image()` – composites the resulting image
* `composited_region()` – composites a portion of the image
* `set_damage_masks()` – sets damage masks
* `get_damage_remaining_mask()` – returns the remaining damage mask
* `get_selection_from_click()` – selects a region by clicking
* `get_selections_from_polygon()` – selects regions using a lasso polygon
* `sync_layer_filled_mask_from_alpha()` – synchronizes a layer's filled mask with its alpha channel
* `get_reference_layer()` – returns the historical copy layer
* `composited_view_image()` – creates an RGBA image for the main canvas
* `composited_view_region()` – creates an RGBA canvas region
* `realistic_input_region()` – prepares the RGB input for realistic inpainting using the selected source
* `get_export_image()` – creates the final image with the original background forced on

Image composition is separated according to its purpose. The `composited_view_image()` and `composited_view_region()` methods prepare an RGBA image for display on the canvas.

The existing `composited_image()` and `composited_region()` methods produce an RGB composition of the original background and the working layers. They do not include the historical copy.

The `get_export_image()` method calls `composited_image()` with `force_original_background=True`, ensuring that the original background is exported regardless of whether it is visible on the canvas.

## 4. Layers

Layers are defined in:

```
rp_restore/core/layers.py
```

Four layer types are used:

```python
class LayerRole(str, Enum):
    BACKGROUND = "background"
    REFERENCE = "reference"
    EDGE = "edge"
    PAINT = "paint"
```

Each layer is represented by a `Layer` object containing:

* `meta` – layer metadata
* `image` – image data in RGBA format
* `damage_filled_mask` – information about damaged pixels filled on this layer

Layer metadata is stored in the `LayerMeta` class. It includes, for example:

* internal layer ID
* layer name
* layer type
* visibility
* opacity
* layer order

Layers use image data stored in a NumPy array with the shape:

```
(height, width, 4)
```

The data type is `uint8`, and the channels are ordered RGBA.

The `REFERENCE` layer represents a historical copy of the painting. It is a special reference layer that cannot be painted on and does not affect the mask of filled damaged areas.

Like other layers, it has independent visibility and opacity settings. Its image data includes an alpha channel that can represent genuinely missing parts of the copy.

The layer is created when a historical copy is loaded. `LayersPanel.refresh_from_project()` also hides empty reference layers in older projects.

## 5. ProjectController

The application's main controller class is located in:

```
rp_restore/gui/project_controller.py
```

The `ProjectController` class connects the data model to the graphical interface. Most user actions eventually pass through the controller.

The controller is responsible for, among other things:

* the currently open project
* the active layer
* the active tool
* selection of damaged areas
* brush and texture settings
* updating the canvas
* updating panels
* running algorithms
* saving and opening projects
* exporting images
* ColorChecker correction
* Undo/Redo
* displaying messages to the user

The controller also handles loading and aligning historical copies and creating new independent proposals.

Important methods:

* `load_reference_image()` – loads an image, opens the alignment dialog, and inserts the copy into the project.
* `create_proposal_from_current_project()` – creates a separate project, either retaining or clearing the working layers.
* `run_realistic_fill_window()` – prepares the input window and runs realistic inpainting using the selected source image.

When creating a new proposal, the current project state is first serialized to a temporary ZIP file and then loaded as a new, independent `Project` object.

For a clean proposal, existing `PAINT` and `EDGE` layers are removed, new empty layers are created, and the original damage mask is reset to an unfilled state. The original image, historical copy, palette, and textures are preserved.

The new project is saved under a separate name and opened only after it has been saved successfully. The original project's unsaved changes are checked in `MainWindow.on_create_proposal_requested()`.

A typical event flow:

```
user clicks on the canvas
→ ImageCanvasWidget converts screen coordinates to image coordinates
→ ProjectController calls the active tool's method
→ the tool modifies data in Project
→ ProjectController refreshes the affected canvas region and panels
```

When modifying the application, first consider whether the functionality belongs in:

* the `Project` model
* the `ProjectController` controller
* a separate tool in `gui/tools`
* a panel in `gui/panels`

## 6. Canvas

The canvas is implemented in:

```
rp_restore/gui/canvas/image_canvas_widget.py
```

The `ImageCanvasWidget` class displays the composed image, handles zooming and panning, and converts coordinates between the screen and the image.

The canvas does not perform complex project modifications itself. It mainly serves as a display widget and a source of mouse events. Tool logic is separated into classes under `gui/tools`.

Selection highlighting is implemented using a helper function in:

```
rp_restore/gui/canvas/overlay_highlight.py
```

The main canvas uses an RGBA image created by `Project.composited_view_image()` and `Project.composited_view_region()`.

The background depends on the visibility of the `BACKGROUND` and `REFERENCE` layers. When both are visible, the historical copy replaces the original image only in areas defined by `damage_original_mask`. When `BACKGROUND` is hidden, the visible historical copy is used across the entire canvas.

The reference layer's opacity is applied to its alpha channel without blending in the original background underneath the replaced areas.

During partial canvas updates, `ImageCanvasWidget.patch_region()` uses `QPainter.CompositionMode_Source` so the new RGBA region completely replaces the previous pixels.

## 7. Tools

Interactive tools are located in:

```
rp_restore/gui/tools/
```

Each tool inherits from the `BaseTool` class:

```
rp_restore/gui/tools/base_tool.py
```

The base class defines these methods:

* `on_mouse_press()`
* `on_mouse_move()`
* `on_mouse_release()`
* `get_cursor()`

Current tools:

* `BrushTool` – brush and texture brush
* `EraserTool` – eraser
* `BlendTool` – smudge tool
* `FillTool` – region fill
* `SelectionTool` – selection by clicking
* `LassoTool` – lasso selection
* `EdgeTool` – drawing and erasing edges
* `EdgeBlendTool` – softening transitions across edges
* `PipetteTool` – eyedropper

To add a new tool:

1. Create a new class under `gui/tools`.
2. Inherit from `BaseTool`.
3. Implement mouse event handlers.
4. Register the tool in `MainWindow`.
5. Add the tool switch to `ProjectController.set_current_tool()`.
6. Add the cursor and panel settings if necessary.

## 8. Panels

Side panels are located in:

```
rp_restore/gui/panels/
```

Main panels:

* `LayersPanel` – layer display and management
* `PalettePanel` – color palette
* `MaterialsPanel` – brush, eraser, smudge, and texture settings
* `EdgeSettingsPanel` – edge settings
* `AlgorithmPanel` – running external algorithms

Panels typically communicate with the data model through `ProjectController` rather than working with it directly. This reduces the risk of the GUI state becoming inconsistent with the project state.

## 9. Saving and loading projects

Saving and loading projects is implemented in:

```
rp_restore/io/project_storage.py
```

The following classes are used:

* `ProjectSerializer`
* `ProjectLoader`

Projects are stored as `.zip` files. A ZIP archive mainly contains:

```
project.json
layers/
masks/
textures/
```

The `project.json` file contains project metadata, for example:

* project name
* list of layers
* paths to saved layer images
* paths to masks
* palette
* current color
* brush settings
* ColorChecker correction settings
* list of textures
* history for the report

Layer images and masks are saved as PNG files. When loading a project, the `Project`, `Layer`, `LayerMeta`, and `Texture` objects are reconstructed.
The historical copy is stored as a regular RGBA layer of type `REFERENCE`. Its image, visibility, opacity, and order are part of the project.

Older projects without a reference layer remain compatible. A historical copy can be loaded into them later.

## 10. Loading and saving images

Image helper functions are located in:

```
rp_restore/io/image_io.py
```

This module handles:

* loading images
* resizing an image to working dimensions
* saving the resulting image
* saving the mask

Image data is represented primarily by NumPy arrays. Individual layers and the image used for rendering the canvas are in RGBA format. Realistic inpainting inputs and exported result images use RGB.

## 11. Damage mask and regions

A damage mask is a two-dimensional Boolean NumPy array. A value of `True` identifies a damaged pixel.

Damage regions are determined from the damage mask and the edge layer. The logic is implemented in:

```
rp_restore/core/regions.py
```

Important components:

* `RegionInfo`
* `RegionMap`
* `build_region_map()`

Selections are represented by classes in:

```
rp_restore/core/selection.py
```

Main classes used:

* `Selection`
* `SelectionSet`

Selections are used by the Select and Lasso tools, region fill, auto-fill, and external algorithms.

## 12. Undo/Redo

The Undo/Redo system is located in:

```
rp_restore/core/history.py
```

Important classes:

* `UndoAction`
* `GlobalUndoManager`

Each pixel change is saved as an `UndoAction` containing:

* action description
* layer ID
* layer type
* bounding box of the changed area
* pixels before the change
* pixels after the change

Undo/Redo works globally across layers. After an Undo or Redo operation, filled damage masks are also synchronized with the layer's alpha channel.

When adding a new operation that modifies pixels, it is necessary to create and store an `UndoAction`; otherwise, the operation cannot be undone.

## 13. Texture brush

Texture logic is located in:

```
rp_restore/core/texture_brush.py
```

Important classes:

* `Texture`
* `TextureSettings`

Important functions:

* `generate_brush_stamp()` – generates a texture brush stamp
* `generate_fill_pattern()` – generates a texture fill pattern
* `deform_texture_image()` – deforms a texture
* `clear_texture_cache()` – clears the cache when settings change

Textures are stored in the project and may be original textures or derived, deformed variants.

## 14. Auto-fill

Automatic filling of small regions is implemented in:

```
rp_restore/core/auto_fill.py
```

Main function:

```
auto_fill_regions()
```

Auto-fill operates on damaged regions. For each selected region, it calculates a color from the surroundings and fills the region on the active Paint layer. The result is also stored in the Undo/Redo history.

## 15. Edges and edge blending

Drawing edges is implemented in the following tool:

```
rp_restore/gui/tools/edge_tool.py
```

The computational logic for softening the transition across an edge is located in:

```
rp_restore/core/edge_blend.py
```

The edge-softening tool is located in:

```
rp_restore/gui/tools/edge_blend_tool.py
```

Edge blending operates on a selected portion of an existing edge. The application creates a smoother transition between filled regions on either side of the edge and then removes the affected portion of that edge.

## 16. Smudging

The smudge tool is implemented in:

```
rp_restore/gui/tools/blend_tool.py
```

Smudging can use different sources depending on the Materials panel settings:

* the active Paint layer only
* a combination of the original image and the active Paint layer

The tool modifies damaged areas only and writes the changes to the active Paint layer.

## 17. External algorithms

External algorithms are run through:

```text
rp_restore/core/algorithm_runner.py
```

Important classes and data structures:

* `AlgorithmType` – distinguishes realistic and texture inpainting
* `RealisticFillMode` – distinguishes basic and guided realistic inpainting modes
* `AlgorithmRequest` – contains input images, masks, and algorithm parameters
* `TextureAlgorithmParams` – contains the texture algorithm's parameters
* `AlgorithmResult` – contains the resulting RGBA region, its position, and log messages
* `AlgorithmRunner` – prepares inputs and runs the appropriate algorithm

### Realistic inpainting

Realistic inpainting uses the client:

```python
painting_inpaint.remote
```

Access credentials are managed by:

```text
rp_restore/core/remote_restoration_config.py
```

The endpoint URL and API key are stored in the user's operating system credential store using `keyring`. The API key is not saved in the project or in an ordinary configuration file. Before launching the client, the credentials are set as environment variables for the running process only.

The user selects a rectangular window no larger than 1440 × 1440 pixels. If a region selection is active, the algorithm's mask is restricted to that selection. Otherwise, the remaining damage mask within the chosen window is used.

Two modes are supported:

* **Basic mode** allows the amount of regeneration to be set with the `partial_noise` parameter,
* **Guided mode** allows manually drawn guide lines to be used and is considerably slower than Basic mode.

The input source is selected independently of the algorithm mode. The `RealisticFillDialog` dialog offers three options:

* `original` – original image,
* `reference` – historical copy,
* `hybrid` – original image with the historical copy in areas defined by the original damage mask.

The historical copy is available as an input source only when the project contains a nonempty reference layer.

The input RGB region is prepared by `Project.realistic_input_region()`. When the historical copy is used, transparent pixels are replaced with the corresponding pixels of the original image. Partially transparent areas are blended according to the copy's alpha channel.

The reference layer's user-configured opacity and visibility on the canvas are not applied to the algorithm input.

The `use_composited_layers` parameter determines whether visible `PAINT` and `EDGE` layers are also composited over the selected source. By default, it is disabled in Basic mode and enabled in Guided mode.

The result is inserted into the active `PAINT` layer, limited to selected damaged pixels not yet filled on that layer.

### Texture inpainting

The texture algorithm is run using the installed package:

```python
texture_infill
```

Available models are discovered in the installed package's `models` directory using `importlib.resources`. Generation itself is performed by the public function:

```python
texture_infill.texture_infill.generate_infill()
```

The texture algorithm supports two output modes:

1. filling the currently selected damaged regions,
2. generating a separate texture to add to the project's materials.

When filling a region, the application computes the selection's bounding rectangle and passes only the corresponding region of the currently composed image and a mask of selected, still-unfilled damaged pixels to the algorithm. The resulting RGBA region is inserted back into the active Paint layer.

Texture algorithm settings include:

* texture model type
* one to three colors and the strength of each color layer
* scale along the X and Y axes
* density along the X and Y axes for supported models
* rotation and overall scale
* opaque or transparent background
* brightness of the opaque background
* seed
* dimensions of the separately generated texture

The dialog allows a reduced-size preview to be generated before running the final computation.

Separately generated textures are saved in the project together with the algorithm parameters, original colors, and color layer strengths. Their colors can later be edited and the texture regenerated in the Materials panel.

The `numba` library used by the texture package writes its cache into a writable application directory in the user's profile, avoiding writes to the installation directory.

## 18. ColorChecker correction

ColorChecker correction calculations are implemented in:

```
rp_restore/core/color_correction.py
```

The dialog is implemented in:

```
rp_restore/gui/colorchecker_dialog.py
```

The correction is calculated as a color transformation matrix. This matrix is saved in the project, and the correction can be enabled or disabled for previewing.

The correction is applied when composing the image for canvas display and when creating the exported result image and PDF report. However, it does not directly change the pixel values of individual layers, which remain stored in their original form.

## 19. Mask and historical copy alignment

Damage mask alignment logic is implemented in:

```
rp_restore/core/mask_alignment.py
```

The point selection dialog is implemented in:

```
rp_restore/gui/mask_alignment_dialog.py
```

The user selects corresponding points on the original image and the mask. These points are used to calculate a homography, and the mask is transformed to match the dimensions of the original image.

The same `MaskAlignmentDialog` is used to align historical copies. The `reference_mode=True` parameter changes the dialog labels and how the input images are presented.

The copy is aligned with the existing original image at the project's working resolution.

A homography is calculated by `compute_homography()` from corresponding points on the historical copy and original image. The copy is transformed by `warp_rgba_to_image()`, which preserves its alpha channel and transparency outside the transformed image.

Premultiplied alpha is used during interpolation to prevent dark fringes around transparent regions.

Important functions:

* `compute_homography()`
* `warp_mask_to_image()`
* `warp_rgba_to_image()` – transforms a historical copy while preserving transparency
* `rgb_to_damage_mask()`

## 20. PDF report

PDF reports are generated in:

```
rp_restore/report/pdf_report.py
```

The report dialog is implemented in:

```
rp_restore/report/report_dialog.py
```

Important components:

* `ReportMetadata`
* `generate_report()`

The report contains the original image, damage mask, resulting image, remaining damage mask, statistics, and layer previews.

The resulting image in the PDF report is obtained through `Project.get_export_image()`. It therefore always includes the original background and visible working layers, without the historical copy.

If the project contains a historical copy, `_add_layers_section()` adds it to a separate **Referenční obraz** (Reference image) section. The copy is documented but not included in the reconstructed result.

Most changes to report content are made in `pdf_report.py`.

## 21. Application settings

Settings are implemented in:

```
rp_restore/config/settings.py
```

The `AppSettings` class currently stores primarily the list of recently opened projects.

Access settings for remote realistic inpainting are not stored through `AppSettings`. The endpoint URL and API key are managed by `remote_restoration_config.py` and stored in the operating system's credential store using `keyring`.

Settings are saved to:

```
~/.rp_restore/settings.json
```

If settings cannot be loaded or saved, the application ignores the error and uses the default state.

## 22. Typical code workflow

Example: a user draws with the brush.

```
1. The user selects the Štětec (Brush) tool in MainWindow
2. MainWindow notifies ProjectController
3. ProjectController activates BrushTool
4. The user clicks on ImageCanvasWidget
5. The canvas converts the cursor position to image coordinates
6. ProjectController calls BrushTool.on_mouse_press()
7. BrushTool modifies pixels on the active Paint layer
8. An UndoAction is created
9. The filled damage mask is synchronized
10. ProjectController refreshes the affected canvas region
```

Other tools follow a similar principle.

### Loading a historical copy

1. The user selects **Načíst historickou kopii...** (Load historical copy...).
2. `MainWindow` calls `ProjectController.load_reference_image()`.
3. `MaskAlignmentDialog` opens in reference mode.
4. A homography is calculated from the selected pairs of points.
5. `warp_rgba_to_image()` creates the aligned RGBA image.
6. The image is stored in the `REFERENCE` layer and the canvas is refreshed.

### Creating a new proposal

1. The user selects the new proposal option.
2. `MainWindow` handles the working-layer option and any prompt to save the original project.
3. `ProjectController.create_proposal_from_current_project()` creates an independent project copy.
4. For a clean proposal, empty `PAINT` and `EDGE` layers are initialized and the original damage mask is restored.
5. The new project is saved as a separate ZIP file and opened in the application.

## 23. Summary

The application is built around the `Project` class, which holds the project data, and the `ProjectController` class, which connects the model to the graphical interface. Individual tools are separate classes that respond to mouse events. Layers, masks, and textures are stored as NumPy arrays, and the entire project is serialized into a ZIP file.
