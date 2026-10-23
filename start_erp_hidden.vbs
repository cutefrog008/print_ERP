' ============================================================
'  start_erp_hidden.vbs
'  Runs start_erp.bat with NO visible console window.
'  Used by the "Printing ERP - Startup" scheduled task so the
'  ERP comes up silently in the background at logon.
'
'  All output is appended to startup.log for troubleshooting.
' ============================================================
Option Explicit

Dim sh, fso, base, cmd
Set sh  = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

base = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = base

cmd = "cmd /c """"" & base & "\start_erp.bat"" hidden >> """ & base & "\startup.log"" 2>&1"""

' 0 = hidden window, False = do not wait for it to finish.
sh.Run cmd, 0, False
