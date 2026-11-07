# Phase4.3 — Zero-Configuration Lecturer Experience

6 November2026, Asia/Jakarta. BaseHEAD `28623736f6ce9d90eeb86dea98908b182631aad1`.
Implementasi diteruskan dari Phase4.2; perubahan lama tetap di workingtree.

## 1. Executive Verdict

**ONLINE — DEPLOYMENT READY.** Paket production dan staging lokal HTTPS teruji.
**WINDOWS OFFLINE — BUILD READY / NOT VERIFIED.** Workflow native tersedia;
binary/vendor provenance dan clean-Windows acceptance masih diperlukan. Tidak ada
overallPASS, URL publik, executableWindows atau ZIP offlineWindows yang siap dosen.

## 2. User Experience Before vs After

Phase4.2 membutuhkan DockerDesktop atau setupnative. Phase4.3 menyediakan jalur
deployment HTTPS agar dosen kelak cukup membuka URL, tetapi publikasi belum terjadi.
Jalur Windows ditargetkan ExtractAll → StartMahjong → browserready → StopMahjong,
tanpa Python/Docker/Node/systemPG pada laptop dosen. Itu merupakan target acceptance,
bukan pengalaman Windows yang telah dibuktikan. Mac/Docker existing tetap tersedia.

## 3. Existing Phase 4.2 Preservation

Fingerprint2257 file awal diperiksa:2252 identik,5perubahan disengaja,0hilang.
Lima file: README.md, README_START_HERE.md, app/settings.py, scripts/run_backend.py,
scripts/build_lecturer_release.py. Semua4file deliveryPhase4.2 identikSHA;44rowDEV
identik fingerprint per-ID. Checkpoint/metadata/contract, engine/referee/bots/action/
encoder, schema/API/security/session/CSRF, UI/JS/animasi dan roster tidak diubah.
Default builder lama tetap membuat runtime+audit; opsi baru dapat melewati audit
untuk menghindari penyalinan ulang arsip besar. Lihat preservation_regression.json.

## 4. Online Architecture

SatuVM Linux persistent: CaddyTLS → satu workerFastAPI → PostgreSQL private.
Tidak autoscale/sleep; activegames tetap in-memory. VolumePG/Caddy dan secretfiles
persisten. Overlay Compose memperluas aplikasi existing, tanpa backend tiruan.
Container production-like aktual berasal dari ekstraksi ZIP baru, Linuxarm64.
Proxy172.30.43.2 dan web172.30.43.3 dicadangkan; jaringanDB internal.

## 5. Online Security

Backend/DB tidak mempublikasikan port. Staging proxy mengikat127.0.0.1. Cookie
production Secure/HttpOnly/SameSiteLax; origin+CSRF existing tetap berlaku.
Tambahan trusted_proxy_ips defaultkosong, hanya alamatIP host eksplisit, menolak
wildcard/CIDR/hostname/unspecified/multicast/scopedIP. Runner mempercayai forwarded
headers hanya dari proxy tepat itu. TLSchain+hostname divalidasi memakai sertifikat
root publik CA staging, tanpa globaltrust/certificatewarning bypass. Spoof header,
wronghost, foreignsession dan missing/wrongCSRF teruji. Allowedhosts eksplisit.

## 6. Online Hosting Requirements

Mulai dengan >=2GiBRAM,2vCPU,20+GiBSSD untuk headroom; bukan jaminan kapasitas publik.
Peakmemory aktual: web220663808B, PG88293376B, Caddy18464768B. PGdata51304KiB.
Satu alur round:0.288589s wall,0.152756s CPUweb (~52.93% satuCPU saat sampel).
Ini smoke lokal, bukan loadtest atau RAMminimum. Docker image/buildcache perlu disk
tambahan. DigitalOcean tabelresmi memberi contoh2GiB/2vCPU/60GiB$18/bulan; pajak,
domain, backup/overage dapat menambah biaya. Tidak ada pembelian/provisioning.
https://www.digitalocean.com/pricing/droplets (diperiksa6Nov2026).
Renderfree bukan default: sleep15menit, filesystemephemeral, PGfreeberakhir30hari:
https://render.com/docs/free. VM persistent dipilih agar game tidak hilang karena sleep.

## 7. Online Deployment Status

**Tidak ada URL eksternal.** Publicdeploy/DNS/modelupload/paidcloud tidak diotorisasi.
Sisa langkah operator: persetujuan akun+budget+domain+publikasi, VMnativebuild,
transfer runtimeSHAverified, secret baru privat, hostname/firewall/DNS, CaddyACME,
externaldesktop/mobile acceptance dengan CA publik. Set port menggunakan
MAHJONG_HTTP_PORT=80 dan MAHJONG_HTTPS_PORT=443; jangan ikutkan localTLSoverride.
Instruksi tepat terdapat pada deploy/README.md. Container task sudah dihentikan;
volume dipertahankan; previewHTTP sementara dilepas.

## 8. Windows Offline Architecture

PyInstaller6.22.3 onedir dari Windowsx64/CPython3.12 asli, CPUtorch2.15,
PyMahjongGB1.4 asli, templates/static/config/v3 di layout ROOT yang sama, readable
Python source, runtime manifest semuafile. Tidak crosscompile atau membuat exe
palsu. Buildrequires compiler di mesinbuild, bukan laptop dosen. EmbeddedPython
dan Nuitka dipertimbangkan; onedir mengurangi perakitan runtime/ekstraksi onefile.
Tidak ada nativebuild/kompatibilitasDLL yang diklaim berhasil.

## 9. Windows PostgreSQL

Operator harus memasok binaryZIPPostgreSQL14x64 resmi beserta SHA256 yang diverifikasi
independen dan reviewredistributionnotices. Builder menolak provenance kosong,
asal nonvendor, inputunsafe/oversize atau notice hilang; tidak mengunduh otomatis.
Launcher dirancang menggunakan LOCALAPPDATA\\MahjongStrategyAI, ACLuser/SYSTEM,
ownershipmarker, credentials stabil, portloopback dinamis, SCRAM, role aplikasi
non-superuser, clusterdata sendiri, boundedreadiness dan hanya proses miliknya.
Tidak membuat globalservice/dropDB. History/config bertahan saatStop. Missing
privateconfig pada ownedprofile kini ditolak, meminta restoreoriginal; tidak rotasi.
Seluruh Windows-specific lifecycle/ACL/DLL tetap wajib diuji native.

## 10. Windows User Walkthrough

**Hanya setelah build dan25gate acceptance native lulus:** verifikasi SHA paketWindows
lengkap, ExtractAll ke folderuser, double-click `Start Mahjong.bat`, tunggu model+PG+
HTTPready sebelum browser dibuka, main/predict/History, tutup via `Stop Mahjong.bat`
atau Ctrl+C console. Restart memakai profil/kredensial sama; activegame tidak persisten.
SourceZIP Phase4.3 saat ini **bukan** paket tersebut dan tidak berisi Mahjong.exe.
Jangan mengirim templateStart sendiri ke dosen. Tidak bypassSmartScreen/AV/UAC.

## 11. Actual Windows Verification

**NOT RUN.** Host aktual Macarm64/Python3.12.10/Node24.4.1/DockerDesktop4.43.2,
engine28.3.2 Linuxarm64/Compose2.38.2. VBoxinventory0registered/0runningVMs.
Tidak ada WindowsOSversion/native screenshot/commandsuccess/exe/size/performance
yang dapat dilaporkan.19unitlauncher/build berjalan di Mac, bukan nativecertification.
Workflowbuild dan25scenario terpisah ada di windows/README_BUILD.md. Vendorarchive,
hash/notice review, Windowsbuilder dan acceptance hasilbuild masih menjadi gate.

## 12. Model Integrity

Ketiga aset asli diverifikasi ulang terhadap manifest dan byteSHA256:

| Aset | SHA256 |
|---|---|
| v3checkpoint | `ad05a5b2ce37ad45f93dc18628db9eb8ea5627a2f1d9d5f87b8a117c7f8a6720` |
| metadata | `84423c71f8826a367b59b868aad1360fdbcc2c9a5cef6ce9bb3219b2bbd4488e` |
| contract | `95f21b15be55dbbe4b9cf001edbc8b52462e4461b9bbaf39431a0a482e73adbc` |

Tidak retrain/fallbackmodel. Keluaran staging menyebut discard_mlp_flexible_v1:
ad05a5b2ce37 dan CPU; checkpoint yang sama harus ada pada candidateWindows.

## 13. Functional Integration

TLSstaging menjalankan23aksi legal (20Play/3Chi) sampai zimo25fan, score[99,-33,-33,-33],
dua inferensi v3, SELF_TURN+POST_MELD_DISCARD, top3terurut/mappinglegal, prediction
read-only+reuse, realPG Create/Read/Delete dan HTMLtable. History tetap200 sesudah
webrestart dengan cookiesama; ongoinggame404. Expiry200→404 setelah2.3s pada
settinguji2s, lalu default3600s dipulihkan. Home/Game/Contact/History/docs/assets
HTTP200 dengan headersecurity. Testregresi realdua-round seeds42/43 juga lulus.
BrowserIAB aktual menggunakan previewHTTPloopback terpisah: predictJ1/J2/T1 diTurn4,
Chi lalu J1/T1/J2 diTurn20, Historydetail, refresh, Normal/Fast/Skip, lima Contactcards
dan notice role belumdikonfirmasi. Viewport/documentwidth1440/1440 dan390/390.
Browser ini bukan bukti externalHTTPS; TLS diverifikasi oleh client tersendiri.

## 14. Regression

Freshbaseline437Python/91Node. Finalreview471Python passed,0failed/errors/skipped,
69.03s;91Node passed,0failed/cancelled/skipped,144.758125ms. Tambahan34kasusPhase4.3.
Focused66passed1.68s. OneexistingStarlette/httpxdeprecation tidak disembunyikan.
Identitas seluruh279kasusPhase2.2 dan437baseline dipastikan hadir+passing diJUnit
final. RealPG `_test` digunakan, termasuk concurrency/isolation/CSRF/schema dan
SQLexport/restore namespaceproyek terpisah. Tidak mengubah evidence lama.
Lihat docs/phase4_3_test_matrix.md dan docs/evidence/phase4_3/full_regression_review_final.xml.

## 15. Release Size and Performance

Ukuran/isi/SHA ZIP source final ada di artifacts/phase4_3/release_manifest.json;
semua member diverifikasi via release_verification.json. Runtime-only, tanpa
duplikasiaudit/expandedshards/venv/secret/devdatabase. ZIP ini memerlukan Docker/
prasyaratbuild, bukan Windows offlinebinary. WindowsZIP/extractedsize/startup/RAM
**NOT MEASURED**. Staging: torchimport1.213975584s, modelinitialization0.099987458s,
restart→ready2.57213425s. Dua prediction latency staging pada production_staging.json
adalah0.015317833s dan0.007666500s (mean0.011492167s); sampel2, bukan benchmarkumum.

## 16. Security and Privacy

Tidak membaca/membagikan developer.env/privatekeys/secretfiles/DBdump/logcustomer;
evidence tidak merekam cookie/CSRF/password/rawDEVrows. Secret staging dibuat lokal
privat lewat helperexisting dan tidak diekspor. Docker nonrootweb, privatePG,
explicitbound/owner/cleanup dan source/modelintegrity tetap. Tidak membuat CIupload
atau publicrelease. LicensingPG/PyInstallerexception tidak otomatis menyelesaikan
dependencylicenses; vendorbinary/DLL/notices/signing masih gate nativeWindows.
SourceZIP ownerlocal menyertakan checkpoint sesuai artifactpolicy existing; jangan
mengupload publik tanpa persetujuan tersendiri.

## 17. Independent Review

Satu reviewer independen read-only menemukan1Important (missingstate mengganti
credentials) dan1Minor (variabelpublicport salah). Kedua temuan diperbaiki sekali;
REDconfig1failed→focused66+full471passed, actualCompose80/443verified. Tidak ada
Critical dan tidak ada knownunresolvedCritical/Important. Reviewer tidak menjalankan
tes; tidak ada independentre-review setelahfix. LimitasiWindows tetap dinyatakan.
Rincian: docs/evidence/phase4_3/independent_review.md.

## 18. Exact Files Changed

Limaexistingfile disebut dibagian3. Tambahan source: scripts/smoke_online.py,
scripts/windows_launcher.py, scripts/build_windows_package.py, deploy/*, windows/*,
packaging/phase4_3_allowlist.json, tests/test_phase4_3_online.py dan
tests/test_phase4_3_windows.py. Dokumen/evidencebaru hanya namespacePhase4.3.
Daftar tepat filebaru/perubahan, ukuran/SHA dan statusGit final:
artifacts/phase4_3/file_inventory.json. Tidak ada unrelatedfile yang diedit.

## 19. Git State

Branchmain, HEAD tetap `28623736f6ce9d90eeb86dea98908b182631aad1`,0staged.
Workingtree masihdirty, termasuk2modified/80untracked warisanPhase4.2.
Jumlahmodified/untracked final ada di artifacts/phase4_3/git_state.json agar tidak
mencampur deltaPhase4.3 dengan seluruhworkingtree. Tidak stage/commit/push/reset/
stash/clean/branchchange/deploy.

## 20. Outstanding Risks

Tidak ada realpublicURL/independentnetwork/mobileHTTPS test atau authorizationcloud.
Windowsbinary/vendorSHA/license/DLL/ACL/signals/cleanuserofflineacceptance/signing
belumdiverifikasi. StagingARM64 tidak membuktikan AMD64hosting. Satuworker/in-memory
activegames hilang saatrestart; history mengikuti cookie+secret/TTLexisting, bukan akun.
Dockerimagepatching/backups/capacity/publicabuse perlu operator saatpublication.
OpenAPIdocs memakai CDN; halamanGameasset lokal, tetapi docsoffline perluinternet.
Pembagian peran Contact belumdikonfirmasi. PDF/video/pengumpulanUAS tidak dikerjakan
atau diklaim selesai pada Phase4.3.

## 21. Final Recommendation

Dosen **belum dapat membuka URLpublik** dan **belum dapat menjalankan ZIPWindows
offline asli** dari pekerjaan ini. JalurMac/DockerPhase4.2 yang telahteruji tetap
dapat digunakan dengan prasyaratnya. Source/deployment handoffPhase4.3 siap untuk
publicationauthorized dan nativeWindowsbuild/verification berikutnya. Jangan
menamai sourceZIP sebagai supportedWindowsrelease.

Jalankan existingMac/Docker dari ekstraksi: DockerDesktop aktif, `sh setup-macos.sh`,
lalu `sh run-macos.sh`; buka http://127.0.0.1:8000/. Preparednative dev tetap
`fastapi dev main.py` setelah environment/projectPGexisting siap. StagingHTTPS:
ikuti tigaComposecommands tepat pada deploy/README.md, tanpa bypassTLSwarning.

## Addendum audit 7 November 2026 — P43-IA01

**GO WITH CAVEATS — P43-IA01 CLOSED pada level source dan pengujian deterministik.**
Windows native tetap **NOT VERIFIED**; status online dan Windows Phase4.3 tidak
dinaikkan menjadi PASS karena perbaikan ini.

Penyebab: first-run menulis `owner.json` sebelum proteksi ACL. Jika ACL gagal,
retry menemukan marker tanpa `state.json` dan terkena guard profil lama. Guard
tersebut benar untuk profil yang sudah dipakai, sehingga tidak boleh dihapus.

Perubahan produksi hanya pada `scripts/windows_launcher.py`: `prepare_state()`
melakukan proteksi, pembuatan nilai konfigurasi, dan validasi sebelum persistensi.
`write_private()` menerima tracking identitas file opsional setelah exclusive-create
berhasil, agar partial write dapat dibedakan dari file milik penulis lain. Format
marker/config, APP_ID, KEYS, O_EXCL, no_links, port dan credential validation tetap.

Rollback hanya untuk first-run saat seluruh isi direktori masih cocok dengan file
yang dibuat percobaan itu, berdasarkan device/inode yang tercatat. Identitas
diperiksa lagi tepat sebelum setiap unlink. File diganti, data tambahan, identitas
yang tidak dapat dibuktikan, atau kegagalan cleanup menyebabkan fail-closed dengan
instruksi inspeksi; tidak ada recursive deletion. Profil lama missing-config tetap
ditolak sebelum membuat secret baru. Database, History dan file pra-eksisting tidak
dihapus atau diregenerasi.

Pengujian baru ditambahkan tanpa mengubah tes lama:

- RED awal: **6 failed, 30 passed**, termasuk seluruh **19 tes launcher lama lulus**.
  ACL failure meninggalkan marker; retry ditolak; partial JSON write, entropy
  failure dan invalid generated config meninggalkan state. Bukti: `p43_ia01_red.*`.
- GREEN awal: **36 passed**. Fault injection membuktikan retry tanpa cleanup manual,
  partial-write recovery, credential persistence, dan penolakan state asing/ambigu.
- Review independen read-only menemukan satu Important: snapshot rollback dapat
  menjadi usang sebelum unlink. Reproduksi tambahan: **1 failed**. Fix minimal
  memeriksa identitas setiap file lagi sebelum unlink; tes launcher final:
  **37 passed, 0 failed/errors/skipped**, 0,09 detik. Reviewer tidak menjalankan suite
  dan tidak melakukan independent re-review setelah fix; verifikasi akhir oleh
  implementer. Tidak ada temuan Critical/Important yang diketahui masih terbuka.
- Full regression final: **489 Python passed, 0 failed/errors/skipped**, 68,71 detik;
  seluruh **471 identitas baseline tetap passing**, ditambah **18 kasus baru**.
  PostgreSQL TEST nyata digunakan, termasuk dua round, history/concurrency dan SQL
  export/restore. Satu warning Starlette/httpx yang sudah ada tetap dilaporkan.
- Node: **91 passed**, 0 failed/cancelled/skipped, 117,902583 ms; seluruh identitas
  baseline sama. Frontend tidak diubah.

Evidence baru hanya memakai prefix `docs/evidence/phase4_3/p43_ia01_`; JUnit final:
`p43_ia01_full_regression_final.xml`. Ringkasan, review, diff, checksum, rekonsiliasi
kasus dan pemeriksaan DEV read-only:
`artifacts/phase4_3/p43_ia01_remediation.json`. Evidence historis tidak ditimpa.

Tidak tersedia Windows x64 lokal: host macOS arm64, inventori VBox nol VM terdaftar
atau berjalan. Simulasi ACL/junction bukan bukti API Windows native. Crash/power loss
atau orphan marker dari versi lama tetap ambigu dan fail-closed; tidak ada pemulihan
credential otomatis. Perlindungan atomik terhadap penulis adversarial dengan
privilege user yang sama dan urutan instance-lock lama berada di luar perbaikan ini.

Engine, referee, bot, encoder, model/aset beku, FastAPI/schema, frontend, deployment,
builder dan arsip delivery tidak diubah. Arsip ZIP historis belum memuat fix ini;
gunakan source terbaru ketika membuat candidate berikutnya. Tidak ada Git mutation,
commit, push, build Windows, publikasi model atau deployment.

## Native Windows setup — 7 November 2026

**GO WITH CAVEATS. WINDOWS NATIVE — IMPLEMENTED / NOT YET VERIFIED.** Source
menyediakan `setup-windows-native.cmd`, lalu `fastapi dev main.py` pada CMD yang
sama; startup berikutnya `run-windows-native.cmd`. Prasyarat tetap CPython3.12x64,
service PostgreSQL lokal, internet saat install dependency, dan C++/SDK jika build
PyMahjongGB memerlukannya. Windows PowerShell bawaan dipakai untuk ACL; tidak ada
execution-policy bypass, Docker, pgAdmin atau SQL Shell dalam jalur native ini.
Belum ada host Windows untuk membuktikan aktivasi CMD/ACL/dependency native.

Gap sebelumnya ada pada `native_finish()`: Windows meminta URL database yang sudah
diprovisikan. Kini `scripts/lecturer_setup.py` memakai satu helper baru,
`scripts/native_postgres.py`, hanya saat setup Windows eksplisit. Host default
127.0.0.1/5432; admin default postgres dengan password getpass tersembunyi. App role
mahjong_app memiliki LOGIN tanpa superuser/create-role/create-db/replication/bypassRLS
atau membership, database mahjong_phase3_dev dimiliki role itu. SQL memakai Psycopg
Identifier/Literal; role+comment transaksional, CREATE DATABASE autocommit dan setup
diserialisasi advisory lock. Schema memakai initialize_schema existing, lalu probe
lifespan aplikasi/model asli. Tidak ada provisioning pada startup FastAPI.

Credentials aplikasi dan session secret disiapkan sekali pada record privat
`.local/native-postgres/pending.json` sebelum DDL; admin password tidak disimpan.
Ownership token pada role/database membuat retry terverifikasi. Existing `.env`
valid dipakai ulang tanpa admin, rewrite, rotasi secret atau reset data. Role/database
asing ditolak sebelum perubahan. Jika CREATE DATABASE berhasil tetapi comment
ownership gagal, state ambigu ditolak dan memerlukan inspeksi; credentials tetap
tersimpan, tidak ada DROP atau destructive rollback. `.env` diterbitkan dari file
privat lengkap melalui exclusive hardlink sesudah schema/probe lulus; path symlink/
junction/unknown state ditolak. Metadata root menghindari recovery sembarang folder.

Keamanan Windows memakai DACL baru dengan hanya SID pengguna dan SYSTEM, inheritance
protected, lalu readback exact owner/principal/rights. Tidak hanya chmod atau grant
tambahan; acknowledgement yang tidak terverifikasi menyebabkan kegagalan sebelum
penulisan secret. PowerShell menerima path melalui JSON ASCII di stdin, program
statis encoded, tanpa shell interpolation. Eksekusi ACL nyata masih gate Windows.
Process overrides PGHOSTADDR/PGSERVICE/PGSERVICEFILE serta MAHJONG_DATABASE_URL/
MAHJONG_SESSION_SECRET ditolak agar config privat yang diuji tetap menjadi config
yang dipakai perintah FastAPI berikutnya. Script tidak mengubah environment itu.

Setup CMD memakai call activate.bat tanpa setlocal; memeriksa executable FastAPI
project sebelum return. Run CMD mengaktifkan venv, melakukan --check tanpa DDL/
install/admin, lalu menjalankan entrypoint asli. Native setup memverifikasi bitness,
pip check, import extension dan CPU torch. Paket terpin tidak diubah: actual host
macOS arm64 CPython3.12.10, torch2.15.0 (CUDA None, CPU tensor/inference), PyMahjongGB1.4.0,
FastAPI0.162.0, psycopg3.3.8; pip check lulus. Instalasi Windows belum dijalankan.

Evidence baru ada di `docs/evidence/phase4_3/native_setup/`. Fresh baseline489Python/
91Node. Proper RED17failed (sebelumnya fixture gagal karena Unix socket Mac terlalu
panjang; dikoreksi menjadi TCP-only, hasil awal tetap disimpan). Tes nyata memakai
cluster PostgreSQL14.19 disposable TCP/SCRAM, bukan DEV: provisioning, role/owner,
autentikasi salah, existing config/foreign resources, schema failure, disk/partial DDL,
retry, v3 prediction, History/read/detail dan restart. Fault tests/command dependency
spies dibedakan dari integrasi DB; tidak ada sertifikasi CMD dari unit tests.

Satu review independen read-only menemukan2Important (libpq environment redirect dan
explicit ACL grants tersisa) serta1Minor (marker dependency lama pada venv yang dibuat
ulang). Ketiganya diperbaiki dengan8tes RED→GREEN. Minor diregrade menjadi blocker
installer karena kontrak venv-baru harus memasang dependency. Tidak ada independent
re-review; reviewer tidak menjalankan suite atau menguji Windows. Scoped role-membership
dan32bit guards juga dibuktikan RED→GREEN. Final focused101passed5.57s; full521Python
passed72.55s dan91Node passed125.249333ms, zero failures/errors/skips, satu warning
Starlette/httpx existing. Seluruh489/91identitas baseline direkonsiliasi.

Paket baru runtime-only berada di `delivery/phase4_3-native-windows-2026-11-07/`;
dua launcher dan helper masuk allowlist nyata. Tidak merebuild audit besar atau
menimpa arsip lama. ZIP merupakan candidate source dengan prasyarat Python/PG,
bukan executable Windows standalone. Manifest, integritas source/model/DEV/history,
review dan daftar file tepat ada di `artifacts/phase4_3/native_setup/verification_summary.json`.
Quick-start diperbarui di README_START_HERE.md; source produksi hanya installer dan
helper baru. P43-IA01, app/schema/engine/ML/frontend/Caddy/Compose/requirements tetap.
Tidak ada stage, commit, push, publikasi, deployment, atau perubahan service PG existing.

Gate tersisa: clean Windowsx64, same-CMD `where fastapi`, kedua command pertama,
fresh-CMD run launcher, real ACL/PowerShell/NTFS hardlink/junction, compiler/dependencies
dan browser full-flow. Tidak ada jaminan atomic filesystem terhadap penulis hostile
dengan privilege user identik. Server policy/logging tidak diubah. Candidate siap
untuk pengujian Windows terkontrol; belum merupakan distribusi Windows tersertifikasi.

Referensi teknis primer:
https://www.postgresql.org/docs/14/sql-createdatabase.html
https://www.psycopg.org/psycopg3/docs/api/sql.html
https://www.postgresql.org/docs/current/libpq-envars.html
https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/icacls
