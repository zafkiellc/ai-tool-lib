' Gacha Advisor - VBS launcher (hidden console)
' Locates WorkBuddy managed Python (pythonw preferred, no console), runs launcher.py (systray version).
Option Explicit
Dim WshShell, FSO, Home, Pyw, Py, ScriptDir, Cmd

Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = ScriptDir

Home = WshShell.ExpandEnvironmentStrings("%USERPROFILE%")
Pyw = ScriptDir & "\runtime\python\pythonw.exe"
Py  = ScriptDir & "\runtime\python\python.exe"

If FSO.FileExists(Pyw) Then
    Cmd = """" & Pyw & """ launcher.py"
ElseIf FSO.FileExists(Py) Then
    Cmd = """" & Py & """ launcher.py"
Else
    ' 回退：WorkBuddy 托管运行时 → 系统 python
    If FSO.FileExists(Home & "\.workbuddy\binaries\python\versions\3.13.12\pythonw.exe") Then
        Cmd = """" & Home & "\.workbuddy\binaries\python\versions\3.13.12\pythonw.exe"" launcher.py"
    Else
        Cmd = "python launcher.py"
    End If
End If

On Error Resume Next
' 0=hide window; False=don't wait (run background)
WshShell.Run Cmd, 0, False
If Err.Number <> 0 Then
    MsgBox "Launch failed: " & Err.Description & vbCrLf & vbCrLf & "Cmd: " & Cmd & _
           vbCrLf & "Make sure Python is installed, or check startup_error.log.", _
           0, "Gacha Advisor"
End If
On Error GoTo 0
