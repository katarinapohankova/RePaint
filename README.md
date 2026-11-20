# RePaint

**Language / Jazyk:** [English](README.md) | [Čeština](README.cs.md) | [Slovenčina](README.sk.md)

RePaint is an application for digitally reconstructing damaged areas of paintings. It lets users work with an original image, a damage mask, multiple layers, manual editing tools, and external algorithms for filling in missing areas.

The application was developed as part of a bachelor's thesis in cooperation with the National Gallery Prague. It is primarily intended for preparing and comparing proposed painting restoration treatments.

## Features

The application supports:

* creating a project from an image and a damage mask
* aligning a damage mask using corresponding points
* loading and aligning a historical copy of a painting
* using a historical copy as a reference when planning a reconstruction
* working with layers
* manually filling damaged areas with color or texture
* filling damaged regions
* selecting damaged areas by clicking or using the lasso tool
* drawing boundaries to divide damaged areas into smaller regions
* smoothing transitions between filled regions
* smudging reconstructed areas
* automatically filling small damaged regions
* ColorChecker color correction
* external realistic and texture-based inpainting
* using a historical copy as input for realistic inpainting
* Undo/Redo
* saving and opening projects in `.zip` format
* creating independent reconstruction proposals from an existing project
* exporting the resulting image
* exporting a PDF report

## Project structure

Basic repository structure:

```
.
├── docs/
│   ├── user_documentation.md
│   ├── user_documentation.cs.md
│   ├── user_documentation.en.md
│   ├── developer_documentation.md
│   ├── developer_documentation.cs.md
│   └── developer_documentation.en.md
├── rp_restore_app/
│   ├── app.py
│   ├── RePaint.spec
│   ├── requirements.txt
│   ├── requirements-lock.txt
│   ├── packaging/
│   │   ├── RePaint.ico
│   │   ├── RePaint.iss
│   │   └── version_info.txt
│   └── rp_restore/
│       ├── config/
│       ├── core/
│       ├── gui/
│       ├── io/
│       ├── report/
│       └── resources/
├── COPYRIGHT.md
├── README.cs.md
├── README.sk.md
└── README.md
```

The `rp_restore_app` directory contains the application itself. Its main Python package is `rp_restore`.

The `docs` directory contains the documentation:

* `user_documentation.md` – user documentation
* `developer_documentation.md` – developer documentation

## Installation and launch

The application can be used in two ways: by installing it with the provided installer or by running it directly from source code.

### Installation with the installer

For regular use, download:

```text
RePaint-Setup-1.1.0.exe
```

The latest version is available under
[GitHub Releases](https://github.com/katarinapohankova/RePaint/releases/latest).

The installer is intended for 64-bit Windows. Running it installs the application into the user's directory, creates a Start menu shortcut, and optionally creates a desktop shortcut.

The installed version already includes Python, the required libraries, and the local texture inpainting algorithm. You do not need to install Python, Git, or other dependencies separately on the target computer.

Realistic inpainting uses a remote service. It requires an internet connection and a valid API key, which you enter on first use and which is subsequently stored in the operating system's credential store.

### Running from source code

Python 3.13 and Git are required. Clone the repository and navigate to the application directory:

```powershell
git clone https://github.com/katarinapohankova/RePaint.git
cd RePaint\rp_restore_app
```

Create and activate a virtual environment:

```powershell
python3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

After activating the environment, install the dependencies using the `python` interpreter from that environment:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Start the application:

```powershell
python app.py
```

Installing from source may require access to the external package repositories specified in `requirements.txt`.
The realistic inpainting client is installed from a private GitHub repository, so appropriate access permissions are required. Regular users are advised to use the prepared Windows installer.

## Usage

After launching the application, you can create a new project or open an existing one.

A new project starts with the original image. You may also add a damage mask, which defines the areas to be reconstructed. When a mask is provided, the application allows it to be aligned with the image using corresponding points.

You can also load a historical copy of the painting into an existing project. It is aligned with the original image and can serve as a reference when reconstructing damaged areas, including when using the realistic inpainting algorithm.

An independent reconstruction proposal can be created from an existing project. You can choose whether to keep the current painting and edge layers or start with empty working layers.

For more detailed instructions, see the [user documentation](docs/user_documentation.en.md).

## Developer documentation

A summary of the application's internal structure, main modules, data model, and tools is available in the [developer documentation](docs/developer_documentation.en.md).

## Saving projects

Projects are saved as `.zip` files containing, in particular:

* project metadata
* the original image
* layers
* masks
* the color palette
* textures
* settings needed to continue working

If a project contains a historical copy, it is stored alongside the other layers, including its transparency and settings. Its alignment is preserved when creating another proposal. Each proposal is saved as a separate project.

An exported result always uses the original image together with the visible working layers. The historical copy is for reference only and is not included in the reconstructed result. It may be included separately in the PDF report.

A saved project can be opened again later to continue editing.

## External algorithms

The application supports two external algorithms:

* **Realistic inpainting** – uses the `painting_inpaint.remote` client and a remote service; the input can be the original image, the historical copy, or a combination based on the damage mask; requires an internet connection, an endpoint URL, and an API key
* **Texture inpainting** – uses the locally installed `texture_infill` package; it can fill a selected damaged area or generate a separate texture and add it to the project's materials

The required packages and models are already included when using the installed version of the application.
