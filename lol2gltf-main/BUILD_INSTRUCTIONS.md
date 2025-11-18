# Building Modified lol2gltf

This directory contains the source code for the modified version of lol2gltf used in the LoL Blender addon.

## Prerequisites

- .NET SDK 8.0 or later
- Visual Studio 2022 or later (or any IDE that supports .NET 8.0)
- Access to the LeagueToolkit NuGet packages (these should be available via NuGet)

## Building

### Using Visual Studio

1. Open `src/lol2gltf.sln` in Visual Studio
2. Restore NuGet packages (should happen automatically)
3. Build the solution (Build → Build Solution, or Ctrl+Shift+B)
4. The executable will be in `src/lol2gltf/bin/Release/net8.0/win-x64/publish/` (or Debug for debug builds)

### Using Command Line

```bash
cd src/lol2gltf
dotnet restore
dotnet build -c Release
dotnet publish -c Release -r win-x64 --self-contained false
```

The executable will be in `bin/Release/net8.0/win-x64/publish/lol2gltf.exe`

## Modifications

This version includes the following modifications from the original:

1. **gltf2static command** - Converts glTF to League of Legends static mesh formats (SCB/SCO)
2. **gltf2anm command** - Extracts animations from glTF files to ANM format

See [MODIFICATIONS.txt](MODIFICATIONS.txt) and [LICENSE_MODIFICATIONS.md](LICENSE_MODIFICATIONS.md) for detailed information about the changes.

## License

This modified work is licensed under the GNU General Public License v3.0 or later.

- Original work Copyright (C) [Year] Crauzer
- Modifications Copyright (C) 2025 ritoshark

See [LICENSE](LICENSE) for the full license text.

## Original Repository

Original lol2gltf: https://github.com/Crauzer/lol2gltf

