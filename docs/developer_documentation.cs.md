# RePaint – programátorská dokumentace

**Language / Jazyk:** [English](developer_documentation.en.md) | [Čeština](developer_documentation.cs.md) | [Slovenčina](developer_documentation.md)

## Obsah

* [1. Základní struktura projektu](#1-základní-struktura-projektu)
* [2. Hlavní použité knihovny](#2-hlavní-použité-knihovny)
* [3. Datový model projektu](#3-datový-model-projektu)
* [4. Vrstvy](#4-vrstvy)
* [5. ProjectController](#5-projectcontroller)
* [6. Canvas](#6-canvas)
* [7. Nástroje](#7-nástroje)
* [8. Panely](#8-panely)
* [9. Ukládání a načítání projektu](#9-ukládání-a-načítání-projektu)
* [10. Načítání a ukládání obrázků](#10-načítání-a-ukládání-obrázků)
* [11. Maska poškození a regiony](#11-maska-poškození-a-regiony)
* [12. Undo/Redo](#12-undoredo)
* [13. Texturový štětec](#13-texturový-štětec)
* [14. Automatická výplň](#14-automatická-výplň)
* [15. Hrany a zjemnění hran](#15-hrany-a-zjemnění-hran)
* [16. Rozmazání](#16-rozmazání)
* [17. Externí algoritmy](#17-externí-algoritmy)
* [18. ColorChecker korekce](#18-colorchecker-korekce)
* [19. Zarovnání masky a historické kopie](#19-zarovnání-masky-a-historické-kopie)
* [20. PDF report](#20-pdf-report)
* [21. Nastavení aplikace](#21-nastavení-aplikace)
* [22. Typický tok práce v kódu](#22-typický-tok-práce-v-kódu)
* [23. Shrnutí](#23-shrnutí)


Aplikace je napsaná v jazyce Python a pro grafické uživatelské rozhraní používá knihovnu PySide6. Pro práci s obrazovými daty se používají především NumPy, Pillow a OpenCV.

## 1. Základní struktura projektu

Hlavní balík aplikace se nachází v adresáři `rp_restore`.

Zjednodušená struktura:

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

Kód je rozdělen na několik částí:

* `core` obsahuje datový model a výpočetní logiku
* `gui` obsahuje grafické rozhraní a ovládání aplikace
* `gui/tools` obsahuje jednotlivé nástroje
* `gui/panels` obsahuje boční panely aplikace
* `io` zajišťuje načítání a ukládání obrázků a projektů
* `report` zajišťuje generování PDF reportů
* `config` obsahuje nastavení aplikace
* `resources` obsahuje výchozí textury, náhledy modelů a grafické zdroje aplikace

## 2. Hlavní použité knihovny

Aplikace používá především následující externí knihovny a balíky:

* `PySide6` – grafické uživatelské rozhraní
* `numpy` – reprezentace a úpravy obrazových dat
* `Pillow` – načítání, převody a ukládání obrázků
* `opencv-python` / `cv2` – vybrané obrazové operace
* `reportlab` – generování PDF reportů
* `keyring` – ukládání endpointu a API klíče vzdálené služby do systémového úložiště přihlašovacích údajů
* `painting_inpaint.remote` – klient vzdáleného realistického doplňování
* `texture_infill` – lokálně spouštěný texturový algoritmus

Texturový algoritmus se používá jako nainstalovaný balík Pythonu. Není uložen ve zdrojovém adresáři aplikace. Jeho modelové soubory jsou součástí balíku `texture_infill`.

## 3. Datový model projektu

Hlavní třídou datového modelu je `Project` v souboru:

```
rp_restore/core/project_model.py
```

Třída `Project` reprezentuje jeden otevřený projekt. Obsahuje:

* název projektu
* cestu k původnímu obrazu
* původní pracovní obraz
* seznam vrstev
* původní masku poškození
* masky vyplněného poškození
* historickou kopii obrazu
* paletu barev
* nastavení štětce
* textury
* nastavení ColorChecker korekce
* správce Undo/Redo

Důležité metody třídy `Project`:

* `add_layer()` – přidání vrstvy
* `remove_layer()` – odstranění vrstvy typu Paint
* `get_background_layer()` – získání vrstvy původního obrazu
* `get_paint_layers()` – získání všech vrstev Paint
* `get_edge_layer()` – získání vrstvy hran
* `composited_image()` – složení výsledného obrazu
* `composited_region()` – složení pouze části obrazu
* `set_damage_masks()` – nastavení masky poškození
* `get_damage_remaining_mask()` – získání zbývajícího poškození
* `get_selection_from_click()` – výběr regionu kliknutím
* `get_selections_from_polygon()` – výběr regionů pomocí lasa
* `sync_layer_filled_mask_from_alpha()` – synchronizace masky vyplnění podle alfa kanálu vrstvy
* `get_reference_layer()` – získání historické kopie
* `composited_view_image()` – vytvoření RGBA obrazu pro hlavní plátno
* `composited_view_region()` – vytvoření RGBA výřezu plátna
* `realistic_input_region()` – příprava RGB vstupu realistického algoritmu podle zvoleného podkladu
* `get_export_image()` – vytvoření finálního obrazu s vynuceným původním pozadím

Skládání obrazu je rozděleno podle účelu. Metody `composited_view_image()` a `composited_view_region()` připravují RGBA obraz pro vykreslování na plátně.

Původní metody `composited_image()` a `composited_region()` pracují s RGB kompozicí původního pozadí a pracovních vrstev. Historická kopie do nich není zahrnuta.

Metoda `get_export_image()` používá `composited_image()` s parametrem `force_original_background=True`, čímž zajišťuje export původního obrazu nezávisle na jeho viditelnosti na plátně.

## 4. Vrstvy

Vrstvy jsou definovány v souboru:

```
rp_restore/core/layers.py
```

Používají se čtyři typy vrstev:

```python
class LayerRole(str, Enum):
    BACKGROUND = "background"
    REFERENCE = "reference"
    EDGE = "edge"
    PAINT = "paint"
```

Každá vrstva je reprezentována třídou `Layer`, která obsahuje:

* `meta` – metadata vrstvy
* `image` – obrazová data ve formátu RGBA
* `damage_filled_mask` – informaci o tom, které poškozené pixely jsou na dané vrstvě vyplněné

Metadata vrstvy jsou uložena ve třídě `LayerMeta`. Obsahují například:

* interní ID vrstvy
* název vrstvy
* typ vrstvy
* viditelnost
* průhlednost
* pořadí vrstvy

Vrstvy používají obrazová data jako pole NumPy o tvaru:

```
(height, width, 4)
```

Datový typ je `uint8` a kanály jsou v pořadí RGBA.

Vrstva typu `REFERENCE` reprezentuje historickou kopii obrazu. Jde o speciální referenční vrstvu, která není určena ke kreslení a neovlivňuje masku vyplněných poškozených míst.

Stejně jako ostatní vrstvy podporuje vlastní viditelnost a krytí. Její obrazová data obsahují také alfa kanál, který umožňuje reprezentovat skutečně chybějící části kopie.

Vrstva se vytvoří při načtení historické kopie. `LayersPanel.refresh_from_project()` zároveň nezobrazuje prázdné referenční vrstvy ze starších projektů.

## 5. ProjectController

Nejdůležitější řídicí třída aplikace je v souboru:

```
rp_restore/gui/project_controller.py
```

Třída `ProjectController` propojuje datový model s grafickým rozhraním. Většina uživatelských akcí nakonec prochází přes controller.

Controller odpovídá například za:

* aktuálně otevřený projekt
* aktivní vrstvu
* aktivní nástroj
* výběr poškozených oblastí
* nastavení štětce a textur
* aktualizaci plátna
* aktualizaci panelů
* spouštění algoritmů
* ukládání a otevírání projektů
* export obrazu
* ColorChecker korekci
* Undo/Redo
* zobrazování hlášení uživateli

Controller dále zajišťuje načítání a zarovnávání historické kopie a vytváření nových nezávislých návrhů.

Důležité metody:

* `load_reference_image()` – načtení obrázku, otevření zarovnávacího dialogu a vložení kopie do projektu.
* `create_proposal_from_current_project()` – vytvoření samostatného projektu se zachovanými nebo prázdnými pracovními vrstvami.
* `run_realistic_fill_window()` – příprava vstupního okna a spuštění realistického doplnění podle vybraného podkladu.

Při vytváření nového návrhu se aktuální stav projektu nejprve serializuje do dočasného ZIP souboru a následně se načte jako nový nezávislý objekt `Project`.

U čistého návrhu se odstraní existující vrstvy `PAINT` a `EDGE`, vytvoří se nové prázdné vrstvy a původní maska poškození se nastaví jako nevyplněná. Původní obraz, historická kopie, paleta a textury se zachovají.

Nový projekt se uloží pod samostatným názvem a otevře se až po úspěšném uložení. Kontrola neuložených změn původního projektu se provádí v `MainWindow.on_create_proposal_requested()`.

Typický tok události:

```
uživatel klikne do plátna
→ ImageCanvasWidget převede souřadnice obrazovky na souřadnice obrazu
→ ProjectController zavolá metodu aktivního nástroje
→ nástroj upraví data v Project
→ ProjectController obnoví příslušnou část plátna a panelů
```

Při úpravách aplikace je vhodné nejprve zkontrolovat, zda daná funkcionalita patří do:

* modelu `Project`
* controlleru `ProjectController`
* samostatného nástroje v `gui/tools`
* panelu v `gui/panels`

## 6. Canvas

Plátno je implementováno v souboru:

```
rp_restore/gui/canvas/image_canvas_widget.py
```

Třída `ImageCanvasWidget` zobrazuje složený obraz, zajišťuje zoom, posun obrazu a převod souřadnic mezi obrazovkou a obrazem.

Plátno samo neprovádí složité úpravy projektu. Slouží především jako zobrazovací prvek a zdroj událostí myši. Logika nástrojů je oddělena do tříd v adresáři `gui/tools`.

Zvýraznění výběru je implementováno pomocnou funkcí v:

```
rp_restore/gui/canvas/overlay_highlight.py
```

Hlavní plátno používá RGBA obraz vytvořený metodami `Project.composited_view_image()` a `Project.composited_view_region()`.

Podklad závisí na viditelnosti vrstev `BACKGROUND` a `REFERENCE`. Pokud jsou obě viditelné, historická kopie nahrazuje původní obraz pouze v oblastech určených `damage_original_mask`. Při skrytém `BACKGROUND` se viditelná kopie používá na celém plátně.

Krytí referenční vrstvy se aplikuje na její alfa kanál bez přimíchávání původního pozadí v nahrazených oblastech.

Při částečném překreslování plátna používá `ImageCanvasWidget.patch_region()` režim `QPainter.CompositionMode_Source`, aby nový RGBA výřez zcela nahradil předchozí pixely.

## 7. Nástroje

Interaktivní nástroje se nacházejí v adresáři:

```
rp_restore/gui/tools/
```

Každý nástroj dědí ze základní třídy `BaseTool`:

```
rp_restore/gui/tools/base_tool.py
```

Základní třída definuje metody:

* `on_mouse_press()`
* `on_mouse_move()`
* `on_mouse_release()`
* `get_cursor()`

Aktuální nástroje:

* `BrushTool` – štětec a texturový štětec
* `EraserTool` – guma
* `BlendTool` – rozmazání
* `FillTool` – výplň regionu
* `SelectionTool` – výběr kliknutím
* `LassoTool` – výběr lasem
* `EdgeTool` – kreslení a mazání hran
* `EdgeBlendTool` – zjemnění přechodu přes hranu
* `PipetteTool` – pipeta

Pro přidání nového nástroje je potřeba:

1. Vytvořit novou třídu v `gui/tools`.
2. Zdědit z `BaseTool`.
3. Implementovat reakce na události myši.
4. Zaregistrovat nástroj v `MainWindow`.
5. Doplnit přepnutí nástroje v `ProjectController.set_current_tool()`.
6. Podle potřeby doplnit kurzor a panelová nastavení.

## 8. Panely

Boční panely se nacházejí v adresáři:

```
rp_restore/gui/panels/
```

Hlavní panely:

* `LayersPanel` – zobrazení a správa vrstev
* `PalettePanel` – paleta barev
* `MaterialsPanel` – nastavení štětce, gumy, rozmazání a textur
* `EdgeSettingsPanel` – nastavení hran
* `AlgorithmPanel` – spouštění externích algoritmů

Panely obvykle nepracují přímo s datovým modelem projektu, ale komunikují přes `ProjectController`. To snižuje riziko, že se stav GUI a stav projektu rozejdou.

## 9. Ukládání a načítání projektu

Ukládání a načítání projektů je implementováno v souboru:

```
rp_restore/io/project_storage.py
```

Používají se třídy:

* `ProjectSerializer`
* `ProjectLoader`

Projekt se ukládá jako soubor `.zip`. Uvnitř ZIP archivu se nachází zejména:

```
project.json
layers/
masks/
textures/
```

Soubor `project.json` obsahuje metadata projektu, například:

* název projektu
* seznam vrstev
* cesty k uloženým obrázkům vrstev
* cesty k maskám
* paletu
* aktuální barvu
* nastavení štětce
* nastavení ColorChecker korekce
* seznam textur
* historii pro report

Obrázky vrstev a masky se ukládají jako PNG. Při načtení se znovu vytvoří objekty `Project`, `Layer`, `LayerMeta` a `Texture`.
Historická kopie se ukládá jako běžná RGBA vrstva typu `REFERENCE`. Její obrázek, viditelnost, krytí a pořadí jsou součástí projektu.

Starší projekty bez referenční vrstvy zůstávají kompatibilní. Historickou kopii do nich lze dodatečně načíst.

## 10. Načítání a ukládání obrázků

Pomocné funkce pro obrázky jsou v:

```
rp_restore/io/image_io.py
```

Tento modul zajišťuje:

* načítání obrázků
* změnu obrázku na pracovní velikost
* uložení výsledného obrazu
* uložení masky

Obrazová data se v aplikaci reprezentují jako pole NumPy. Jednotlivé vrstvy i obraz určený k vykreslení na plátně používají RGBA. Vstupy realistického algoritmu a exportovaný výsledný obraz používají RGB.

## 11. Maska poškození a regiony

Maska poškození je dvourozměrné pole NumPy typu bool. Hodnota `True` označuje poškozený pixel.

Regiony poškození se vytvářejí podle masky poškození a vrstvy hran. Logika se nachází v souboru:

```
rp_restore/core/regions.py
```

Důležité prvky:

* `RegionInfo`
* `RegionMap`
* `build_region_map()`

Výběry oblastí jsou reprezentovány třídami v:

```
rp_restore/core/selection.py
```

Používají se zejména:

* `Selection`
* `SelectionSet`

Výběry se používají při nástrojích Vybrat, Laso, výplni, automatické výplni a externích algoritmech.

## 12. Undo/Redo

Systém Undo/Redo se nachází v:

```
rp_restore/core/history.py
```

Důležité třídy:

* `UndoAction`
* `GlobalUndoManager`

Každá změna pixelů se ukládá jako `UndoAction`, která obsahuje:

* popis akce
* ID vrstvy
* typ vrstvy
* ohraničující obdélník změněné oblasti
* pixely před změnou
* pixely po změně

Undo/Redo funguje globálně napříč vrstvami. Po provedení Undo nebo Redo se synchronizují také masky vyplnění poškození podle alfa kanálu vrstvy.

Při přidávání nové úpravy, která mění pixely, je potřeba vytvořit a uložit `UndoAction`, jinak změnu nebude možné vrátit.

## 13. Texturový štětec

Logika textur je v souboru:

```
rp_restore/core/texture_brush.py
```

Důležité třídy:

* `Texture`
* `TextureSettings`

Důležité funkce:

* `generate_brush_stamp()` – vytvoření stopy texturového štětce
* `generate_fill_pattern()` – vytvoření texturového vzoru pro výplň
* `deform_texture_image()` – deformace textury
* `clear_texture_cache()` – vyčištění cache při změně nastavení

Textury se ukládají do projektu a mohou být původní nebo odvozené deformované textury.

## 14. Automatická výplň

Automatická výplň malých oblastí je implementována v:

```
rp_restore/core/auto_fill.py
```

Hlavní funkce:

```
auto_fill_regions()
```

Automatická výplň pracuje s poškozenými regiony. Pro každý vybraný region vypočítá barvu z okolí a vyplní jej na aktivní vrstvě Paint. Výsledek se uloží také do historie Undo/Redo.

## 15. Hrany a zjemnění hran

Kreslení hran je implementováno v nástroji:

```
rp_restore/gui/tools/edge_tool.py
```

Výpočetní logika zjemnění přechodu přes hranu je v:

```
rp_restore/core/edge_blend.py
```

Nástroj pro zjemnění hran se nachází v:

```
rp_restore/gui/tools/edge_blend_tool.py
```

Zjemnění hrany pracuje s vybranou částí existující hrany. Aplikace vytvoří jemnější přechod mezi vyplněnými oblastmi po obou stranách hrany a následně odstraní zasaženou část hrany.

## 16. Rozmazání

Nástroj rozmazání je implementován v:

```
rp_restore/gui/tools/blend_tool.py
```

Rozmazání může používat různý zdroj podle nastavení v panelu Materiály:

* pouze aktivní vrstvu Paint
* kombinaci původního obrazu a aktivní vrstvy Paint

Nástroj upravuje jen poškozené oblasti a změny zapisuje do aktivní vrstvy Paint.

## 17. Externí algoritmy

Spouštění externích algoritmů zajišťuje soubor:

```text
rp_restore/core/algorithm_runner.py
```

Důležité třídy a datové struktury:

* `AlgorithmType` – rozlišuje realistické a texturové doplňování
* `RealisticFillMode` – rozlišuje základní a vedený režim realistického doplňování
* `AlgorithmRequest` – obsahuje vstupní obrazy, masky a parametry algoritmu
* `TextureAlgorithmParams` – obsahuje parametry texturového algoritmu
* `AlgorithmResult` – obsahuje výsledný RGBA výřez, jeho pozici a zprávy do logu
* `AlgorithmRunner` – připravuje vstupy a spouští příslušný algoritmus

### Realistické doplňování

Realistické doplňování používá klienta:

```python
painting_inpaint.remote
```

Přístupové údaje spravuje modul:

```text
rp_restore/core/remote_restoration_config.py
```

Endpoint URL a API klíč se ukládají pomocí knihovny `keyring` do systémového úložiště uživatele. API klíč se neukládá do projektu ani do běžného konfiguračního souboru. Před spuštěním klienta se údaje nastaví jako proměnné prostředí pouze pro aktuálně běžící proces.

Uživatel vybírá obdélníkové okno s maximálním rozměrem 1440 × 1440 pixelů. Pokud existuje aktivní výběr regionů, maska algoritmu je omezena na tento výběr. Jinak se použije zbývající maska poškození ve zvoleném okně.

Podporovány jsou dva režimy:

* **základní režim** umožňuje nastavit míru dogenerování parametrem `partial_noise`,
* **vedený režim** umožňuje využít ručně nakreslené vodicí čáry a je výrazně pomalejší než základní režim.

Výběr vstupního podkladu je nezávislý na režimu algoritmu. Dialog `RealisticFillDialog` nabízí tři možnosti:

* `original` – původní obraz,
* `reference` – historická kopie,
* `hybrid` – původní obraz s historickou kopií v oblastech určených původní maskou poškození.

Historická kopie je dostupná jako zdroj pouze tehdy, pokud projekt obsahuje neprázdnou referenční vrstvu.

Přípravu vstupního RGB výřezu zajišťuje `Project.realistic_input_region()`. Při použití historické kopie se průhledné pixely nahradí odpovídajícími pixely původního obrazu. Při částečné průhlednosti se oba obrazy smíchají podle alfa kanálu kopie.

Do výpočtu se nezahrnuje uživatelem nastavené krytí referenční vrstvy ani její viditelnost na plátně.

Parametr `use_composited_layers` určuje, zda se k vybranému podkladu přidají také viditelné vrstvy `PAINT` a `EDGE`. Ve výchozím stavu je v základním režimu vypnutý a ve vedeném zapnutý.

Výsledek se vloží do aktivní vrstvy typu `PAINT`, a to pouze do vybraných poškozených pixelů, které na dané vrstvě ještě nebyly vyplněny.

### Texturové doplňování

Texturový algoritmus se spouští prostřednictvím nainstalovaného balíku:

```python
texture_infill
```

Dostupné modely se zjišťují z adresáře `models` nainstalovaného balíku pomocí `importlib.resources`. Samotné generování provádí veřejná funkce:

```python
texture_infill.texture_infill.generate_infill()
```

Texturový algoritmus podporuje dva typy výstupu:

1. doplnění aktuálně vybraných poškozených oblastí,
2. vygenerování samostatné textury, která se přidá mezi materiály projektu.

Při doplňování oblasti aplikace vypočítá ohraničující obdélník výběru a algoritmu předá pouze příslušný výřez aktuálně složeného obrazu a masku vybraných, dosud nevyplněných poškozených pixelů. Výsledný RGBA výřez se vloží zpět do aktivní vrstvy malby.

Nastavení texturového algoritmu zahrnují:

* typ modelu textury
* jednu až tři barvy a sílu každé barevné vrstvy
* měřítko v osách X a Y
* hustotu v osách X a Y u podporovaných modelů
* rotaci a celkové měřítko
* neprůhledné nebo průhledné pozadí
* jas neprůhledného pozadí
* seed
* rozměry samostatně generované textury

Dialog umožňuje vygenerovat zmenšený náhled výsledku ještě před spuštěním finálního výpočtu.

Samostatně vygenerované textury se ukládají do projektu společně s parametry algoritmu, původními barvami a silami barevných vrstev. V panelu Materiály lze jejich barvy později upravit a texturu opět vygenerovat.

Knihovna `numba`, kterou používá texturový balík, zapisuje cache do zapisovatelného adresáře aplikace v uživatelském profilu, aby nebylo nutné zapisovat do instalačního adresáře.

## 18. ColorChecker korekce

Výpočetní část ColorChecker korekce je v:

```
rp_restore/core/color_correction.py
```

Dialog je v:

```
rp_restore/gui/colorchecker_dialog.py
```

Korekce se počítá jako barevná transformační matice. Tato matice se uloží do projektu a korekci lze zapínat nebo vypínat pro náhled.

Korekce se aplikuje při skládání obrazu pro zobrazení na plátně i při vytváření exportovaného výsledného obrazu a PDF reportu. Nemění však přímo pixely jednotlivých vrstev, které zůstávají uložené v původní podobě.

## 19. Zarovnání masky a historické kopie

Logika zarovnání masky je v:

```
rp_restore/core/mask_alignment.py
```

Dialog pro výběr bodů je v:

```
rp_restore/gui/mask_alignment_dialog.py
```

Uživatel vybere odpovídající body mezi původním obrazem a maskou. Z nich se vypočítá homografie a maska se transformuje na rozměry původního obrazu.

Stejný dialog `MaskAlignmentDialog` se používá také při zarovnávání historické kopie. Parametr `reference_mode=True` upravuje jeho popisky a způsob prezentace vstupních obrázků.

Kopie se zarovnává k již existujícímu původnímu obrazu v pracovním rozlišení projektu.

Homografie se vypočítá pomocí `compute_homography()` z odpovídajících bodů historické kopie a původního obrazu. K transformaci kopie se používá `warp_rgba_to_image()`, která zachovává alfa kanál a průhlednost oblastí mimo transformovaný obrázek.

Při interpolaci se používá přednásobený alfa kanál (premultiplied alpha), aby nevznikaly tmavé okraje průhledných oblastí.

Důležité funkce:

* `compute_homography()`
* `warp_mask_to_image()`
* `warp_rgba_to_image()` – transformace historické kopie se zachováním průhlednosti
* `rgb_to_damage_mask()`

## 20. PDF report

Generování PDF reportu je v:

```
rp_restore/report/pdf_report.py
```

Dialog pro vyplnění údajů je v:

```
rp_restore/report/report_dialog.py
```

Důležité prvky:

* `ReportMetadata`
* `generate_report()`

Report obsahuje původní obraz, masku poškození, výsledný obraz, zbývající masku, statistiky a náhledy vrstev.

Výsledný obraz v PDF reportu se získává pomocí `Project.get_export_image()`. Vždy tedy obsahuje původní pozadí a viditelné pracovní vrstvy, bez historické kopie.

Pokud projekt obsahuje historickou kopii, funkce `_add_layers_section()` ji přidá do samostatné části **Referenční obraz**. Kopie se tím dokumentuje, ale nezahrnuje se do výsledné rekonstrukce.

Při úpravě obsahu reportu se většina změn provádí v souboru `pdf_report.py`.

## 21. Nastavení aplikace

Nastavení jsou v:

```
rp_restore/config/settings.py
```

Třída `AppSettings` aktuálně ukládá především seznam naposledy otevřených projektů.

Nastavení přístupu ke vzdálenému realistickému doplňování se neukládají prostřednictvím `AppSettings`. Endpoint URL a API klíč spravuje modul `remote_restoration_config.py` a ukládá je pomocí knihovny `keyring` do systémového úložiště přihlašovacích údajů.

Nastavení se ukládají do:

```
~/.rp_restore/settings.json
```

Pokud se nastavení nepodaří načíst nebo uložit, aplikace chybu ignoruje a použije výchozí stav.

## 22. Typický tok práce v kódu

Příklad: uživatel použije štětec.

```
1. Uživatel vybere nástroj Štětec v MainWindow
2. MainWindow informuje ProjectController
3. ProjectController nastaví aktivní BrushTool
4. Uživatel klikne do ImageCanvasWidget
5. Canvas převede polohu kurzoru na souřadnice obrazu
6. ProjectController zavolá BrushTool.on_mouse_press()
7. BrushTool upraví pixely aktivní vrstvy Paint
8. Vytvoří se UndoAction
9. Synchronizuje se maska vyplnění poškození
10. ProjectController obnoví příslušnou část plátna
```

Podobný princip používají také ostatní nástroje.

### Načtení historické kopie

1. Uživatel vybere možnost **Načíst historickou kopii...**.
2. `MainWindow` zavolá `ProjectController.load_reference_image()`.
3. Otevře se `MaskAlignmentDialog` v referenčním režimu.
4. Z vybraných dvojic bodů se vypočítá homografie.
5. `warp_rgba_to_image()` vytvoří zarovnaný RGBA obraz.
6. Obrázek se uloží do vrstvy `REFERENCE` a plátno se obnoví.

### Vytvoření nového návrhu

1. Uživatel vybere možnost vytvoření nového návrhu.
2. `MainWindow` zpracuje volbu pracovních vrstev a případné uložení původního projektu.
3. `ProjectController.create_proposal_from_current_project()` vytvoří nezávislou kopii projektu.
4. U čistého návrhu se inicializují prázdné vrstvy `PAINT` a `EDGE` a obnoví se původní maska poškození.
5. Nový projekt se uloží do samostatného ZIP souboru a otevře se v aplikaci.

## 23. Shrnutí

Aplikace je postavena kolem třídy `Project`, která obsahuje všechna data projektu, a třídy `ProjectController`, která propojuje model s grafickým rozhraním. Jednotlivé nástroje jsou samostatné třídy reagující na události myši. Vrstvy, masky a textury jsou uloženy jako pole NumPy a celý projekt se serializuje do ZIP souboru.
