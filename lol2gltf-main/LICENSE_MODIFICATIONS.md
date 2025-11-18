# Modified lol2gltf - License and Modifications Notice

This is a modified version of lol2gltf, originally created by Crauzer.

## Original License

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

## Modifications

This modified version includes the following changes from the original:

### 1. Added glTF to Static Mesh Conversion (`gltf2static` command)
   - **File**: `src/lol2gltf/Program.cs`
   - **Method**: `ConvertGltfToStaticMesh(GltfToStaticMeshOptions options)`
   - **Description**: Added functionality to convert glTF assets to League of Legends static mesh formats (SCB/SCO)
   - **Options Class**: `GltfToStaticMeshOptions` in `Options.cs`
   - **Date**: 2025

### 2. Added glTF to Animation Extraction (`gltf2anm` command)
   - **File**: `src/lol2gltf/Program.cs`
   - **Method**: `ConvertGltfToAnimation(GltfToAnimationOptions options)`
   - **Description**: Added functionality to extract animations from glTF assets and save them as ANM files
   - **Options Class**: `GltfToAnimationOptions` in `Options.cs`
   - **Date**: 2025

### 3. Updated Command Line Parser
   - **File**: `src/lol2gltf/Program.cs`
   - **Changes**: Added `GltfToStaticMeshOptions` and `GltfToAnimationOptions` to the command line parser
   - **Date**: 2025

## Source Code Availability

The source code for this modified version is available at:
- Repository: https://github.com/ritoshark/lol-blender (or your repository URL)
- Original repository: https://github.com/Crauzer/lol2gltf

## Copyright Notice

Original work Copyright (C) [Year] Crauzer
Modifications Copyright (C) 2025 ritoshark

This modified work is licensed under the GNU General Public License v3.0 or later.

## Compliance with GPL v3

In accordance with section 5 of the GNU General Public License v3:

a) This work carries prominent notices stating that it has been modified, and giving the relevant date (2025).

b) This work carries prominent notices stating that it is released under the GNU General Public License v3.

c) The entire work, as a whole, is licensed under the GNU General Public License v3 to anyone who comes into possession of a copy.

## How to Obtain Source Code

The complete source code for this modified version is available in the repository listed above. The source code includes:
- All modified source files
- Build scripts and project files
- Documentation of changes

For the original source code, please visit: https://github.com/Crauzer/lol2gltf

