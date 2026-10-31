; Per-user Windows installer. Payload and output paths are supplied by the builder.
Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"
!include "x64.nsh"

Name "ASTRA Desktop"
OutFile "${OUTPUT_FILE}"
InstallDir "$LOCALAPPDATA\Programs\ASTRA Desktop"
InstallDirRegKey HKCU "Software\ASTRA Desktop" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID zlib
BrandingText "ASTRA Desktop - Windows offline"
!ifndef PRODUCT_VERSION
!define PRODUCT_VERSION "2.4.0.0"
!endif
VIProductVersion "${PRODUCT_VERSION}"
VIAddVersionKey /LANG=1040 "ProductName" "ASTRA Desktop"
VIAddVersionKey /LANG=1040 "FileDescription" "ASTRA Desktop - Installer Windows offline"
VIAddVersionKey /LANG=1040 "FileVersion" "${PRODUCT_VERSION}"
VIAddVersionKey /LANG=1040 "LegalCopyright" "ASTRA Desktop contributors"
ShowInstDetails show
ShowUninstDetails show

!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "ASTRA Desktop per Windows"
!define MUI_WELCOMEPAGE_TEXT "Installa ASTRA per il tuo utente Windows.$\r$\n$\r$\nIl motore Python, i modelli 3D e le texture sono inclusi. Non servono Internet o una installazione Python separata.$\r$\n$\r$\nIl simulatore apre una finestra grafica nativa Godot. Il client Python e incluso. Chiudi eventuali istanze di ASTRA prima di aggiornare."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\ASTRA.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Avvia ASTRA Desktop"
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
    CreateDirectory "$SMPROGRAMS\ASTRA Desktop"
    CreateShortcut "$SMPROGRAMS\ASTRA Desktop\ASTRA Desktop.lnk" "$INSTDIR\ASTRA.exe"
    CreateShortcut "$SMPROGRAMS\ASTRA Desktop\Grafica leggera.lnk" "$INSTDIR\ASTRA.exe" "--quality low"
    CreateShortcut "$SMPROGRAMS\ASTRA Desktop\Grafica alta.lnk" "$INSTDIR\ASTRA.exe" "--quality high"
    CreateShortcut "$SMPROGRAMS\ASTRA Desktop\Guida e API Python.lnk" "$INSTDIR\GUIDA-DESKTOP.txt"
    CreateShortcut "$SMPROGRAMS\ASTRA Desktop\Disinstalla ASTRA.lnk" "$INSTDIR\Uninstall.exe"
    WriteRegStr HKCU "Software\ASTRA Desktop" "InstallDir" "$INSTDIR"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ASTRADesktop" "DisplayName" "ASTRA Desktop (Windows offline)"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ASTRADesktop" "DisplayVersion" "${PRODUCT_VERSION}"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ASTRADesktop" "InstallLocation" "$INSTDIR"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ASTRADesktop" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ASTRADesktop" "QuietUninstallString" '$\"$INSTDIR\Uninstall.exe$\" /S'
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ASTRADesktop" "DisplayIcon" "$INSTDIR\ASTRA.exe"
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ASTRADesktop" "NoModify" 1
    WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ASTRADesktop" "NoRepair" 1
  ${EndIf}
SectionEnd

Section /o "Collegamento sul desktop"
  ${If} $NoIntegration != "1"
    CreateShortcut "$DESKTOP\ASTRA Desktop.lnk" "$INSTDIR\ASTRA.exe"
  ${EndIf}
SectionEnd

Function un.onInit
  SetRegView 64
  SetShellVarContext current
  FileOpen $0 "$INSTDIR\ASTRA-PACKAGE.txt" r
  IfErrors invalid_package
  FileRead $0 $1
  FileClose $0
  StrCmp $1 "ASTRA-DESKTOP-2$\r$\n" valid_package
  invalid_package:
    MessageBox MB_ICONSTOP "Cartella ASTRA non riconosciuta. Disinstallazione annullata."
    Abort
  valid_package:
FunctionEnd

Section "Uninstall"
  ; Only remove files listed in the built payload; never recursively delete a folder.
  IfFileExists "$INSTDIR\no-integration.flag" skip_integration
  ReadRegStr $0 HKCU "Software\ASTRA Desktop" "InstallDir"
  StrCmp $0 "$INSTDIR" 0 skip_integration
    Delete "$SMPROGRAMS\ASTRA Desktop\ASTRA Desktop.lnk"
    Delete "$SMPROGRAMS\ASTRA Desktop\Grafica leggera.lnk"
    Delete "$SMPROGRAMS\ASTRA Desktop\Grafica alta.lnk"
    Delete "$SMPROGRAMS\ASTRA Desktop\Guida e API Python.lnk"
    Delete "$SMPROGRAMS\ASTRA Desktop\Disinstalla ASTRA.lnk"
    RMDir "$SMPROGRAMS\ASTRA Desktop"
    Delete "$DESKTOP\ASTRA Desktop.lnk"
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\ASTRADesktop"
    DeleteRegKey HKCU "Software\ASTRA Desktop"
  skip_integration:
  !include "${UNINSTALL_INCLUDE}"
  Delete "$INSTDIR\installation-manifest.json"
  Delete "$INSTDIR\no-integration.flag"
  Delete "$INSTDIR\ASTRA-PACKAGE.txt"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
SectionEnd
