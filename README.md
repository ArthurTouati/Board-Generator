# KiCad 10 RF Shielding & Outline Generator Plugin (v2)

This Action Plugin automates the generation of a custom rectangular board outline with rounded corners, a continuous shielding via fence that detours around corner mounting holes, and isolated chassis mounting regions with custom stitching rings.

## Features
- **Board Outline Generation:** Creates a custom rectangular outline with rounded corner fillets of radius $R$ on the `Edge.Cuts` layer.
- **Corner Mounting Holes:** Places Non-Plated Through Holes (NPTH) or drawn silkscreen crosses at customizable offsets from corners.
- **Copper Isolation Zones:** Generates circular copper zones on `F.Cu` and `B.Cu` layers with high priority (priority 2), connected to unique nets (`CHASSIS_1` to `CHASSIS_4`).
- **Stitching Rings:** Places 8 stitching vias concentric with each mounting hole, connected to the respective `CHASSIS_i` net.
- **RF Shielding via Fence:** Places GND shielding vias along the setback perimeter.
- **Corner Detours:** Automatically bends the shielding via path inwards around the active mounting zones to maintain complete RF isolation from the chassis net.
- **Dynamic UI Calculations:** A native wxPython GUI that instantly computes the guided wavelength $\lambda$ and recommended via spacing $s$ when changing Max Frequency ($f_{\text{max}}$) or Dielectric Constant ($\epsilon_r$).
- **Strict Defensive Validation:** Validates physical layout parameters and warns/halts if inputs are invalid or detours overlap.

## Installation

1. Copy the entire `Board Generator` directory.
2. Place the directory into your KiCad plugins folder based on your operating system:
   - **Windows:** `%USERPROFILE%\Documents\KiCad\10.0\scripting\plugins`
   - **Linux:** `~/.local/share/kicad/10.0/scripting/plugins`
   - **macOS:** `~/Documents/KiCad/10.0/scripting/plugins`
3. Restart KiCad, or open the PCB Editor and click `Tools > External Plugins > Refresh`.

The plugin will now appear in the `Tools > External Plugins` menu and on your Action Plugins toolbar.

## Usage
1. Click the "Board Outline & Shielding Generator" icon on the toolbar or select it from `Tools > External Plugins`.
2. Configure board dimensions, mounting holes, and shielding parameters.
3. Observe live calculations for wavelength and via spacing.
4. Click **Generate** to draw the layout and components.

## Compatibility
Built for KiCad 10 Python API (`pcbnew`).
