# Independent Phase4.3 review and resolution

One fresh read-only reviewer (`phase43_review`, separate agent) inspected the final
deployment/launcher/build changes and compared the preflight source fingerprints.
The reviewer did **not** run tests. No second review or independent re-review was
requested after these fixes.

| Severity | Finding | Resolution / evidence |
|---|---|---|
| Important | An existing owned Windows profile missing `state.json` regenerated credentials and ports even when PG data remained. | `prepare_state` now refuses before writes/protection/database startup and requests restoration of the original private config. Regression creates a retained PG_VERSION/history sentinel, removes only the test config, and asserts no files change. `review_config_red`: one executed failing case; `review_focused_green`:66 passed; `full_regression_review_final`:471 passed. |
| Minor | Public handoff used HTTPPORT/HTTPSPORT, which are not the Compose variable names. | Guide now uses MAHJONG_HTTP_PORT/MAHJONG_HTTPS_PORT. Actual Compose config with80/443 resolves both published ports correctly; `artifacts/phase4_3/expiry_cleanup.json`. |

Reviewer reported no Critical findings. Both actionable findings received one fix
pass and executed verification. No unresolved Critical/Important source finding
is known; this is not certification of unexecuted Windows behavior or a public
site. Native Windows ACLs, process signals, DLL collection, vendor binary licensing,
SmartScreen and clean-machine acceptance remain explicit release gates.

Earlier implementer RED/GREEN checks also caught and resolved task-local proxy-IP
collision, post-start PG authentication cleanup, secret protection ordering and
provenance metadata filtering. Historical failing outputs remain as evidence;
they are not the final test result. One mistyped focused-test filename produced
pytest collection exit4 before the corrected66-case command; it was not a test
failure or an approval rejection. No safety bypass was used.
