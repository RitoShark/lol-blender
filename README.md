# LoL Blender - Blender Addon

A comprehensive Blender addon for importing and exporting League of Legends game files. Supports character models, skeletons, animations, and static objects.

## Features

### Supported File Formats

- **SKL/SKN** - Character skeletons and skinned meshes
- **ANM** - Character animations
- **SCB** - Static objects (Simple Static Mesh)
- **SCO** - Static objects with pivot points

### Key Capabilities

✅ Import League of Legends character models with proper rigging  
✅ Export custom models back to game format  
✅ Import and export animations  
✅ Automatic bone weight limiting (max 4 influences per vertex)  (NEEDS TESTING NOT TESTED)
✅ UV corner snapping tools for texture alignment  
✅ Drag-and-drop file support  
✅ Preserves bind matrices and skeleton hierarchy  

## Installation

### Requirements

- **Blender 4.0 or newer** (tested with Blender 4.2)
- **Windows** (currently only Windows is fully supported)

### Step 1: Download

1. Go to the [Releases](https://github.com/RitoShark/lol-blender/releases) page
2. Download the latest `lol-blender.zip`
3. **Do NOT unzip the file** - Blender can install it directly

### Step 2: Install in Blender

1. Open Blender
2. Go to `Edit` → `Preferences` → `Add-ons`
3. Click `Install...` button at the top
4. Navigate to the downloaded `lol-blender.zip`
5. Click `Install Add-on`
6. Enable the addon by checking the checkbox next to "Import-Export: LoL League Tools"

### Step 3: Verify Installation

After enabling the addon, you should see:
- **File → Import** menu contains LoL import options
- **File → Export** menu contains LoL export options
- **3D Viewport sidebar** (press `N`) has a "LoL Tools" tab

### Step 4: Optional - Download lol2gltf (Recommended)

For best import quality, download the lol2gltf converter:

1. Go to https://github.com/Crauzer/lol2gltf/releases
2. Download `lol2gltf.exe`
3. Place it in Blender's addon folder: `%APPDATA%\Blender Foundation\Blender\[version]\scripts\addons\lol_blender\lol2gltf-main\`
4. Restart Blender

**Note:** The addon works without lol2gltf using a fallback method, but lol2gltf provides more reliable conversions.

## Usage

### Importing Character Models (SKL + SKN)

1. Go to `File` → `Import` → `LoL SKN+SKL`
2. Navigate to your League of Legends game files
3. Select a `.skn` file (the corresponding `.skl` must be in the same folder)
4. Adjust the scale factor if needed (default: 0.01 = 1%)
5. Click `Import`

### Importing Animations (ANM)

1. First import the character model (SKL+SKN)
2. Go to `File` → `Import` → `LoL ANM Animation`
3. Select an `.anm` file
4. The animation will be applied to the existing armature

### Exporting Models

1. Select your mesh and armature in the 3D viewport
2. Go to `File` → `Export` → `LoL SKN+SKL`
3. Choose the output location and filename
4. Click `Export`

**Important:** Your mesh must have:
- An armature modifier
- Vertex groups matching bone names
- Maximum 4 bone influences per vertex (use "Limit to 4 Influences" tool)

### Exporting Animations

1. Select the armature with the animation
2. Go to `File` → `Export` → `LoL ANM Animation`
3. Choose output location
4. Click `Export`

### Using the LoL Blender Tools Panele

Open the 3D Viewport sidebar (press `N`) and find the **LoL Tools** tab.

Available tools:
- **Import/Export buttons** for quick access
- **Limit to 4 Influences** - Automatically reduces bone weights (required for export)
- **UV Corners** panel (in UV Editor) - Snap UV vertices to corners

### UV Corner Tools

In the **UV Editor**, open the sidebar (`N` key) and find the **UV Corners** panel.

1. Select UV vertices you want to snap
2. Click one of the corner buttons to snap selected UVs to that corner:
   - ◸ Top Left (0, 1)
   - ◹ Top Right (1, 1)
   - ◺ Bottom Left (0, 0)
   - ◿ Bottom Right (1, 0)

## Tips & Tricks

### Model Scale

League of Legends uses a different scale than Blender. The default import scale (0.01) makes models 1% of their original size, which is usually correct for Blender's viewport.

### Bone Influences

League of Legends requires maximum 4 bone influences per vertex. Before exporting:
1. Select your mesh
2. Open LoL Tools panel
3. Click "Limit to 4 Influences"

### Animation Frame Rate

LoL animations typically use 30 FPS. Make sure your Blender scene is set to 30 FPS before exporting animations:
- Go to `Output Properties` → `Frame Rate` → Set to 30 FPS

### File Organization

Keep `.skl` and `.skn` files in the same folder with matching names:
```
champion_base.skl
champion_base.skn
champion_run.anm
champion_attack.anm
```

## Troubleshooting

### Import fails with "glTF conversion failed"

**Solution:** The addon includes bundled dependencies, but if you still see errors:
1. Check the Blender console (Window → Toggle System Console)
2. Make sure both `.skl` and `.skn` files exist in the same folder
3. Try re-installing the addon

### Export fails with "Too many influences"

**Solution:** Use the "Limit to 4 Influences" tool before exporting.

### Animations look wrong after import

**Solution:** 
1. Make sure you imported the SKL+SKN first
2. Check that bone names match between model and animation
3. Verify frame rate is set to 30 FPS

### "lol2gltf.exe not found" warning

**Effect:** Import still works using fallback method, but may be slower.

**To fix (optional):**
1. Download lol2gltf from: https://github.com/Crauzer/lol2gltf/releases
2. Place `lol2gltf.exe` in the addon's `lol2gltf-main` folder
3. Restart Blender

## Technical Details

### How It Works

The addon uses a bridge architecture:

```
LoL Files (SKL/SKN/ANM) → glTF → Blender Scene
Blender Scene → glTF → LoL Files (SKL/SKN/ANM)
```

- **pyritofile** - Reads and writes League of Legends binary formats
- **pygltflib** - Creates glTF intermediate format
- **lol2gltf** - (Optional) External tool for more reliable conversion
- **Blender's glTF importer** - Brings data into Blender

### File Storage

The addon stores temporary files in:
```
%TEMP%\lol_league_tools\
```

These can be safely deleted when Blender is closed.

## Credits

- **pyritofile** - For League of Legends file format support
- **lol2gltf** by Crauzer - For reliable SKL/SKN conversion
- **LoL Blender Contributors** - For development and testing

## License

This project is released under the GNU General Public License v3.0 or later. See [LICENSE](LICENSE) file for details.

**Note:** This project is licensed under GPL v3 as required by the copyleft license of the bundled modified lol2gltf. See the [LICENSE](LICENSE) file for full license text and third-party component licenses.

## Support & Contributing

- **Issues:** Report bugs on the [GitHub Issues](https://github.com/RitoShark/lol-blender/issues) page
- **Discussions:** Ask questions in [GitHub Discussions](https://github.com/RitoShark/lol-blender/discussions)
- **Contributing:** Pull requests are welcome!

---

**Note:** This addon is not affiliated with or endorsed by Riot Games. League of Legends and Riot Games are trademarks or registered trademarks of Riot Games, Inc.
