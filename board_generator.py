#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
KiCad 10 RF Shielding & Outline Generator Plugin (v2)
------------------------------------------------------
An Action Plugin that automates the generation of:
1. A custom rectangular board outline with rounded corners.
2. A continuous GND via shielding fence that detours around active mounting holes.
3. Isolated chassis mounting regions (CHASSIS_1 to CHASSIS_4) with stitching vias.
"""

import os
import math
import pcbnew
import wx

class LineSegment:
    def __init__(self, start_pt, end_pt):
        self.start_pt = start_pt
        self.end_pt = end_pt
        dx = end_pt.x - start_pt.x
        dy = end_pt.y - start_pt.y
        self.length = math.sqrt(dx*dx + dy*dy)
        
    def point_at(self, u):
        x = self.start_pt.x + u * (self.end_pt.x - self.start_pt.x)
        y = self.start_pt.y + u * (self.end_pt.y - self.start_pt.y)
        return pcbnew.VECTOR2I(int(x), int(y))

class ArcSegment:
    def __init__(self, center, radius, start_angle, end_angle):
        self.center = center
        self.radius = radius
        self.start_angle = start_angle
        self.end_angle = end_angle
        
        diff = end_angle - start_angle
        while diff > math.pi:
            diff -= 2 * math.pi
        while diff < -math.pi:
            diff += 2 * math.pi
        self.diff = diff
        self.length = radius * abs(diff)
        
    def point_at(self, u):
        angle = self.start_angle + u * self.diff
        x = self.center.x + self.radius * math.cos(angle)
        y = self.center.y + self.radius * math.sin(angle)
        return pcbnew.VECTOR2I(int(x), int(y))


class BoardGeneratorDialog(wx.Dialog):
    def __init__(self, parent):
        super(BoardGeneratorDialog, self).__init__(parent, title="RF Shielding & Outline Generator", size=(520, 720))
        
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # --- TITLE ---
        title_lbl = wx.StaticText(panel, label="RF Shielding & Outline Generator (v2)")
        title_lbl.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        main_sizer.Add(title_lbl, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 15)
        
        # --- SCROLLABLE CONTAINER FOR SETTINGS ---
        scroll_win = wx.ScrolledWindow(panel, style=wx.VSCROLL)
        scroll_win.SetScrollRate(0, 20)
        scroll_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # 1. BOARD OUTLINE GROUP
        box_outline = wx.StaticBox(scroll_win, label="Board Outline Settings")
        outline_sizer = wx.StaticBoxSizer(box_outline, wx.VERTICAL)
        grid_outline = wx.FlexGridSizer(3, 2, 8, 10)
        grid_outline.AddGrowableCol(1, 1)
        
        grid_outline.Add(wx.StaticText(scroll_win, label="Board Width (W, mm):"))
        self.tc_width = wx.TextCtrl(scroll_win, value="100.0")
        grid_outline.Add(self.tc_width, 1, wx.EXPAND)
        
        grid_outline.Add(wx.StaticText(scroll_win, label="Board Height (H, mm):"))
        self.tc_height = wx.TextCtrl(scroll_win, value="80.0")
        grid_outline.Add(self.tc_height, 1, wx.EXPAND)
        
        grid_outline.Add(wx.StaticText(scroll_win, label="Corner Radius (R, mm):"))
        self.tc_radius = wx.TextCtrl(scroll_win, value="5.0")
        grid_outline.Add(self.tc_radius, 1, wx.EXPAND)
        
        outline_sizer.Add(grid_outline, 1, wx.EXPAND | wx.ALL, 10)
        scroll_sizer.Add(outline_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        
        # 2. MOUNTING CORNERS GROUP
        box_corners = wx.StaticBox(scroll_win, label="Mounting Corner & Chassis Settings")
        corners_sizer = wx.StaticBoxSizer(box_corners, wx.VERTICAL)
        
        corners_sizer.Add(wx.StaticText(scroll_win, label="Enable corners:"), 0, wx.LEFT | wx.TOP, 5)
        cb_grid = wx.GridSizer(2, 2, 5, 5)
        self.cb_tl = wx.CheckBox(scroll_win, label="Top-Left (CHASSIS_1)")
        self.cb_tl.SetValue(True)
        self.cb_tr = wx.CheckBox(scroll_win, label="Top-Right (CHASSIS_2)")
        self.cb_tr.SetValue(True)
        self.cb_br = wx.CheckBox(scroll_win, label="Bottom-Right (CHASSIS_3)")
        self.cb_br.SetValue(True)
        self.cb_bl = wx.CheckBox(scroll_win, label="Bottom-Left (CHASSIS_4)")
        self.cb_bl.SetValue(True)
        cb_grid.Add(self.cb_tl)
        cb_grid.Add(self.cb_tr)
        cb_grid.Add(self.cb_br)
        cb_grid.Add(self.cb_bl)
        corners_sizer.Add(cb_grid, 0, wx.EXPAND | wx.ALL, 8)
        
        grid_corners = wx.FlexGridSizer(4, 2, 8, 10)
        grid_corners.AddGrowableCol(1, 1)
        
        grid_corners.Add(wx.StaticText(scroll_win, label="Mounting Hole Offset (D_offset, mm):"))
        self.tc_offset = wx.TextCtrl(scroll_win, value="5.0")
        grid_corners.Add(self.tc_offset, 1, wx.EXPAND)
        
        grid_corners.Add(wx.StaticText(scroll_win, label="Hole Diameter (D_hole, mm):"))
        self.tc_hole_dia = wx.TextCtrl(scroll_win, value="3.2")
        grid_corners.Add(self.tc_hole_dia, 1, wx.EXPAND)
        
        grid_corners.Add(wx.StaticText(scroll_win, label="Chassis Pad Diameter (D_chassis, mm):"))
        self.tc_chassis_dia = wx.TextCtrl(scroll_win, value="7.0")
        grid_corners.Add(self.tc_chassis_dia, 1, wx.EXPAND)
        
        grid_corners.Add(wx.StaticText(scroll_win, label="Silkscreen Cross Size (mm):"))
        self.tc_cross_size = wx.TextCtrl(scroll_win, value="2.0")
        grid_corners.Add(self.tc_cross_size, 1, wx.EXPAND)
        
        corners_sizer.Add(grid_corners, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        
        # Center marking option
        corners_sizer.Add(wx.StaticText(scroll_win, label="Mounting Center Mark Type:"), 0, wx.LEFT | wx.TOP, 10)
        self.rb_npth = wx.RadioButton(scroll_win, label="Physical NPTH Drill Hole", style=wx.RB_GROUP)
        self.rb_cross = wx.RadioButton(scroll_win, label="Silkscreen Cross on F_SilkS")
        self.rb_npth.SetValue(True)
        corners_sizer.Add(self.rb_npth, 0, wx.LEFT | wx.TOP, 5)
        corners_sizer.Add(self.rb_cross, 0, wx.LEFT | wx.TOP | wx.BOTTOM, 5)
        
        scroll_sizer.Add(corners_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        
        # 3. RF VIA SHIELDING GROUP
        box_shield = wx.StaticBox(scroll_win, label="RF Via Shielding Settings")
        shield_sizer = wx.StaticBoxSizer(box_shield, wx.VERTICAL)
        grid_shield = wx.FlexGridSizer(7, 2, 8, 10)
        grid_shield.AddGrowableCol(1, 1)
        
        grid_shield.Add(wx.StaticText(scroll_win, label="Max Frequency (f_max, GHz):"))
        self.tc_fmax = wx.TextCtrl(scroll_win, value="6.0")
        grid_shield.Add(self.tc_fmax, 1, wx.EXPAND)
        
        grid_shield.Add(wx.StaticText(scroll_win, label="Dielectric Constant (er):"))
        self.tc_er = wx.TextCtrl(scroll_win, value="4.4")
        grid_shield.Add(self.tc_er, 1, wx.EXPAND)
        
        grid_shield.Add(wx.StaticText(scroll_win, label="Via Spacing Factor (N_factor):"))
        self.tc_nfactor = wx.TextCtrl(scroll_win, value="10.0")
        grid_shield.Add(self.tc_nfactor, 1, wx.EXPAND)
        
        grid_shield.Add(wx.StaticText(scroll_win, label="Setback Distance (D_setback, mm):"))
        self.tc_setback = wx.TextCtrl(scroll_win, value="1.0")
        grid_shield.Add(self.tc_setback, 1, wx.EXPAND)
        
        grid_shield.Add(wx.StaticText(scroll_win, label="GND-Chassis Net Clearance (mm):"))
        self.tc_clearance = wx.TextCtrl(scroll_win, value="1.0")
        grid_shield.Add(self.tc_clearance, 1, wx.EXPAND)
        
        grid_shield.Add(wx.StaticText(scroll_win, label="Via Outer Diameter (mm):"))
        self.tc_via_dia = wx.TextCtrl(scroll_win, value="0.6")
        grid_shield.Add(self.tc_via_dia, 1, wx.EXPAND)
        
        grid_shield.Add(wx.StaticText(scroll_win, label="Via Drill Diameter (mm):"))
        self.tc_via_drill = wx.TextCtrl(scroll_win, value="0.3")
        grid_shield.Add(self.tc_via_drill, 1, wx.EXPAND)
        
        shield_sizer.Add(grid_shield, 1, wx.EXPAND | wx.ALL, 10)
        scroll_sizer.Add(shield_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        
        # 4. DYNAMIC CALCULATIONS GROUP
        box_calc = wx.StaticBox(scroll_win, label="Calculated RF Parameters (Dynamic)")
        calc_sizer = wx.StaticBoxSizer(box_calc, wx.VERTICAL)
        
        self.lbl_lambda = wx.StaticText(scroll_win, label="Guided Wavelength (\u03bb): 23.82 mm")
        self.lbl_lambda.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.lbl_spacing = wx.StaticText(scroll_win, label="Recommended Via Spacing (s): 2.38 mm")
        self.lbl_spacing.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        
        calc_sizer.Add(self.lbl_lambda, 0, wx.ALL, 5)
        calc_sizer.Add(self.lbl_spacing, 0, wx.ALL, 5)
        scroll_sizer.Add(calc_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        
        scroll_win.SetSizer(scroll_sizer)
        main_sizer.Add(scroll_win, 1, wx.EXPAND)
        
        # --- DIALOG BUTTONS ---
        btn_box = wx.BoxSizer(wx.HORIZONTAL)
        btn_ok = wx.Button(panel, label="Generate")
        btn_cancel = wx.Button(panel, wx.ID_CANCEL, label="Cancel")
        btn_box.Add(btn_ok)
        btn_box.Add(btn_cancel, flag=wx.LEFT, border=10)
        main_sizer.Add(btn_box, 0, wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, 15)
        
        panel.SetSizer(main_sizer)
        
        # Bind text update handlers for real-time calculations
        self.tc_fmax.Bind(wx.EVT_TEXT, self.UpdateCalculations)
        self.tc_er.Bind(wx.EVT_TEXT, self.UpdateCalculations)
        self.tc_nfactor.Bind(wx.EVT_TEXT, self.UpdateCalculations)
        
        # Bind OK button generator
        btn_ok.Bind(wx.EVT_BUTTON, self.OnGenerate)
        
        # Initialize calculations
        self.UpdateCalculations()
        
    def UpdateCalculations(self, event=None):
        try:
            fmax = float(self.tc_fmax.GetValue())
            er = float(self.tc_er.GetValue())
            nfactor = float(self.tc_nfactor.GetValue())
            if fmax <= 0 or er <= 0 or nfactor <= 0:
                raise ValueError
            
            # c = 299.792458 mm/ns
            v = 299.792458 / math.sqrt(er)
            wavelength = v / fmax
            spacing = wavelength / nfactor
            self.lbl_lambda.SetLabel(f"Guided Wavelength (\u03bb): {wavelength:.2f} mm")
            self.lbl_spacing.SetLabel(f"Recommended Via Spacing (s): {spacing:.2f} mm")
        except ValueError:
            self.lbl_lambda.SetLabel("Guided Wavelength (\u03bb): Invalid input")
            self.lbl_spacing.SetLabel("Recommended Via Spacing (s): Invalid input")
            
    def OnGenerate(self, event):
        if self.ValidateAndCollectInputs():
            self.EndModal(wx.ID_OK)
            
    def ValidateAndCollectInputs(self):
        try:
            self.width = float(self.tc_width.GetValue())
            self.height = float(self.tc_height.GetValue())
            self.corner_radius = float(self.tc_radius.GetValue())
            
            self.offset = float(self.tc_offset.GetValue())
            self.hole_dia = float(self.tc_hole_dia.GetValue())
            self.chassis_dia = float(self.tc_chassis_dia.GetValue())
            self.cross_size = float(self.tc_cross_size.GetValue())
            
            self.fmax = float(self.tc_fmax.GetValue())
            self.er = float(self.tc_er.GetValue())
            self.nfactor = float(self.tc_nfactor.GetValue())
            self.setback = float(self.tc_setback.GetValue())
            self.clearance = float(self.tc_clearance.GetValue())
            self.via_dia = float(self.tc_via_dia.GetValue())
            self.via_drill = float(self.tc_via_drill.GetValue())
            
            self.use_npth = self.rb_npth.GetValue()
            self.enable_tl = self.cb_tl.IsChecked()
            self.enable_tr = self.cb_tr.IsChecked()
            self.enable_br = self.cb_br.IsChecked()
            self.enable_bl = self.cb_bl.IsChecked()
        except ValueError:
            wx.MessageBox("All inputs must be valid numeric values.", "Input Error", wx.OK | wx.ICON_ERROR)
            return False

        # Defensive boundaries and validation checks
        if self.width <= 0 or self.height <= 0:
            wx.MessageBox("Board Width and Height must be positive.", "Input Error", wx.OK | wx.ICON_ERROR)
            return False
            
        if self.corner_radius < 0:
            wx.MessageBox("Corner Radius must be non-negative.", "Input Error", wx.OK | wx.ICON_ERROR)
            return False
            
        if self.corner_radius * 2 > min(self.width, self.height):
            wx.MessageBox("Corner Radius is too large for the board dimensions.", "Input Error", wx.OK | wx.ICON_ERROR)
            return False

        if self.hole_dia <= 0 or self.chassis_dia <= 0 or self.offset <= 0:
            wx.MessageBox("Hole size, Chassis size, and Offset must be positive.", "Input Error", wx.OK | wx.ICON_ERROR)
            return False

        if self.chassis_dia <= self.hole_dia:
            wx.MessageBox("Chassis Zone Diameter must be greater than Mounting Hole Diameter.", "Input Error", wx.OK | wx.ICON_ERROR)
            return False

        if self.setback <= 0 or self.clearance <= 0:
            wx.MessageBox("Setback and Net Clearance must be positive.", "Input Error", wx.OK | wx.ICON_ERROR)
            return False

        if self.via_dia <= 0 or self.via_drill <= 0 or self.via_drill >= self.via_dia:
            wx.MessageBox("Via diameter and drill must be positive, and drill must be smaller than diameter.", "Input Error", wx.OK | wx.ICON_ERROR)
            return False

        if not self.use_npth and self.cross_size <= 0:
            wx.MessageBox("Silkscreen cross size must be positive.", "Input Error", wx.OK | wx.ICON_ERROR)
            return False

        if self.offset <= self.setback:
            wx.MessageBox("Mounting Hole Offset (D_offset) must be greater than Via Setback (D_setback).", "Input Error", wx.OK | wx.ICON_ERROR)
            return False

        # Detour geometry check for rectangular detour
        r_detour = self.chassis_dia / 2.0 + self.clearance
        if (self.offset + r_detour) >= self.width / 2.0:
            wx.MessageBox(
                f"Horizontal detours overlap!\n"
                f"Detour reach ({self.offset + r_detour:.2f} mm) exceeds half of board width ({self.width / 2.0:.2f} mm).\n"
                f"Please reduce D_chassis, D_clearance, or D_offset.",
                "Geometry Error", wx.OK | wx.ICON_ERROR
            )
            return False

        if (self.offset + r_detour) >= self.height / 2.0:
            wx.MessageBox(
                f"Vertical detours overlap!\n"
                f"Detour reach ({self.offset + r_detour:.2f} mm) exceeds half of board height ({self.height / 2.0:.2f} mm).\n"
                f"Please reduce D_chassis, D_clearance, or D_offset.",
                "Geometry Error", wx.OK | wx.ICON_ERROR
            )
            return False

        return True


class BoardGeneratorPlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "Board Outline & Shielding Generator"
        self.category = "Generate board and shielding elements"
        self.description = "Generates rectangular board outline with rounded corners and custom via shielding fence with detours."
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(os.path.dirname(__file__), 'icon.png')

    def Run(self):
        log_path = os.path.join(os.path.dirname(__file__), "debug_generator.log")
        try:
            if os.path.exists(log_path):
                os.remove(log_path)
        except Exception:
            pass

        def log_debug(msg):
            try:
                with open(log_path, "a") as f:
                    f.write(msg + "\n")
                    f.flush()
            except Exception:
                pass

        log_debug("--- START RUN ---")
        board = pcbnew.GetBoard()
        if not board:
            log_debug("No board found")
            return
            
        log_debug("Finding pcb_frame...")
        pcb_frame = None
        for win in wx.GetTopLevelWindows():
            if win.GetTitle().lower().startswith('pcb editor') or win.GetTitle().lower().startswith('pcbnew'):
                pcb_frame = win
                break
                
        log_debug("Instantiating BoardGeneratorDialog...")
        dlg = BoardGeneratorDialog(pcb_frame)
        log_debug("Showing dialog modal...")
        res = dlg.ShowModal()
        log_debug(f"Dialog result: {res}")
        
        if res == wx.ID_OK:
            log_debug("Generating PCB components...")
            self.generate_pcb(board, dlg, log_debug)
            log_debug("PCB components generated successfully.")
            
            # Commented out to isolate canvas refresh crashes
            # if hasattr(pcbnew, "UpdateUserInterface"):
            #     log_debug("Calling UpdateUserInterface...")
            #     try:
            #         pcbnew.UpdateUserInterface()
            #         log_debug("UpdateUserInterface called.")
            #     except Exception as ex:
            #         log_debug(f"UpdateUserInterface failed: {ex}")
            # 
            # log_debug("Scheduling Refresh via wx.CallAfter...")
            # try:
            #         wx.CallAfter(pcbnew.Refresh)
            #         log_debug("Refresh scheduled via wx.CallAfter.")
            # except Exception as ex:
            #         log_debug(f"wx.CallAfter(Refresh) failed: {ex}")
            #         try:
            #             pcbnew.Refresh()
            #             log_debug("Refresh called directly.")
            #         except Exception as ex2:
            #             log_debug(f"Direct Refresh failed: {ex2}")
            log_debug("Skipping UI refresh calls.")
            
        log_debug("Destroying dialog...")
        dlg.Destroy()
        log_debug("Dialog destroyed.")

    def generate_pcb(self, board, p, log_debug=None):
        if not log_debug:
            def log_debug(msg):
                pass

        log_debug("generate_pcb: 1. Net Initialization...")
        gnd_net = self.get_or_create_net(board, "GND")
        log_debug(f"GND net resolved: {gnd_net}")
        chassis_nets = [
            self.get_or_create_net(board, "CHASSIS_1"),
            self.get_or_create_net(board, "CHASSIS_2"),
            self.get_or_create_net(board, "CHASSIS_3"),
            self.get_or_create_net(board, "CHASSIS_4")
        ]
        log_debug(f"Chassis nets resolved: {chassis_nets}")

        # 2. Board boundaries
        x_lim = p.width / 2.0
        y_lim = p.height / 2.0
        edge_cuts = board.GetLayerID("Edge.Cuts")
        f_silks = board.GetLayerID("F.SilkS")
        f_cu = board.GetLayerID("F.Cu")
        b_cu = board.GetLayerID("B.Cu")
        outline_width = int(pcbnew.FromMM(0.15))

        # 3. Draw Outer Board Outline (centered at 0, 0)
        self.draw_board_outline(board, x_lim, y_lim, p.corner_radius, edge_cuts, outline_width)

        # 4. Process corners (TL, TR, BR, BL)
        # Signs for corners:
        # TL = (-1, -1), TR = (1, -1), BR = (1, 1), BL = (-1, 1)
        corners = [
            {"name": "TL", "sx": -1, "sy": -1, "enabled": p.enable_tl, "net": chassis_nets[0]},
            {"name": "TR", "sx": 1,  "sy": -1, "enabled": p.enable_tr, "net": chassis_nets[1]},
            {"name": "BR", "sx": 1,  "sy": 1,  "enabled": p.enable_br, "net": chassis_nets[2]},
            {"name": "BL", "sx": -1, "sy": 1,  "enabled": p.enable_bl, "net": chassis_nets[3]}
        ]

        # Calculate detour parameters
        r_detour = p.chassis_dia / 2.0 + p.clearance

        # Create isolated mounting zones and center marking
        for i, c in enumerate(corners):
            cx = c["sx"] * (x_lim - p.offset)
            cy = c["sy"] * (y_lim - p.offset)

            if c["enabled"]:
                # Draw mounting center mark
                if p.use_npth:
                    fp = pcbnew.FOOTPRINT(board)
                    fp.SetReference(f"MH_{c['name']}")
                    fp.SetPosition(pcbnew.VECTOR2I(int(pcbnew.FromMM(cx)), int(pcbnew.FromMM(cy))))
                    
                    pad = pcbnew.PAD(fp)
                    pad.SetNumber("1")
                    pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
                    pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
                    pad_sz = int(pcbnew.FromMM(p.hole_dia))
                    pad.SetSize(pcbnew.VECTOR2I(pad_sz, pad_sz))
                    pad.SetDrillSize(pcbnew.VECTOR2I(pad_sz, pad_sz))
                    pad.SetLayerSet(pad.UnplatedHoleMask())
                    fp.Add(pad)
                    board.Add(fp)
                else:
                    cross_w = int(pcbnew.FromMM(0.15))
                    cross_half = p.cross_size / 2.0
                    
                    line_h = pcbnew.PCB_SHAPE(board)
                    line_h.SetShape(pcbnew.SHAPE_T_SEGMENT)
                    line_h.SetStart(pcbnew.VECTOR2I(int(pcbnew.FromMM(cx - cross_half)), int(pcbnew.FromMM(cy))))
                    line_h.SetEnd(pcbnew.VECTOR2I(int(pcbnew.FromMM(cx + cross_half)), int(pcbnew.FromMM(cy))))
                    line_h.SetLayer(f_silks)
                    line_h.SetWidth(cross_w)
                    board.Add(line_h)
                    
                    line_v = pcbnew.PCB_SHAPE(board)
                    line_v.SetShape(pcbnew.SHAPE_T_SEGMENT)
                    line_v.SetStart(pcbnew.VECTOR2I(int(pcbnew.FromMM(cx)), int(pcbnew.FromMM(cy - cross_half))))
                    line_v.SetEnd(pcbnew.VECTOR2I(int(pcbnew.FromMM(cx)), int(pcbnew.FromMM(cy + cross_half))))
                    line_v.SetLayer(f_silks)
                    line_v.SetWidth(cross_w)
                    board.Add(line_v)

                # Draw circular copper zone on F_Cu and B_Cu
                poly = pcbnew.SHAPE_POLY_SET()
                poly.NewOutline()
                N_poly = 32
                r_chassis = p.chassis_dia / 2.0
                for j in range(N_poly):
                    angle = 2.0 * math.pi * j / N_poly
                    px = cx + r_chassis * math.cos(angle)
                    py = cy + r_chassis * math.sin(angle)
                    poly.Append(int(pcbnew.FromMM(px)), int(pcbnew.FromMM(py)))
                
                zone = pcbnew.ZONE(board)
                zone.SetNet(c["net"])
                zone.SetAssignedPriority(2)
                lset = pcbnew.LSET()
                lset.AddLayer(f_cu)
                lset.AddLayer(b_cu)
                zone.SetLayerSet(lset)
                zone.SetOutline(poly)
                board.Add(zone)

                # Draw stitching ring of 8 vias concentric with hole
                r_stitch = (p.hole_dia + p.chassis_dia) / 4.0
                for j in range(8):
                    phi = 2.0 * math.pi * j / 8.0
                    vx = cx + r_stitch * math.cos(phi)
                    vy = cy + r_stitch * math.sin(phi)
                    via = pcbnew.PCB_VIA(board)
                    via.SetPosition(pcbnew.VECTOR2I(int(pcbnew.FromMM(vx)), int(pcbnew.FromMM(vy))))
                    via.SetWidth(int(pcbnew.FromMM(p.via_dia)))
                    via.SetDrill(int(pcbnew.FromMM(p.via_drill)))
                    via.SetNet(c["net"])
                    via.SetLayerPair(f_cu, b_cu)
                    board.Add(via)

        # 5. Build GND Shielding Via Fence Path
        # We construct 8 path segments representing the continuous loop
        path_elements = []

        # Corner endpoints on setback lines
        # For a corner (sx, sy):
        # x_h, y_h = cx - sx * r_detour, sy * (y_lim - setback)
        # x_v, y_v = sx * (x_lim - setback), cy - sy * r_detour
        pts = {}
        for c in corners:
            sx, sy = c["sx"], c["sy"]
            name = c["name"]
            cx_val = sx * (x_lim - p.offset)
            cy_val = sy * (y_lim - p.offset)

            if c["enabled"]:
                # Rectangular detour coordinates
                x_h = cx_val - sx * r_detour
                y_h = sy * (y_lim - p.setback)
                x_v = sx * (x_lim - p.setback)
                y_v = cy_val - sy * r_detour
                pts[f"h_{name}"] = pcbnew.VECTOR2I(int(pcbnew.FromMM(x_h)), int(pcbnew.FromMM(y_h)))
                pts[f"v_{name}"] = pcbnew.VECTOR2I(int(pcbnew.FromMM(x_v)), int(pcbnew.FromMM(y_v)))
            else:
                # Fillet coordinates
                r_fillet = max(0.0, p.corner_radius - p.setback)
                cx_fillet = sx * (x_lim - p.corner_radius)
                cy_fillet = sy * (y_lim - p.corner_radius)
                x_h = cx_fillet
                y_h = sy * (y_lim - p.setback)
                x_v = sx * (x_lim - p.setback)
                y_v = cy_fillet
                pts[f"h_{name}"] = pcbnew.VECTOR2I(int(pcbnew.FromMM(x_h)), int(pcbnew.FromMM(y_h)))
                pts[f"v_{name}"] = pcbnew.VECTOR2I(int(pcbnew.FromMM(x_v)), int(pcbnew.FromMM(y_v)))

        # Assemble the closed loop clockwise starting at TL horizontal point
        # Top line: h_TL to h_TR
        path_elements.append(LineSegment(pts["h_TL"], pts["h_TR"]))
        
        # TR Corner
        path_elements.extend(self.get_corner_path(corners[1], p, r_detour, x_lim, y_lim, pts["h_TR"], pts["v_TR"], True))
        
        # Right line: v_TR to v_BR
        path_elements.append(LineSegment(pts["v_TR"], pts["v_BR"]))
        
        # BR Corner
        path_elements.extend(self.get_corner_path(corners[2], p, r_detour, x_lim, y_lim, pts["v_BR"], pts["h_BR"], False))
        
        # Bottom line: h_BR to h_BL
        path_elements.append(LineSegment(pts["h_BR"], pts["h_BL"]))
        
        # BL Corner
        path_elements.extend(self.get_corner_path(corners[3], p, r_detour, x_lim, y_lim, pts["h_BL"], pts["v_BL"], True))
        
        # Left line: v_BL to v_TL
        path_elements.append(LineSegment(pts["v_BL"], pts["v_TL"]))
        
        # TL Corner
        path_elements.extend(self.get_corner_path(corners[0], p, r_detour, x_lim, y_lim, pts["v_TL"], pts["h_TL"], False))

        # 6. Distribute Vias Along the Shielding Path
        # Calculate overall path length
        L_total = sum(el.length for el in path_elements)
        if L_total > 0:
            # Spacing formula: s = lambda / nfactor
            v = 299.792458 / math.sqrt(p.er)
            wavelength = v / p.fmax
            spacing_mm = wavelength / p.nfactor
            spacing_iu = pcbnew.FromMM(spacing_mm)

            N_vias = int(round(L_total / spacing_iu))
            if N_vias > 1:
                step_sz = L_total / N_vias
                for k in range(N_vias):
                    pos = self.get_point_on_path(path_elements, k * step_sz)
                    
                    # Place via
                    via = pcbnew.PCB_VIA(board)
                    via.SetPosition(pos)
                    via.SetWidth(int(pcbnew.FromMM(p.via_dia)))
                    via.SetDrill(int(pcbnew.FromMM(p.via_drill)))
                    via.SetNet(gnd_net)
                    via.SetLayerPair(f_cu, b_cu)
                    board.Add(via)

        # Rebuild connectivity to avoid GUI crashes
        if hasattr(board, "BuildConnectivity"):
            log_debug("Calling board.BuildConnectivity()...")
            try:
                board.BuildConnectivity()
                log_debug("board.BuildConnectivity() called.")
            except Exception as ex:
                log_debug(f"board.BuildConnectivity() failed: {ex}")

    def get_corner_path(self, corner, p, r_detour, x_lim, y_lim, start_pt, end_pt, start_is_horizontal):
        # Returns a list of segments representing the corner path
        sx, sy = corner["sx"], corner["sy"]
        
        if corner["enabled"]:
            # Rectangular detour
            if start_is_horizontal:
                mid_pt = pcbnew.VECTOR2I(start_pt.x, end_pt.y)
            else:
                mid_pt = pcbnew.VECTOR2I(end_pt.x, start_pt.y)
            return [LineSegment(start_pt, mid_pt), LineSegment(mid_pt, end_pt)]
        else:
            # Standard fillet arc or sharp corner
            r_fillet = p.corner_radius - p.setback
            if r_fillet > 0.0:
                cx_fillet = sx * (x_lim - p.corner_radius)
                cy_fillet = sy * (y_lim - p.corner_radius)
                center_iu = pcbnew.VECTOR2I(int(pcbnew.FromMM(cx_fillet)), int(pcbnew.FromMM(cy_fillet)))
                r_fillet_iu = int(pcbnew.FromMM(r_fillet))
                
                start_ang = math.atan2(start_pt.y - center_iu.y, start_pt.x - center_iu.x)
                end_ang = math.atan2(end_pt.y - center_iu.y, end_pt.x - center_iu.x)
                return [ArcSegment(center_iu, r_fillet_iu, start_ang, end_ang)]
            else:
                return [LineSegment(start_pt, end_pt)]

    def get_point_on_path(self, segments, d):
        for seg in segments:
            if d <= seg.length:
                if seg.length == 0:
                    return seg.point_at(0.0)
                return seg.point_at(d / seg.length)
            d -= seg.length
        return segments[-1].point_at(1.0)

    def draw_board_outline(self, board, x_lim, y_lim, radius, layer_id, width_iu):
        # Corner center helper
        def draw_fillet(cx, cy, start_ang, end_ang):
            diff = end_ang - start_ang
            while diff > math.pi:
                diff -= 2 * math.pi
            while diff < -math.pi:
                diff += 2 * math.pi
            mid_ang = start_ang + diff / 2.0
            
            r_iu = int(pcbnew.FromMM(radius))
            cx_iu = int(pcbnew.FromMM(cx))
            cy_iu = int(pcbnew.FromMM(cy))
            
            start_pt = pcbnew.VECTOR2I(int(cx_iu + r_iu * math.cos(start_ang)), int(cy_iu + r_iu * math.sin(start_ang)))
            mid_pt = pcbnew.VECTOR2I(int(cx_iu + r_iu * math.cos(mid_ang)), int(cy_iu + r_iu * math.sin(mid_ang)))
            end_pt = pcbnew.VECTOR2I(int(cx_iu + r_iu * math.cos(end_ang)), int(cy_iu + r_iu * math.sin(end_ang)))
            
            arc = pcbnew.PCB_SHAPE(board)
            arc.SetShape(pcbnew.SHAPE_T_ARC)
            arc.SetArcGeometry(start_pt, mid_pt, end_pt)
            arc.SetLayer(layer_id)
            arc.SetWidth(width_iu)
            board.Add(arc)

        # Straight segments helper
        def draw_line(x1, y1, x2, y2):
            line = pcbnew.PCB_SHAPE(board)
            line.SetShape(pcbnew.SHAPE_T_SEGMENT)
            line.SetStart(pcbnew.VECTOR2I(int(pcbnew.FromMM(x1)), int(pcbnew.FromMM(y1))))
            line.SetEnd(pcbnew.VECTOR2I(int(pcbnew.FromMM(x2)), int(pcbnew.FromMM(y2))))
            line.SetLayer(layer_id)
            line.SetWidth(width_iu)
            board.Add(line)

        if radius > 0.0:
            # 4 fillet arcs
            # Top-Right
            draw_fillet(x_lim - radius, -y_lim + radius, -math.pi/2.0, 0.0)
            # Bottom-Right
            draw_fillet(x_lim - radius, y_lim - radius, 0.0, math.pi/2.0)
            # Bottom-Left
            draw_fillet(-x_lim + radius, y_lim - radius, math.pi/2.0, math.pi)
            # Top-Left
            draw_fillet(-x_lim + radius, -y_lim + radius, math.pi, 1.5 * math.pi)

            # 4 lines
            draw_line(-x_lim + radius, -y_lim, x_lim - radius, -y_lim) # Top
            draw_line(x_lim, -y_lim + radius, x_lim, y_lim - radius) # Right
            draw_line(x_lim - radius, y_lim, -x_lim + radius, y_lim) # Bottom
            draw_line(-x_lim, y_lim - radius, -x_lim, -y_lim + radius) # Left
        else:
            # Simple sharp rectangle
            draw_line(-x_lim, -y_lim, x_lim, -y_lim)
            draw_line(x_lim, -y_lim, x_lim, y_lim)
            draw_line(x_lim, y_lim, -x_lim, y_lim)
            draw_line(-x_lim, y_lim, -x_lim, -y_lim)

    def get_or_create_net(self, board, net_name):
        net = board.FindNet(net_name)
        if not net:
            net = board.FindNet(0)
        return net

# Register plugin only if not running automated tests
if "KICAD_TESTING" not in os.environ:
    try:
        BoardGeneratorPlugin().register()
    except Exception:
        pass

