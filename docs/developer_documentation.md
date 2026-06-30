# RePaint – programátorská dokumentácia

## Obsah

* [1. Základná štruktúra projektu](#1-základná-štruktúra-projektu)
* [2. Hlavné použité knižnice](#2-hlavné-použité-knižnice)
* [3. Dátový model projektu](#3-dátový-model-projektu)
* [4. Vrstvy](#4-vrstvy)
* [5. ProjectController](#5-projectcontroller)
* [6. Canvas](#6-canvas)
* [7. Nástroje](#7-nástroje)
* [8. Panely](#8-panely)
* [9. Ukladanie a načítanie projektu](#9-ukladanie-a-načítanie-projektu)
* [10. Načítanie a ukladanie obrázkov](#10-načítanie-a-ukladanie-obrázkov)
* [11. Maska poškodenia a regióny](#11-maska-poškodenia-a-regióny)
* [12. Undo/Redo](#12-undoredo)
* [13. Textúrový štetec](#13-textúrový-štetec)
* [14. Auto-výplň](#14-auto-výplň)
* [15. Hrany a zjemnenie hrán](#15-hrany-a-zjemnenie-hrán)
* [16. Rozmazanie](#16-rozmazanie)
* [17. Externé algoritmy](#17-externé-algoritmy)
* [18. ColorChecker korekcia](#18-colorchecker-korekcia)
* [19. Zarovnanie masky](#19-zarovnanie-masky)
* [20. PDF report](#20-pdf-report)
* [21. Nastavenia aplikácie](#21-nastavenia-aplikácie)
* [22. Typický tok práce v kóde](#22-typický-tok-práce-v-kóde)
* [23. Zhrnutie](#23-zhrnutie)


Aplikácia je napísaná v jazyku Python a používa knižnicu PySide6 na grafické používateľské rozhranie. Na prácu s obrazovými dátami sa používa najmä NumPy, Pillow a OpenCV.

## 1. Základná štruktúra projektu

Hlavný balík aplikácie sa nachádza v priečinku `rp_restore`.

Zjednodušená štruktúra:

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
│   ├── selection.py
│   └── texture_brush.py
├── gui/
│   ├── main_window.py
│   ├── project_controller.py
│   ├── mask_alignment_dialog.py
│   ├── colorchecker_dialog.py
│   ├── realistic_fill_dialog.py
│   ├── texture_fill_dialog.py
│   ├── start_screen_widget.py
│   ├── canvas/
│   ├── panels/
│   └── tools/
├── io/
│   ├── image_io.py
│   └── project_storage.py
└── report/
    ├── pdf_report.py
    └── report_dialog.py
```

Kód je rozdelený na niekoľko vrstiev:

* `core` obsahuje dátový model a výpočtovú logiku
* `gui` obsahuje grafické rozhranie a ovládanie aplikácie
* `gui/tools` obsahuje jednotlivé nástroje
* `gui/panels` obsahuje bočné panely aplikácie
* `io` rieši načítanie a ukladanie obrázkov a projektov
* `report` rieši generovanie PDF reportu
* `config` obsahuje nastavenia aplikácie

## 2. Hlavné použité knižnice

Aplikácia používa najmä tieto externé knižnice:

* `PySide6` – grafické rozhranie
* `numpy` – reprezentácia a úprava obrazových dát
* `Pillow` – načítanie a ukladanie obrázkov
* `opencv-python` / `cv2` – vybrané obrazové operácie
* `reportlab` – generovanie PDF reportov
* `painting_inpaint` – vzdialené realistické dopĺňanie
* externý textúrový algoritmus sa musí nachádzať v priečinku `external_algorithms`

## 3. Dátový model projektu

Hlavná trieda dátového modelu je `Project` v súbore:

```
rp_restore/core/project_model.py
```

Trieda `Project` reprezentuje jeden otvorený projekt. Obsahuje:

* názov projektu
* cestu k pôvodnému obrazu
* pôvodný pracovný obraz
* zoznam vrstiev
* pôvodnú masku poškodenia
* masky vyplnenia poškodenia
* paletu farieb
* nastavenia štetca
* textúry
* nastavenia ColorChecker korekcie
* undo/redo manažér

Dôležité metódy triedy `Project`:

* `add_layer()` – pridanie vrstvy
* `remove_layer()` – odstránenie vrstvy typu Paint
* `get_background_layer()` – získanie pôvodného obrazu
* `get_paint_layers()` – získanie všetkých Paint vrstiev
* `get_edge_layer()` – získanie vrstvy hrán
* `composited_image()` – poskladanie výsledného obrazu
* `composited_region()` – poskladanie iba časti obrazu
* `set_damage_masks()` – nastavenie masky poškodenia
* `get_damage_remaining_mask()` – získanie zostávajúceho poškodenia
* `get_selection_from_click()` – výber regiónu kliknutím
* `get_selections_from_polygon()` – výber regiónov pomocou lasa
* `sync_layer_filled_mask_from_alpha()` – zosynchronizovanie masky vyplnenia podľa alfa kanála vrstvy

## 4. Vrstvy

Vrstvy sú definované v súbore:

```
rp_restore/core/layers.py
```

Používajú sa tri typy vrstiev:

```python
class LayerRole(str, Enum):
    BACKGROUND = "background"
    EDGE = "edge"
    PAINT = "paint"
```

Každá vrstva je reprezentovaná triedou `Layer`, ktorá obsahuje:

* `meta` – metadata vrstvy
* `image` – obrazové dáta vo formáte RGBA
* `damage_filled_mask` – informáciu o tom, ktoré poškodené pixely sú vyplnené na tejto vrstve

Metadata vrstvy sú uložené v triede `LayerMeta`. Obsahujú napríklad:

* interné ID vrstvy
* názov vrstvy
* typ vrstvy
* viditeľnosť
* priehľadnosť
* poradie vrstvy

Vrstvy používajú obrazové dáta ako NumPy pole tvaru:

```
(height, width, 4)
```

Typ dát je `uint8` a kanály sú v poradí RGBA.

## 5. ProjectController

Najdôležitejšia riadiaca trieda aplikácie je:

```
rp_restore/gui/project_controller.py
```

Trieda `ProjectController` prepája dátový model s grafickým rozhraním. Väčšina používateľských akcií nakoniec prechádza cez controller.

Controller zodpovedá napríklad za:

* aktuálne otvorený projekt
* aktívnu vrstvu
* aktívny nástroj
* výber poškodených oblastí
* nastavenia štetca a textúr
* aktualizáciu canvasu
* aktualizáciu panelov
* spúšťanie algoritmov
* ukladanie a otváranie projektu
* export obrazu
* ColorChecker korekciu
* Undo/Redo
* zobrazenie hlášok používateľovi

Typický tok udalosti je:

```
používateľ klikne do canvasu
→ ImageCanvasWidget prepočíta súradnice obrazovky na súradnice obrazu
→ ProjectController zavolá metódu aktívneho nástroja
→ nástroj upraví dáta v Project
→ ProjectController obnoví príslušnú časť canvasu a panelov
```

Pri úpravách aplikácie je dobré najskôr skontrolovať, či daná funkcionalita patrí do:

* modelu `Project`
* controlleru `ProjectController`
* samostatného nástroja v `gui/tools`
* panelu v `gui/panels`

## 6. Canvas

Canvas je implementovaný v súbore:

```
rp_restore/gui/canvas/image_canvas_widget.py
```

Trieda `ImageCanvasWidget` zobrazuje výsledný obraz, rieši zoom, posun obrazu a prevod súradníc medzi obrazovkou a obrazom.

Canvas sám nevykonáva zložité úpravy projektu. Slúži hlavne ako zobrazovací prvok a zdroj udalostí myši. Logika nástrojov je oddelená v triedach v priečinku `gui/tools`.

Zvýraznenie výberu je implementované pomocou pomocnej funkcie v:

```
rp_restore/gui/canvas/overlay_highlight.py
```

## 7. Nástroje

Interaktívne nástroje sú v priečinku:

```
rp_restore/gui/tools/
```

Každý nástroj dedí zo základnej triedy `BaseTool`:

```
rp_restore/gui/tools/base_tool.py
```

Základná trieda definuje metódy:

* `on_mouse_press()`
* `on_mouse_move()`
* `on_mouse_release()`
* `get_cursor()`

Aktuálne nástroje:

* `BrushTool` – štetec a textúrový štetec
* `EraserTool` – guma
* `BlendTool` – rozmazanie
* `FillTool` – výplň regiónu
* `SelectionTool` – výber kliknutím
* `LassoTool` – výber lasom
* `EdgeTool` – kreslenie a mazanie hrán
* `EdgeBlendTool` – zjemnenie prechodu cez hranu
* `PipetteTool` – pipeta

Ak treba pridať nový nástroj, tak by to bolo takto:

1. Vytvoriť novú triedu v `gui/tools`
2. Zdediť z `BaseTool`
3. Implementovať reakcie na udalosti myši
4. Zaregistrovať nástroj v `MainWindow`
5. Doplniť prepnutie nástroja v `ProjectController.set_current_tool()`
6. Podľa potreby doplniť kurzor a panelové nastavenia

## 8. Panely

Bočné panely sa nachádzajú v priečinku:

```
rp_restore/gui/panels/
```

Hlavné panely:

* `LayersPanel` – zobrazenie a správa vrstiev
* `PalettePanel` – paleta farieb
* `MaterialsPanel` – nastavenia štetca, gumy, rozmazania a textúr
* `EdgeSettingsPanel` – nastavenia hrán
* `AlgorithmPanel` – spúšťanie externých algoritmov

Panely nepracujú priamo s dátovým modelom projektu, ale typicky komunikujú cez `ProjectController`. To znižuje riziko, že sa stav GUI a stav projektu rozídu.

## 9. Ukladanie a načítanie projektu

Ukladanie a načítanie projektov je implementované v súbore:

```
rp_restore/io/project_storage.py
```

Používajú sa triedy:

* `ProjectSerializer`
* `ProjectLoader`

Projekt sa ukladá ako `.zip` súbor. Vnútri ZIP-u sa nachádza najmä:

```
project.json
layers/
masks/
textures/
```

Súbor `project.json` obsahuje metadata projektu, napríklad:

* názov projektu
* zoznam vrstiev
* cesty k uloženým obrázkom vrstiev
* cesty k maskám
* paletu
* aktuálnu farbu
* nastavenia štetca
* nastavenia ColorChecker korekcie
* zoznam textúr
* históriu pre report

Obrázky vrstiev a masky sa ukladajú ako PNG. Pri načítaní sa znovu vytvoria objekty `Project`, `Layer`, `LayerMeta` a `Texture`.

## 10. Načítanie a ukladanie obrázkov

Pomocné funkcie pre obrázky sú v:

```
rp_restore/io/image_io.py
```

Tento modul rieši:

* načítanie obrázkov
* zmenu obrázka na pracovnú veľkosť
* uloženie výsledného obrazu
* uloženie masky

Obrazové dáta sa v aplikácii väčšinou držia ako NumPy polia. Pri vrstvách sa používa RGBA, pri výslednom zloženom obraze RGB.

## 11. Maska poškodenia a regióny

Maska poškodenia je dvojrozmerné bool NumPy pole. Hodnota `True` označuje poškodený pixel.

Regióny poškodenia sa vytvárajú podľa masky poškodenia a vrstvy hrán. Logika je v súbore:

```
rp_restore/core/regions.py
```

Dôležité prvky:

* `RegionInfo`
* `RegionMap`
* `build_region_map()`

Výber oblastí je reprezentovaný triedami v:

```
rp_restore/core/selection.py
```

Používajú sa hlavne:

* `Selection`
* `SelectionSet`

Výbery sa používajú pri nástroji Vybrat, Laso, výplni, auto-výplni a externých algoritmoch.

## 12. Undo/Redo

Undo/Redo systém sa nachádza v:

```
rp_restore/core/history.py
```

Dôležité triedy:

* `UndoAction`
* `GlobalUndoManager`

Každá zmena pixelov sa ukladá ako `UndoAction`, ktorá obsahuje:

* popis akcie
* ID vrstvy
* typ vrstvy
* bounding box zmenenej oblasti
* pixely pred zmenou
* pixely po zmene

Undo/Redo funguje globálne naprieč vrstvami. Po aplikovaní Undo alebo Redo sa synchronizujú aj masky vyplnenia poškodenia podľa alfa kanála vrstvy.

Pri pridávaní novej úpravy, ktorá mení pixely, je potrebné vytvoriť a uložiť `UndoAction`, inak sa zmena nebude dať vrátiť.

## 13. Textúrový štetec

Logika textúr je v súbore:

```
rp_restore/core/texture_brush.py
```

Dôležité triedy:

* `Texture`
* `TextureSettings`

Dôležité funkcie:

* `generate_brush_stamp()` – vytvorenie stopy textúrového štetca
* `generate_fill_pattern()` – vytvorenie textúrového vzoru pre výplň
* `deform_texture_image()` – deformácia textúry
* `clear_texture_cache()` – vyčistenie cache pri zmene nastavení

Textúry sa ukladajú do projektu a môžu byť buď pôvodné, alebo odvodené deformované textúry.

## 14. Auto-výplň

Auto-výplň malých oblastí je implementovaná v:

```
rp_restore/core/auto_fill.py
```

Hlavná funkcia je:

```
auto_fill_regions()
```

Auto-výplň pracuje s regiónmi poškodenia. Pre každý vybraný región vypočíta farbu z okolia a vyplní ho na aktívnej Paint vrstve. Výsledok sa uloží aj do Undo/Redo histórie.

## 15. Hrany a zjemnenie hrán

Kreslenie hrán je v nástroji:

```
rp_restore/gui/tools/edge_tool.py
```

Výpočtová logika zjemnenia prechodu cez hranu je v:

```
rp_restore/core/edge_blend.py
```

Nástroj na zjemnenie hrán je:

```
rp_restore/gui/tools/edge_blend_tool.py
```

Zjemnenie hrany pracuje s vybranou časťou existujúcej hrany. Aplikácia vytvorí mäkší prechod medzi vyplnenými oblasťami po oboch stranách hrany a následne odstráni zasiahnutú časť hrany.

## 16. Rozmazanie

Nástroj rozmazania je implementovaný v:

```
rp_restore/gui/tools/blend_tool.py
```

Rozmazanie môže používať rôzny zdroj podľa nastavenia v paneli Materiály:

* iba aktívnu Paint vrstvu
* kombináciu pôvodného obrazu a aktívnej Paint vrstvy

Nástroj upravuje len poškodené oblasti a zmeny zapisuje do aktívnej Paint vrstvy.

## 17. Externé algoritmy

Spúšťanie externých algoritmov je v súbore:

```
rp_restore/core/algorithm_runner.py
```

Dôležité triedy:

* `AlgorithmType`
* `AlgorithmRequest`
* `TextureAlgorithmParams`
* `AlgorithmResult`
* `AlgorithmRunner`

Podporované typy algoritmov:

```python
AlgorithmType.REALISTIC
AlgorithmType.TEXTURE
```

Realistické dopĺňanie používa vzdialený klient `painting_inpaint`. Algoritmus dostáva výrez obrazu a masku výrezu. Výstupom je RGBA patch, ktorý sa aplikuje do aktívnej Paint vrstvy.

Textúrové dopĺňanie zatiaľ používa externý textúrový pipeline v priečinku:

```
external_algorithms/texture_generation_pipeline
```

Pri spustení sa pripraví maska výberu, farby a parametre textúry. Výstup sa oreže podľa bounding boxu výberu a vloží sa do projektu.

Pri pridávaní nového algoritmu je vhodné:

1. Doplniť nový typ do `AlgorithmType`
2. Rozšíriť `AlgorithmRequest` alebo vytvoriť nové parametre
3. Pridať vetvu do `AlgorithmRunner.run()`
4. Pripraviť dialóg alebo ovládanie v `gui`
5. Výsledok vrátiť ako `AlgorithmResult`
6. V `ProjectController` zabezpečiť vloženie výsledku do aktívnej Paint vrstvy a uloženie Undo akcie

## 18. ColorChecker korekcia

Výpočtová časť ColorChecker korekcie je v:

```
rp_restore/core/color_correction.py
```

Dialóg je v:

```
rp_restore/gui/colorchecker_dialog.py
```

Korekcia sa počíta ako farebná transformačná matica. Táto matica sa uloží do projektu a môže sa zapínať alebo vypínať pre náhľad.

Korekcia sa aplikuje pri skladaní výsledného obrazu, ale nemení priamo pixely jednotlivých vrstiev. Slúži teda ako zobrazovacia korekcia.

## 19. Zarovnanie masky

Logika zarovnania masky je v:

```
rp_restore/core/mask_alignment.py
```

Dialóg na výber bodov je v:

```
rp_restore/gui/mask_alignment_dialog.py
```

Používateľ vyberie zodpovedajúce body medzi pôvodným obrazom a maskou. Z nich sa vypočíta homografia a maska sa transformuje na rozmery pôvodného obrazu.

Dôležité funkcie:

* `compute_homography()`
* `warp_mask_to_image()`
* `rgb_to_damage_mask()`

## 20. PDF report

Generovanie PDF reportu je v:

```
rp_restore/report/pdf_report.py
```

Dialóg pre vyplnenie údajov je v:

```
rp_restore/report/report_dialog.py
```

Dôležité prvky:

* `ReportMetadata`
* `generate_report()`

Report obsahuje pôvodný obraz, masku poškodenia, výsledný obraz, zostávajúcu masku, štatistiky a náhľady vrstiev

Pri úprave obsahu reportu sa väčšina zmien robí v súbore `pdf_report.py`.

## 21. Nastavenia aplikácie

Nastavenia sú v:

```
rp_restore/config/settings.py
```

Trieda `AppSettings` aktuálne ukladá najmä zoznam naposledy otvorených projektov.

Nastavenia sa ukladajú do:

```
~/.rp_restore/settings.json
```

Ak sa nastavenia nepodarí načítať alebo uložiť, aplikácia chybu ignoruje a použije predvolený stav.

## 22. Typický tok práce v kóde

Príklad: používateľ použije štetec.

```
1. Používateľ vyberie nástroj Štětec v MainWindow
2. MainWindow informuje ProjectController
3. ProjectController nastaví aktívny BrushTool
4. Používateľ klikne do ImageCanvasWidget
5. Canvas prevedie pozíciu kurzora na súradnice obrazu
6. ProjectController zavolá BrushTool.on_mouse_press()
7. BrushTool upraví pixely aktívnej Paint vrstvy
8. Vytvorí sa UndoAction
9. Synchronizuje sa maska vyplnenia poškodenia
10. ProjectController obnoví príslušnú časť canvasu
```

Podobný princíp používajú aj ostatné nástroje.

## 23. Zhrnutie

Aplikácia je postavená okolo triedy `Project`, ktorá drží všetky dáta projektu, a triedy `ProjectController`, ktorá prepája model s grafickým rozhraním. Jednotlivé nástroje sú samostatné triedy reagujúce na udalosti myši. Vrstvy, masky a textúry sú uložené ako NumPy polia a celý projekt sa serializuje do ZIP súboru.
