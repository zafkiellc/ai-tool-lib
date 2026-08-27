On Error Resume Next
Set fso = CreateObject("Scripting.FileSystemObject")
Set ws = CreateObject("WScript.Shell")
' 取 vbs 自身所在目录（兼容中文路径）
dir = fso.GetParentFolderName(WScript.ScriptFullName)

If Not fso.FileExists(dir & "\pythonw.exe") Then
    MsgBox "未找到 pythonw.exe，请确认本文件夹（巡站724_便携版）完整。" & vbCrLf & vbCrLf & "路径：" & dir, vbCritical, "督导填表助手"
    WScript.Quit 1
End If

' 0 = 隐藏窗口；False = 不等待（pythonw 自行驻留托盘）
ws.Run """" & dir & "\pythonw.exe"" server.py", 0, False

If Err.Number <> 0 Then
    MsgBox "启动失败：" & Err.Description & vbCrLf & vbCrLf & "路径：" & dir, vbCritical, "督导填表助手"
End If
