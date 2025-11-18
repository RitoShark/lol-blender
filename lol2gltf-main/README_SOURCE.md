# Modified lol2gltf Source Code

This directory contains the **source code** for the modified version of lol2gltf that is bundled with the LoL Blender addon.

## Why is this here?

This source code is provided to comply with the **GNU General Public License v3.0** (GPL v3) requirements. When distributing GPL-licensed software (like the modified lol2gltf.exe), the license requires that the corresponding source code be made available.

## What's included?

- **Source files**: `src/lol2gltf/Program.cs` and `src/lol2gltf/Options.cs` (modified)
- **Project files**: `src/lol2gltf/lol2gltf.csproj` and `src/lol2gltf.sln`
- **License documentation**: `LICENSE`, `LICENSE_MODIFICATIONS.md`, `MODIFICATIONS.txt`
- **Build instructions**: `BUILD_INSTRUCTIONS.md`

## What's NOT included?

- Build artifacts (bin/, obj/, publish/ directories)
- Compiled executables (.exe, .dll, .pdb files)
- NuGet package cache

These are excluded via `.gitignore` as they can be regenerated from the source code.

## Building

See [BUILD_INSTRUCTIONS.md](BUILD_INSTRUCTIONS.md) for detailed build instructions.

## Modifications

This version includes modifications to add:
- `gltf2static` command (glTF to SCB/SCO conversion)
- `gltf2anm` command (glTF to ANM animation extraction)

See [MODIFICATIONS.txt](MODIFICATIONS.txt) for details.

## License

- Original work Copyright (C) [Year] Crauzer
- Modifications Copyright (C) 2025 ritoshark
- Licensed under GNU General Public License v3.0 or later

Original repository: https://github.com/Crauzer/lol2gltf

