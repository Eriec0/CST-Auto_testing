'==============================================================
' MACRO CST STUDIO SUITE 2024
' Antena mikrostrip U-Slot + DGS Dumbbell, FR-4, target 3,5 GHz
' Semua dimensi dibuat sebagai PARAMETER, sehingga mudah diubah
' manual atau dari Python (GPR-BO) tanpa menggambar ulang.
'
' Sistem koordinat:
'   x : lebar (patch simetris terhadap x = 0)
'   y : panjang (feed line di y < 0, patch di 0 <= y <= Lp)
'   z : ground z = -tc..0, substrat 0..hs, patch hs..hs+tc
'
' Asumsi geometri (silakan ubah bila perlu):
'   LU  = panjang lengan U-Slot (arah y)
'   WU  = lebar luar U-Slot (arah x)
'   gU  = lebar jalur slot
'   PU  = pergeseran pusat U-Slot dari pusat patch (arah y)
'   LD, WD = panjang dan lebar kepala dumbbell
'   gD  = lebar penghubung dumbbell
'   AD  = panjang penghubung dumbbell (tetap, bukan variabel BO)
'   PD  = pergeseran pusat dumbbell dari pusat patch (arah y)
'   LI  = kedalaman inset, gI = lebar celah inset (tetap)
'   Bagian U-Slot yang tertutup berada di bawah, lengan mengarah ke +y.
'
' Monitor farfield: dibuat di BANYAK frekuensi (FF_F_START..FF_F_STOP, langkah FF_F_STEP),
' sehingga kurva efisiensi (1D Results\Efficiencies) punya banyak titik dan efisiensi/gain
' dapat dibaca di frekuensi resonansi, bukan hanya di 3,5 GHz. Monitor utama FF_F_MAIN
' (nama "farfield (f=3.5)") selalu dibuat agar kode Python lama tetap berjalan.
'==============================================================
Option Explicit

' ---------- SAKLAR ----------
Const LOAD_FROM_LIBRARY = True  ' True = muat material dari library CST. False = definisikan manual dengan nilai library (cadangan)
Const MAT_SUB = "FR-4 (lossy)"
Const MAT_CU = "Copper (annealed)"
Const RUN_SIM = True      ' True = jalankan solver setelah model jadi. False = hanya menggambar
Const EXPORT_FF = True    ' True = setelah solver selesai, ekspor farfield (directivity) ke file teks
Const FF_OUT_DIR = "C:\Users\User\Playground\CST_Auto\export\"   ' samakan dengan OUT_DIR di Python
Const FF_MON_ON = True    ' True = buat monitor farfield di banyak frekuensi. False = hanya monitor utama
Const FF_F_START = 2.5    ' GHz, harus >= batas bawah Solver.FrequencyRange
Const FF_F_STOP = 4.5     ' GHz, harus <= batas atas Solver.FrequencyRange
Const FF_F_STEP = 0.25    ' GHz (makin kecil makin banyak monitor, makin lama solver)
Const FF_F_MAIN = 3.5     ' GHz, monitor utama yang diekspor directivity-nya (selalu dibuat)
Const COMP = "antena"

' ---------- NILAI AWAL (string, titik desimal) ----------
Const V_hs = "1.6"        ' tebal substrat (mm)
Const V_tc = "0.035"      ' tebal tembaga (mm)
Const V_Lp = "20.22"
Const V_Wp = "26.33"
Const V_Wf = "3.11"
Const V_Lf = "10"
Const V_gI = "1.0"
Const V_LI = "6.15"
Const V_LU = "10.0"
Const V_WU = "10.5"
Const V_gU = "0.6"
Const V_PU = "2.0"        ' dinaikkan agar slot tidak menabrak ujung inset feed
Const V_LD = "3.0"
Const V_WD = "3.0"
Const V_gD = "0.3"
Const V_AD = "2.5"
Const V_PD = "0.0"

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
    Dim yb As Double, yt As Double, msg As String
    yb = Val(V_Lp) / 2 + Val(V_PU) - Val(V_LU) / 2
    yt = Val(V_Lp) / 2 + Val(V_PU) + Val(V_LU) / 2
    msg = ""
    If yb <= Val(V_LI) + 0.5 Then
        msg = msg & "Dasar U-Slot (y = " & Format(yb, "0.00") & " mm) terlalu dekat dengan ujung inset (LI = " & V_LI & " mm). Naikkan PU atau kurangi LI." & vbCrLf
    End If
    If yt >= Val(V_Lp) - 0.5 Then
        msg = msg & "Ujung U-Slot (y = " & Format(yt, "0.00") & " mm) hampir keluar dari patch (Lp = " & V_Lp & " mm). Kurangi LU atau PU." & vbCrLf
    End If
    If Val(V_WU) >= Val(V_Wp) - 1 Then
        msg = msg & "WU terlalu lebar terhadap Wp." & vbCrLf
    End If
    If msg <> "" Then MsgBox msg, vbExclamation, "Peringatan geometri"
End Sub

'--------------------------------------------------------------
Sub DefineParameters()
    SetP "hs", V_hs
    SetP "tc", V_tc
    SetP "Lp", V_Lp
    SetP "Wp", V_Wp
    SetP "Wf", V_Wf
    SetP "Lf", V_Lf
    SetP "gI", V_gI
    SetP "LI", V_LI
    SetP "LU", V_LU
    SetP "WU", V_WU
    SetP "gU", V_gU
    SetP "PU", V_PU
    SetP "LD", V_LD
    SetP "WD", V_WD
    SetP "gD", V_gD
    SetP "AD", V_AD
    SetP "PD", V_PD
    ' turunan
    SetP "Ws", "Wp+6*hs"
    SetP "ycen", "Lp/2"
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
    Dim mc As String, yd As String
    mc = MAT_CU
    yd = "(Lp/2+PD)"

    AddH "new component: " & COMP, "Component.New " & Q(COMP)

    ' ---- Substrat, ground, patch ----
    MkBrick "Substrate", MAT_SUB, "-Ws/2", "Ws/2", "-Lf", "Lp+3*hs", "0", "hs"
    MkBrick "Ground", mc, "-Ws/2", "Ws/2", "-Lf", "Lp+3*hs", "-tc", "0"
    MkBrick "Patch", mc, "-Wp/2", "Wp/2", "0", "Lp", "hs", "hs+tc"

    ' ---- Inset feed: celah dipotong dari patch ----
    MkBrick "Notch", mc, "-(Wf/2+gI)", "Wf/2+gI", "-1", "LI", "hs-tc", "hs+2*tc"
    Subtract "Patch", "Notch"

    ' ---- U-Slot (tiga bagian: dasar, lengan kiri, lengan kanan) ----
    MkBrick "SlotBase", mc, "-WU/2", "WU/2", "Lp/2+PU-LU/2", "Lp/2+PU-LU/2+gU", "hs-tc", "hs+2*tc"
    MkBrick "SlotL", mc, "-WU/2", "-WU/2+gU", "Lp/2+PU-LU/2", "Lp/2+PU+LU/2", "hs-tc", "hs+2*tc"
    MkBrick "SlotR", mc, "WU/2-gU", "WU/2", "Lp/2+PU-LU/2", "Lp/2+PU+LU/2", "hs-tc", "hs+2*tc"
    Subtract "Patch", "SlotBase"
    Subtract "Patch", "SlotL"
    Subtract "Patch", "SlotR"

    ' ---- Feed line (ditambahkan setelah slot dipotong) ----
    MkBrick "Feed", mc, "-Wf/2", "Wf/2", "-Lf", "LI", "hs", "hs+tc"
    AddH "boolean add shapes: " & COMP & ":Patch, " & COMP & ":Feed", _
         "Solid.Add " & Q(COMP & ":Patch") & ", " & Q(COMP & ":Feed")

    ' ---- DGS Dumbbell pada ground ----
    MkBrick "DGS_head1", mc, "-WD/2", "WD/2", yd & "-AD/2-LD", yd & "-AD/2", "-2*tc", "tc"
    MkBrick "DGS_neck", mc, "-gD/2", "gD/2", yd & "-AD/2", yd & "+AD/2", "-2*tc", "tc"
    MkBrick "DGS_head2", mc, "-WD/2", "WD/2", yd & "+AD/2", yd & "+AD/2+LD", "-2*tc", "tc"
    Subtract "Ground", "DGS_head1"
    Subtract "Ground", "DGS_neck"
    Subtract "Ground", "DGS_head2"
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
    AddH "define frequency range", "Solver.FrequencyRange " & Q("2.5") & ", " & Q("4.5")

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
    If Dir(FF_OUT_DIR, vbDirectory) = "" Then MkDir FF_OUT_DIR
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
