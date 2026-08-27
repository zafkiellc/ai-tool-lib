' QiangJian Cert Download Tool - Hidden Launcher
' Launch pythonw.exe (no console window)
Set fso = CreateObject("Scripting.FileSystemObject")
baseDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = baseDir
shell.Run """" & baseDir & "\python\pythonw.exe"" ""web_launcher.py""", 0, False
