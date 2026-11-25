'==============================================================
' MACRO CST STUDIO SUITE 2024
' Antena mikrostrip patch FR-4 dengan dua slot sejajar terbuka (patch berbentuk E), pita demonstrasi 2,4 sampai 2,6 GHz
' Dibuat dari macros/uslot_dgs_dumbbell_v4.bas (struktur, port, solver, monitor, dan ekspor SAMA); hanya geometri, parameter, dan pita diganti.
' Semua dimensi dibuat sebagai PARAMETER, sehingga bisa diubah manual atau dari Python (GPR-BO) tanpa menggambar ulang.
'
' Sistem koordinat (sama dengan v4):
'   x : lebar (patch simetris terhadap x = 0)
'   y : panjang (feed line di y < 0, patch di 0 <= y <= Lp)
'   z : ground z = -tc..0, substrat 0..hs, patch hs..hs+tc
'
' Parameter geometri BO (nama PERSIS sama dengan PARAM_NAMES di designs/eshape_fr4.py):
'   Lp, Wp     = panjang (arah y) dan lebar (arah x) patch
'   Lsl, Wsl   = panjang (arah y) dan lebar (arah x) tiap slot; slot dari y = Lp - Lsl sampai tepi y = Lp (terbuka)
'   Dsl        = jarak pusat tiap slot dari x = 0 (dua slot simetris di x = -Dsl dan x = +Dsl)
'   LI         = kedalaman inset umpan
' Parameter tetap: hs (tebal substrat), tc (tebal tembaga), Wf (lebar saluran 50 ohm), Lf (panjang saluran), gI (celah inset).
' Parameter turunan: Wsub = Wp + 6*hs (lebar substrat dan ground).
'
' Monitor farfield: 1,5 sampai 3,5 GHz langkah 0,25 (9 titik, termasuk monitor utama 2,5 GHz). Nilai ini HARUS sama dengan
' CST["monitors_ghz"] dan CST["f0_ghz"] di designs/eshape_fr4.py. Solver.FrequencyRange 1,5 sampai 3,5 GHz.
' Nilai awal geometri hanyalah PERKIRAAN dari rumus patch standar, bukan hasil simulasi; jalankan satu kali untuk melihat fr awalnya.
'==============================================================
Option Explicit

' ---------- SAKLAR ----------
Const LOAD_FROM_LIBRARY = True  ' True = muat material dari library CST. False = definisikan manual dengan nilai library (cadangan)
Const MAT_SUB = "FR-4 (lossy)"
Const MAT_CU = "Copper (annealed)"
Const RUN_SIM = False     ' False = hanya menggambar model (disarankan; simulasi dijalankan oleh py main.py run). True = jalankan solver setelah model jadi
Const EXPORT_FF = False   ' True = setelah solver selesai, ekspor farfield ke file teks (hanya bila RUN_SIM = True)
Const FF_OUT_DIR = "C:\Users\User\Playground\CST_Auto\export\"   ' hanya dipakai bila EXPORT_FF = True
Const FF_MON_ON = True    ' True = buat monitor farfield di banyak frekuensi. False = hanya monitor utama
Const FF_F_START = 1.5    ' GHz, harus >= batas bawah Solver.FrequencyRange; = CST["monitors_ghz"][0] di file desain
Const FF_F_STOP = 3.5     ' GHz, harus <= batas atas Solver.FrequencyRange;  = CST["monitors_ghz"][1]
Const FF_F_STEP = 0.25    ' GHz;                                             = CST["monitors_ghz"][2]
Const FF_F_MAIN = 2.5     ' GHz, monitor utama (selalu dibuat);              = CST["f0_ghz"]
Const COMP = "antena"

' ---------- NILAI AWAL (string, titik desimal) ----------
Const V_hs = "1.6"        ' tebal substrat (mm)
Const V_tc = "0.035"      ' tebal tembaga (mm)
Const V_Wf = "3.11"       ' lebar saluran 50 ohm untuk FR-4 1,6 mm (EXTRA_BASE di file desain)
Const V_Lf = "10"
Const V_gI = "1.0"
Const V_Lp = "27.0"
Const V_Wp = "38.0"
Const V_Lsl = "12.0"
Const V_Wsl = "2.0"
Const V_Dsl = "9.0"
Const V_LI = "7.0"

'--------------------------------------------------------------
Function Q(s As String) As String
    Q = Chr(34) & s & Chr(34)
End Function

Sub AddH(title As String, code As String)
    AddToHistory title, code
End Sub

Sub SetP(nm As String, expr As String)
    StoreParameter nm, expr
End Sub

Sub MkBrick(nm As String, mat As String, x1 As String, x2 As String, y1 As String, y2 As String, z1 As String, z2 As String)
    Dim s As String
    s = "With Brick" & vbLf
    s = s & ".Reset" & vbLf
    s = s & ".Name " & Q(nm) & vbLf
    s = s & ".Component " & Q(COMP) & vbLf
    s = s & ".Material " & Q(mat) & vbLf
    s = s & ".Xrange " & Q(x1) & ", " & Q(x2) & vbLf
    s = s & ".Yrange " & Q(y1) & ", " & Q(y2) & vbLf
    s = s & ".Zrange " & Q(z1) & ", " & Q(z2) & vbLf
    s = s & ".Create" & vbLf
    s = s & "End With"
    AddH "define brick: " & COMP & ":" & nm, s
End Sub

Sub Subtract(target As String, tool As String)
    AddH "boolean subtract shapes: " & COMP & ":" & target & ", " & COMP & ":" & tool, _
         "Solid.Subtract " & Q(COMP & ":" & target) & ", " & Q(COMP & ":" & tool)
End Sub

'--------------------------------------------------------------
Sub CheckGeometry()
    ' Aturan yang sama dengan geometry_problems() di designs/eshape_fr4.py
    Dim msg As String
    msg = ""
    If Val(V_Lp) - Val(V_Lsl) <= Val(V_LI) + 0.5 Then
        msg = msg & "Dasar slot (y = " & Format(Val(V_Lp) - Val(V_Lsl), "0.00") & " mm) terlalu dekat dengan ujung inset (LI = " & V_LI & " mm). Kurangi Lsl atau LI." & vbCrLf
    End If
    If Val(V_Dsl) - Val(V_Wsl) / 2 < 3 Then
        msg = msg & "Lengan tengah terlalu sempit (Dsl - Wsl/2 < 3 mm). Naikkan Dsl atau kurangi Wsl." & vbCrLf
    End If
    If Val(V_Dsl) + Val(V_Wsl) / 2 > Val(V_Wp) / 2 - 2 Then
        msg = msg & "Slot terlalu dekat tepi samping patch (lengan luar < 2 mm). Kurangi Dsl atau naikkan Wp." & vbCrLf
    End If
    If msg <> "" Then MsgBox msg, vbExclamation, "Peringatan geometri"
End Sub

'--------------------------------------------------------------
Sub DefineParameters()
    SetP "hs", V_hs
    SetP "tc", V_tc
    SetP "Wf", V_Wf
    SetP "Lf", V_Lf
    SetP "gI", V_gI
    SetP "Lp", V_Lp
    SetP "Wp", V_Wp
    SetP "Lsl", V_Lsl
    SetP "Wsl", V_Wsl
    SetP "Dsl", V_Dsl
    SetP "LI", V_LI
    ' turunan
    SetP "Wsub", "Wp+6*hs"
End Sub

Sub DefineUnitsAndBoundary()
    Dim s As String
    s = "With Units" & vbLf
    s = s & ".Geometry " & Q("mm") & vbLf
    s = s & ".Frequency " & Q("GHz") & vbLf
    s = s & ".Time " & Q("ns") & vbLf
    s = s & "End With"
    AddH "define units", s

    s = "With Boundary" & vbLf
    s = s & ".Xmin " & Q("expanded open") & vbLf
    s = s & ".Xmax " & Q("expanded open") & vbLf
    s = s & ".Ymin " & Q("expanded open") & vbLf
    s = s & ".Ymax " & Q("expanded open") & vbLf
    s = s & ".Zmin " & Q("expanded open") & vbLf
    s = s & ".Zmax " & Q("expanded open") & vbLf
    s = s & "End With"
    AddH "define boundaries", s
End Sub

Sub DefineMaterials()
    Dim s As String
    If LOAD_FROM_LIBRARY Then
        AddH "define material: " & MAT_SUB, "Material.LoadFromMaterialLibrary " & Q(MAT_SUB)
        AddH "define material: " & MAT_CU, "Material.LoadFromMaterialLibrary " & Q(MAT_CU)
    Else
        ' Cadangan: nama sama dengan library, nilai mengikuti library CST (sepengetahuan saya)
        s = "With Material" & vbLf
        s = s & ".Reset" & vbLf
        s = s & ".Name " & Q(MAT_SUB) & vbLf
        s = s & ".Folder " & Q("") & vbLf
        s = s & ".FrqType " & Q("all") & vbLf
        s = s & ".Type " & Q("Normal") & vbLf
        s = s & ".SetMaterialUnit " & Q("GHz") & ", " & Q("mm") & vbLf
        s = s & ".Epsilon " & Q("4.3") & vbLf
        s = s & ".Mu " & Q("1.0") & vbLf
        s = s & ".Sigma " & Q("0.0") & vbLf
        s = s & ".TanD " & Q("0.025") & vbLf
        s = s & ".TanDFreq " & Q("10.0") & vbLf
        s = s & ".TanDGiven " & Q("True") & vbLf
        s = s & ".TanDModel " & Q("ConstTanD") & vbLf
        s = s & ".Colour " & Q("0.94") & ", " & Q("0.82") & ", " & Q("0.76") & vbLf
        s = s & ".Create" & vbLf
        s = s & "End With"
        AddH "define material: " & MAT_SUB, s

        s = "With Material" & vbLf
        s = s & ".Reset" & vbLf
        s = s & ".Name " & Q(MAT_CU) & vbLf
        s = s & ".Folder " & Q("") & vbLf
        s = s & ".Type " & Q("Normal") & vbLf
        s = s & ".Epsilon " & Q("1.0") & vbLf
        s = s & ".Mu " & Q("1.0") & vbLf
        s = s & ".Kappa " & Q("5.8e7") & vbLf
        s = s & ".Rho " & Q("8930.0") & vbLf
        s = s & ".Colour " & Q("1.0") & ", " & Q("0.65") & ", " & Q("0.0") & vbLf
        s = s & ".Create" & vbLf
        s = s & "End With"
        AddH "define material: " & MAT_CU, s
    End If
End Sub

Sub BuildGeometry()
    Dim mc As String
    mc = MAT_CU

    AddH "new component: " & COMP, "Component.New " & Q(COMP)

    ' ---- Substrat, ground (penuh, tanpa DGS), patch ----
    MkBrick "Substrate", MAT_SUB, "-Wsub/2", "Wsub/2", "-Lf", "Lp+3*hs", "0", "hs"
    MkBrick "Ground", mc, "-Wsub/2", "Wsub/2", "-Lf", "Lp+3*hs", "-tc", "0"
    MkBrick "Patch", mc, "-Wp/2", "Wp/2", "0", "Lp", "hs", "hs+tc"

    ' ---- Inset feed: celah dipotong dari patch (sama dengan v4) ----
    MkBrick "Notch", mc, "-(Wf/2+gI)", "Wf/2+gI", "-1", "LI", "hs-tc", "hs+2*tc"
    Subtract "Patch", "Notch"

    ' ---- Dua slot sejajar terbuka di tepi y = Lp (alat potong melewati tepi 1 mm agar potongan bersih) ----
    MkBrick "SlotA", mc, "-Dsl-Wsl/2", "-Dsl+Wsl/2", "Lp-Lsl", "Lp+1", "hs-tc", "hs+2*tc"
    MkBrick "SlotB", mc, "Dsl-Wsl/2", "Dsl+Wsl/2", "Lp-Lsl", "Lp+1", "hs-tc", "hs+2*tc"
    Subtract "Patch", "SlotA"
    Subtract "Patch", "SlotB"

    ' ---- Feed line (ditambahkan setelah slot dipotong, sama dengan v4) ----
    MkBrick "Feed", mc, "-Wf/2", "Wf/2", "-Lf", "LI", "hs", "hs+tc"
    AddH "boolean add shapes: " & COMP & ":Patch, " & COMP & ":Feed", _
         "Solid.Add " & Q(COMP & ":Patch") & ", " & Q(COMP & ":Feed")
End Sub

Sub DefinePortAndSolver()
    Dim s As String
    s = "With Port" & vbLf
    s = s & ".Reset" & vbLf
    s = s & ".PortNumber " & Q("1") & vbLf
    s = s & ".Label " & Q("") & vbLf
    s = s & ".NumberOfModes " & Q("1") & vbLf
    s = s & ".AdjustPolarization " & Q("False") & vbLf
    s = s & ".PolarizationAngle " & Q("0.0") & vbLf
    s = s & ".ReferencePlaneDistance " & Q("0") & vbLf
    s = s & ".TextSize " & Q("50") & vbLf
    s = s & ".Coordinates " & Q("Free") & vbLf
    s = s & ".Orientation " & Q("ymin") & vbLf
    s = s & ".PortOnBound " & Q("False") & vbLf
    s = s & ".ClipPickedPortToBound " & Q("False") & vbLf
    s = s & ".Xrange " & Q("-(Wf/2+4*hs)") & ", " & Q("Wf/2+4*hs") & vbLf
    s = s & ".Yrange " & Q("-Lf") & ", " & Q("-Lf") & vbLf
    s = s & ".Zrange " & Q("-tc") & ", " & Q("6*hs") & vbLf
    s = s & ".XrangeAdd " & Q("0.0") & ", " & Q("0.0") & vbLf
    s = s & ".YrangeAdd " & Q("0.0") & ", " & Q("0.0") & vbLf
    s = s & ".ZrangeAdd " & Q("0.0") & ", " & Q("0.0") & vbLf
    s = s & ".SingleEnded " & Q("False") & vbLf
    s = s & ".Create" & vbLf
    s = s & "End With"
    AddH "define port: 1", s

    ChangeSolverType "HF Time Domain"
    AddH "define frequency range", "Solver.FrequencyRange " & Q("1.5") & ", " & Q("3.5")

    s = "With Mesh" & vbLf
    s = s & ".MeshType " & Q("PBA") & vbLf
    s = s & "End With"
    AddH "define mesh type", s

    DefineFarfieldMonitors
End Sub

'--------------------------------------------------------------
' ---------- Monitor farfield multi-frekuensi ----------
Function Round4(x As Double) As Double
    Round4 = Int(x * 10000 + 0.5) / 10000
End Function

' Teks frekuensi dengan titik desimal (aman untuk pengaturan regional koma). 3 -> "3", 2.75 -> "2.75"
Function FFText(f As Double) As String
    FFText = Replace(CStr(Round4(f)), ",", ".")
End Function

Function FFName(f As Double) As String
    FFName = "farfield (f=" & FFText(f) & ")"
End Function

Function FFItemName() As String
    FFItemName = "Farfields\" & FFName(FF_F_MAIN) & " [1]"
End Function

Sub AddFarfieldMonitor(f As Double)
    Dim s As String
    s = "With Monitor" & vbLf
    s = s & ".Reset" & vbLf
    s = s & ".Name " & Q(FFName(f)) & vbLf
    s = s & ".Domain " & Q("Frequency") & vbLf
    s = s & ".FieldType " & Q("Farfield") & vbLf
    s = s & ".MonitorValue " & Q(FFText(f)) & vbLf
    s = s & ".ExportFarfieldSource " & Q("False") & vbLf
    s = s & ".UseSubvolume " & Q("False") & vbLf
    s = s & ".Create" & vbLf
    s = s & "End With"
    AddH "define farfield monitor: " & FFName(f), s
End Sub

Sub DefineFarfieldMonitors()
    Dim i As Long, n As Long, f As Double, hasMain As Boolean
    hasMain = False
    If FF_MON_ON Then
        n = Int((FF_F_STOP - FF_F_START) / FF_F_STEP + 0.5)
        For i = 0 To n
            f = Round4(FF_F_START + i * FF_F_STEP)
            AddFarfieldMonitor f
            If Abs(f - FF_F_MAIN) < 0.00001 Then hasMain = True
        Next i
    End If
    If Not hasMain Then AddFarfieldMonitor FF_F_MAIN
End Sub

Sub ExportCut(phi As Integer, plotMode As String, fname As String)
    On Error Resume Next
    Kill fname
    On Error GoTo 0

    SelectTreeItem FFItemName()
    With FarfieldPlot
        .Reset
        .Plottype "Polar"
        .Vary "angle1"
        .Theta "0"
        .Phi CStr(phi)
        .Step "1"
        .Step2 "1"
        .SetLockSteps "True"
        .SetPlotMode plotMode
        .Plot
    End With

    With ASCIIExport
        .Reset
        .FileName fname
        .Mode "FixedWidth"
        .Execute
    End With

    If Dir(fname) = "" Then
        MsgBox "File tidak terbentuk: " & fname, vbExclamation, "Ekspor farfield"
    End If
End Sub

Sub Main ()
    If EXPORT_FF Then
        If Dir(FF_OUT_DIR, vbDirectory) = "" Then MkDir FF_OUT_DIR
    End If
    CheckGeometry
    DefineParameters
    DefineUnitsAndBoundary
    DefineMaterials
    BuildGeometry
    DefinePortAndSolver
    Plot.ZoomToStructure
    If RUN_SIM Then
        Solver.Start
        If EXPORT_FF Then
            ' Plot polar: satu file memuat irisan phi dan phi+180,
            ' jadi dua file mencakup kedua bidang utama.
            ExportCut 0, "Directivity", FF_OUT_DIR & "ff_dir_phi0.txt"
            ExportCut 90, "Directivity", FF_OUT_DIR & "ff_dir_phi90.txt"
        End If
    End If
End Sub
