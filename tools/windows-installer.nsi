; Per-user Windows installer. Payload and output paths are supplied by the builder.
Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"
!include "x64.nsh"

Name "ASTRA Flight Systems"
OutFile "${OUTPUT_FILE}"
InstallDir "$LOCALAPPDATA\Programs\ASTRA Flight Systems"
InstallDirRegKey HKCU "Software\ASTRA Flight Systems" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
SetCompressorDictSize 32
BrandingText "ASTRA Flight Systems - Windows offline"
VIProductVersion "1.5.0.0"
VIAddVersionKey /LANG=1040 "ProductName" "ASTRA Flight Systems"
VIAddVersionKey /LANG=1040 "FileDescription" "ASTRA Flight Systems - Installer Windows offline"
VIAddVersionKey /LANG=1040 "FileVersion" "1.5.0.0"
VIAddVersionKey /LANG=1040 "LegalCopyright" "ASTRA Flight Systems contributors"
ShowInstDetails show
ShowUninstDetails show

!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "ASTRA Flight Systems per Windows"
!define MUI_WELCOMEPAGE_TEXT "Installa ASTRA per il tuo utente Windows.$\r$\n$\r$\nIl motore Python, i modelli 3D e le texture sono inclusi. Non servono Internet o una installazione Python separata.$\r$\n$\r$\nIl simulatore si apre nel browser locale. Chiudi eventuali istanze di ASTRA prima di aggiornare."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\ASTRA.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Avvia ASTRA Flight Systems"
!define MUI_FINISHPAGE_RUN_NOTCHECKED
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Italian"
!insertmacro MUI_LANGUAGE "English"

Var NoIntegration

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "Questo pacchetto richiede Windows a 64 bit (x64)."
    Abort
  ${EndIf}
  SetRegView 64
  SetShellVarContext current
  StrCpy $NoIntegration "0"
  ${GetParameters} $0
  ClearErrors
  ${GetOptions} $0 "/NOINTEGRATION" $1
  ${IfNot} ${Errors}
    StrCpy $NoIntegration "1"
  ${EndIf}
FunctionEnd

Section "Simulatore offline (obbligatorio)" CoreSection
  SectionIn RO
  SetOutPath "$INSTDIR"
  File /r "${PAYLOAD_DIR}\*.*"
  File /oname=ASTRA-PACKAGE.txt "${PACKAGE_MARKER}"
  File /oname=installation-manifest.json "${PACKAGE_MANIFEST}"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  ${If} $NoIntegration == "1"
    FileOpen $0 "$INSTDIR\no-integration.flag" w
    FileClose $0
  ${Else}
    CreateDirectory "$SMPROGRAMS\ASTRA Flight Systems"
    CreateShortcut "$SMPROGRAMS\ASTRA Flight Systems\ASTRA Flight Systems.lnk" "$INSTDIR\ASTRA.exe"
    CreateShortcut "$SMPROGRAMS\ASTRA Flight Systems\Disinstalla ASTRA.lnk" "$INSTDIR\Uninstall.exe"
    WriteRegStr HKCU "Software\ASTRA Flight Systems" "InstallDir" "$INSTDIR"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ASTRAFlightSystems" "DisplayName" "ASTRA Flight Systems (Windows offline)"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ASTRAFlightSystems" "DisplayVersion" "1.5.0.0"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ASTRAFlightSystems" "InstallLocation" "$INSTDIR"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ASTRAFlightSystems" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ASTRAFlightSystems" "QuietUninstallString" '$\"$INSTDIR\Uninstall.exe$\" /S'
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ASTRAFlightSystems" "DisplayIcon" "$INSTDIR\ASTRA.exe"
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ASTRAFlightSystems" "NoModify" 1
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ASTRAFlightSystems" "NoRepair" 1
  ${EndIf}
SectionEnd

Section /o "Collegamento sul desktop"
  ${If} $NoIntegration != "1"
    CreateShortcut "$DESKTOP\ASTRA Flight Systems.lnk" "$INSTDIR\ASTRA.exe"
  ${EndIf}
SectionEnd

Function un.onInit
  SetRegView 64
  SetShellVarContext current
  FileOpen $0 "$INSTDIR\ASTRA-PACKAGE.txt" r
  IfErrors invalid_package
  FileRead $0 $1
  FileClose $0
  StrCmp $1 "ASTRA-WINDOWS-1$\r$\n" valid_package
  invalid_package:
    MessageBox MB_ICONSTOP "Cartella ASTRA non riconosciuta. Disinstallazione annullata."
    Abort
  valid_package:
FunctionEnd

Section "Uninstall"
  ; Only remove files listed in the built payload; never recursively delete a folder.
  IfFileExists "$INSTDIR\no-integration.flag" skip_integration
  ReadRegStr $0 HKCU "Software\ASTRA Flight Systems" "InstallDir"
  StrCmp $0 "$INSTDIR" 0 skip_integration
    Delete "$SMPROGRAMS\ASTRA Flight Systems\ASTRA Flight Systems.lnk"
    Delete "$SMPROGRAMS\ASTRA Flight Systems\Disinstalla ASTRA.lnk"
    RMDir "$SMPROGRAMS\ASTRA Flight Systems"
    Delete "$DESKTOP\ASTRA Flight Systems.lnk"
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ASTRAFlightSystems"
    DeleteRegKey HKCU "Software\ASTRA Flight Systems"
  skip_integration:
  !include "${UNINSTALL_INCLUDE}"
  Delete "$INSTDIR\installation-manifest.json"
  Delete "$INSTDIR\no-integration.flag"
  Delete "$INSTDIR\ASTRA-PACKAGE.txt"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
SectionEnd
