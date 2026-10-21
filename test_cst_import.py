"""
build_antenna.py — v2
Bangun antena mikrostrip U-Slot + DGS Dumbbell dari nol di CST
Frekuensi target: 3,5 GHz, substrat FR-4 (custom)
"""

import cst.interface

CST_PROJECT_PATH = r"C:\Users\User\Playground\CST_Auto\antenna_5g.cst"

# ============================================================
# KONEKSI KE CST
# ============================================================
print("Menghubungkan ke CST...")
cst_env = cst.interface.DesignEnvironment.connect_to_any_or_new()
print("Terhubung. Membuat project Microwave Studio baru...")
project = cst_env.new_mws()
print("Project baru dibuat.")

def vba(code, label=""):
    """Eksekusi VBA dengan label untuk debugging."""
    try:
        project.schematic.execute_vba_code(code, timeout=None)
        if label:
            print(f"   ✅ {label}")
    except Exception as e:
        print(f"   ❌ GAGAL di '{label}': {e}")
        raise

# ============================================================
# 1. DEFINISI PARAMETER
# ============================================================
print("Mendefinisikan parameter...")
vba('''
Sub Main()
    StoreParameter("h",     "1.6")
    StoreParameter("Wg",    "35.93")
    StoreParameter("Lg",    "29.82")
    StoreParameter("Wp",    "26.33")
    StoreParameter("Lp",    "20.22")
    StoreParameter("Wf",    "3.11")
    StoreParameter("LI",    "6.15")
    StoreParameter("Lu",    "10.0")
    StoreParameter("Wu",    "10.5")
    StoreParameter("gU",    "0.6")
    StoreParameter("PU",    "0.0")
    StoreParameter("LD",    "3.0")
    StoreParameter("WD",    "3.0")
    StoreParameter("gD",    "0.3")
    StoreParameter("LA",    "2.5")
    StoreParameter("PD",    "0.0")
    StoreParameter("t_cu",  "0.035")
End Sub
''', "parameter")

# ============================================================
# 2. DEFINISI MATERIAL FR-4
# ============================================================
print("Mendefinisikan material FR-4 custom...")
vba('''
Sub Main()
    On Error Resume Next
    Material.Delete "FR4_custom"
    On Error Goto 0

    Material.Reset
    Material.Name "FR4_custom"
    Material.Folder ""
    Material.Colour "0.6", "0.8", "0.4"
    Material.Type "Normal"
    Material.SetMaterialType "Normal"
    Material.Epsilon "4.3"
    Material.Mue "1.0"
    Material.TanD "0.019"
    Material.TanDM "0.0"
    Material.Sigma "0.0"
    Material.Rho "0.0"
    Material.ThermalConductivity "0.3"
    Material.SpecificHeat "1000"
    Material.YoungsModulus "0"
    Material.PoissonsRatio "0"
    Material.ThermalExpansionRate "0"
    Material.Create
End Sub
''', "material FR4_custom")

# ============================================================
# 3. BANGUN GEOMETRI
# ============================================================
print("Membangun geometri...")

# 3a. Substrat
vba('''
Sub Main()
    Brick.Reset
    Brick.Name "substrate"
    Brick.Component "antenna"
    Brick.Material "FR4_custom"
    Brick.Xrange "-Wg/2", "Wg/2"
    Brick.Yrange "-Lg/2", "Lg/2"
    Brick.Zrange "0", "h"
    Brick.Create
End Sub
''', "substrat")

# 3b. Ground plane
vba('''
Sub Main()
    Brick.Reset
    Brick.Name "ground"
    Brick.Component "antenna"
    Brick.Material "PEC"
    Brick.Xrange "-Wg/2", "Wg/2"
    Brick.Yrange "-Lg/2", "Lg/2"
    Brick.Zrange "-t_cu", "0"
    Brick.Create
End Sub
''', "ground")

# 3c. Patch
vba('''
Sub Main()
    Brick.Reset
    Brick.Name "patch"
    Brick.Component "antenna"
    Brick.Material "PEC"
    Brick.Xrange "-Wp/2", "Wp/2"
    Brick.Yrange "-Lp/2", "Lp/2"
    Brick.Zrange "h", "h+t_cu"
    Brick.Create
End Sub
''', "patch")

# 3d. Feed line
vba('''
Sub Main()
    Brick.Reset
    Brick.Name "feed"
    Brick.Component "antenna"
    Brick.Material "PEC"
    Brick.Xrange "-Wf/2", "Wf/2"
    Brick.Yrange "-Lg/2", "-Lp/2"
    Brick.Zrange "h", "h+t_cu"
    Brick.Create
End Sub
''', "feed line")

# 3e. U-Slot outer
vba('''
Sub Main()
    Brick.Reset
    Brick.Name "uslot_outer"
    Brick.Component "antenna"
    Brick.Material "PEC"
    Brick.Xrange "-Wu/2+PU", "Wu/2+PU"
    Brick.Yrange "-Lu/2", "Lu/2"
    Brick.Zrange "h-0.001", "h+t_cu+0.001"
    Brick.Create
End Sub
''', "uslot_outer")

# 3f. U-Slot inner
vba('''
Sub Main()
    Brick.Reset
    Brick.Name "uslot_inner"
    Brick.Component "antenna"
    Brick.Material "PEC"
    Brick.Xrange "-Wu/2+gU+PU", "Wu/2-gU+PU"
    Brick.Yrange "-Lu/2-0.5", "Lu/2-gU"
    Brick.Zrange "h-0.001", "h+t_cu+0.001"
    Brick.Create
End Sub
''', "uslot_inner")

# 3g. Boolean U-Slot
vba('''
Sub Main()
    Solid.Subtract "antenna:uslot_outer", "antenna:uslot_inner"
    Solid.Subtract "antenna:patch", "antenna:uslot_outer"
End Sub
''', "boolean U-slot")

# 3h. DGS top
vba('''
Sub Main()
    Brick.Reset
    Brick.Name "dgs_top"
    Brick.Component "antenna"
    Brick.Material "PEC"
    Brick.Xrange "-WD/2+PD", "WD/2+PD"
    Brick.Yrange "LD/2", "LD/2+LD"
    Brick.Zrange "-t_cu-0.001", "0.001"
    Brick.Create
End Sub
''', "dgs_top")

# 3i. DGS bottom
vba('''
Sub Main()
    Brick.Reset
    Brick.Name "dgs_bot"
    Brick.Component "antenna"
    Brick.Material "PEC"
    Brick.Xrange "-WD/2+PD", "WD/2+PD"
    Brick.Yrange "-LD/2-LD", "-LD/2"
    Brick.Zrange "-t_cu-0.001", "0.001"
    Brick.Create
End Sub
''', "dgs_bot")

# 3j. DGS connector
vba('''
Sub Main()
    Brick.Reset
    Brick.Name "dgs_conn"
    Brick.Component "antenna"
    Brick.Material "PEC"
    Brick.Xrange "-gD/2+PD", "gD/2+PD"
    Brick.Yrange "-LD/2", "LD/2"
    Brick.Zrange "-t_cu-0.001", "0.001"
    Brick.Create
End Sub
''', "dgs_conn")

# 3k. Boolean DGS
vba('''
Sub Main()
    Solid.Add "antenna:dgs_top", "antenna:dgs_conn"
    Solid.Add "antenna:dgs_top", "antenna:dgs_bot"
    Solid.Subtract "antenna:ground", "antenna:dgs_top"
End Sub
''', "boolean DGS")

# ============================================================
# 4. SETUP SIMULASI
# ============================================================
print("Menyiapkan simulasi...")
vba('''
Sub Main()
    Solver.FrequencyRange "2.5", "4.5"
    Boundary.Open "expanded open", "expanded open", "expanded open"
    Boundary.Open "expanded open", "expanded open", "expanded open"
    Mesh.SetCreator "High Frequency"
    Mesh.MeshType "Tetrahedral"
End Sub
''', "setup simulasi")

# ============================================================
# 5. SIMPAN
# ============================================================
print(f"Menyimpan project ke {CST_PROJECT_PATH}...")
project.save(CST_PROJECT_PATH, include_results=True, allow_overwrite=True)
print("✅ Selesai.")
print()
print("Langkah manual selanjutnya di CST GUI:")
print("  1. Cek visual: pastikan substrat, patch, U-slot, DGS terlihat benar")
print("  2. Tambahkan port: Simulation → Sources → Waveguide Port")
print("     Pilih face feed line di ujung Y = -Lg/2")
print("  3. Jalankan simulasi S11 untuk cek baseline resonansi di ~3,5 GHz")