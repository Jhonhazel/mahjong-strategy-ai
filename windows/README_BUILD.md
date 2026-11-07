# Windows offline — build workflow ready, runtime NOT VERIFIED

No Windows VM/runner is available on the current macOSarm64 host. No Windows.exe
or supported offline ZIP has been produced. Unit fixtures on Mac are **not** a
WindowsPASS. Do not distribute the Start/Stop templates alone as a working app.

## Chosen method

PyInstaller6.22.3 **onedir**, built on actual Windowsx64/CPython3.12, with official
PyTorch2.15CPU, original unmodifiedPyMahjongGB1.4 and the exact v3 inference assets.
This avoids onefile temporary extraction and retains readable projectPython source;
actual templates/JS/CSS/SVG remain in app-runtime/_internal/app. EmbeddedPython
was considered but adds _pth/pip/DLL assembly; Nuitka adds more compiler complexity.
The chosen method is a native build, never a Mac/Linux cross-compiled.exe.

## Build-machine prerequisites (not lecturer prerequisites)

Windows11x64 recommended; CPython3.12x64 with py launcher; MicrosoftC++ BuildTools/
WindowsSDK for the upstream extension; PowerShell under an approved execution
policy; internet during build; sufficient disk for CPUtorch and frozen dependencies.
Do not disable antivirus/SmartScreen or execution-policy protections.

Obtain the genuine PostgreSQL14 Windowsx64 binary ZIP through:
https://www.postgresql.org/download/windows/
https://www.enterprisedb.com/download-postgresql-binaries

Independently verify the vendor/source checksum and review **all** bundled notices,
including third-party DLLs, before setting license_reviewed=true. Fill a private
copy of postgres-provenance.example.json with the real official URL/version/SHA.
The placeholder intentionally cannot pass. There is no invented trusted checksum
or automatic executable download. PostgreSQL's license permits redistribution
with its notices; it does not establish every EDB-bundled component's terms:
https://www.postgresql.org/about/licence/

From this exported source root, PowerShell:

```powershell
.\windows\build.ps1 -PostgresArchive 'C:\Build Inputs\postgresql-binaries.zip' -Provenance 'C:\Build Inputs\reviewed-provenance.json' -OutputDirectory 'C:\Build Output\mahjong-candidate'
```

These input paths are examples, not supplied files. The script creates an isolated
buildvenv under.local, installs the pinned officialCPU/build requirements, checks
dependencies, then invokes scripts.build_windows_package. No runtime package
installation occurs on the lecturer laptop. Build refuses existingoutput, wrong
OS/CPU/Python/torch, unreviewedPG input, missingnotices, unsafeZIP or asset mismatch.
No globalPG service or remote resource is created. No Git/CI upload is performed.

Expected **candidate** layout after a successful native build:

```text
mahjong-strategy-ai-windows-CANDIDATE/
  Start Mahjong.bat
  Stop Mahjong.bat
  app-runtime/Mahjong.exe + _internal/
  postgres-runtime/bin,lib,share,doc-or-notices/
  source/                     # readable application Python
  RUNTIME_MANIFEST.json
  BUILD_REPORT.json
  README_START_HERE.txt
```

Only one v3copy exists in runtimeassets. Full projecttests/audit/trainingdata do
not belong in this package. Dependency/vendor license files must remain included.
PyInstaller's redistribution exception still requires dependency-license compliance:
https://pyinstaller.org/en/stable/license.html

## Launcher lifecycle / persistence

Per-user LOCALAPPDATA\MahjongStrategyAI stores ownershipmarker, private config,
stable randomcredentials, dynamicfirst-run ports and project-ownedPGdata.
An existing owned profile missing state.json refuses startup: restore its original
private configuration rather than generating replacement credentials or ports.
Windows ACL protection precedes secretcreation. No database/secret overwrite or unrelated
process kill. PGbinds127.0.0.1 and checks actualdata_directory before use. DBrole is
non-superuser. Existing schema initialization remains idempotent and validates
semantics. A held instance lock prevents duplicate supervisors. Startup checks
package/model hashes, childPID/listeningport and actualmodel/DB readiness before
opening the browser. Stop requests a private controlfile; supervisor closes only
its own app processgroup and pg_ctl-owneddata, preservinghistory/config.

Forced poweroff/console termination may leave ownedPG running; nextStart detects
and validates its own cluster. NormalStop/Ctrl+C is the required path. No guarantee
of Windows signals/ACLs/DLL behavior is claimed until the following test is run.

## Mandatory clean-Windows gate before calling it supported

On a clean Windows11x64 ordinaryuser account, with no projectPython/Docker/PG and
no Macfilesystem access, record OS/version/architecture, packageSHA and results:

1. Verify candidatechecksum and every runtime/modelmanifest; ExtractAll to a path
   with spaces and Unicode. Check standarduserACLs and no unintendedUAC prompt.
2. Disconnect network. Double-clickStart. Verify actualownedPGinit/model readiness,
   browseropen, Home/Game/fiveContactcards, localtile/JS/CSS. DocsCDN may be offline.
3. Play legaldiscard and claim, verify bot/publicanimationNormal/Fast/Skip, request
   realv3Top3, save/list/detail/deletePGhistory, finish a realround. TestCSRF/owners.
4. Stop normally, check ownedports/processes closed, restart; same browsercookie
   and secret retainhistory. Activegame must not survive restart by assumption.
5. Test duplicateStart/Stop, slowstartup/timeout, missingruntimeDLL, wrongarchitecture,
   missing/tamperedmodel, incompleteZIP, occupiedPG/appport, failedPGauthentication,
   corruptedconfig/wrongowner, insufficientRAM/disk, browserlaunchfailure and crash
   recovery. Preserve existingdata and never kill the colliding service.
6. Inspect stdout/stderr/private diagnostics for secretleaks and check no network
   installation/telemetry/update occurs. Record native cold/warmstartup, memoryCPU,
   ZIP/extractedsize, PGstorage, signing/SmartScreen/AV results and requiredDLLs.

An unsigned build can trigger Defender/SmartScreen; do not bypass. If VCRuntime
or another system prerequisite remains, document it and do not call the package
zero-prerequisite. Signing/certificates/publication require separate authorization.
Only after real acceptance may the owner create a supported release.

### Individual offline acceptance records — all NOT RUN on Windows

Record native evidence for each requirement separately before promotion:

1. Fresh extraction.
2. First launcher execution.
3. Real database initialization.
4. Real model load.
5. Readiness200.
6. Browser opens.
7. Home renders.
8. New game starts.
9. Human legal discard.
10. Bot activity visible.
11. Actual model Top3.
12. Prediction saved in realPostgreSQL.
13. History shows new record.
14. History detail/table works.
15. Prediction deletion works.
16. Complete realround finishes.
17. Normal close.
18. Restart.
19. Previous history preserved.
20. Same persisted signing secret/cookie identity contract.
21. Bad model checksum fails safely.
22. Database port collision fails safely without stopping its owner.
23. Extraction path contains spaces (also testUnicode).
24. Normal use with network disconnected; no package/model download.
25. Ordinaryuser startup without unexpectedadmin prompt; document any prerequisite.
