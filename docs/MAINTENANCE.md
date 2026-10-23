# Maintenance policy

The browser edition is the flagship and desktop 2.1 is its native shell. Their scheduling behavior lives in `replanv2-engine.js`; calendar reconciliation lives in `replanv2-calendar.js`; export rendering lives in `replanv2-pdf.js`; UI orchestration lives in `replanv2.js`. Add regression cases to the isolated module tests before changing their contracts.

Flutter 2.2 is a secondary client. Its pure engine is `rplanv2_2/lib/planner.dart`. Common deadline, shared-capacity, completion and availability behavior must pass `test-fixtures/scheduling.json` in both runtimes. Its whole-minute precision and supported settings differ from the browser's hundredth-hour model. Each client owns its backup format and must validate it atomically, including conversion of the other client’s JSON. Preserve calendar plan identity during transfers. Flutter omits missed history and rounds browser durations to whole minutes; browser import rounds workload to hundredths of an hour.

`Replan.ipynb`, `replanex.py`, `replanv0.py`, `replanv1.py`, `replanv1_1.py` and `replanv1_2.py` are archived historical implementations. They remain at their existing paths to preserve references and regression imports. They are not parallel supported releases and should not receive new planner features. Their historical regression tests are retained; their passing status is not a production support promise. Use `requirements-legacy.txt` for their pandas dependency; optional Google packages are documented there.

Root `requirements.txt` routes to the maintained desktop dependencies. Notebook and debugger packages are not application requirements. Flutter application dependency versions are recorded in `pubspec.lock` and enforced in CI. Desktop dependency ranges intentionally permit supported patch updates; record resolved versions when producing a platform release.

No release is ready solely because unit tests pass. Follow `RELEASE_CHECKLIST.md` for live providers, file dialogs, persistent storage and device verification. Do not claim cloud backup, automated mastery inference, mobile validation or open-source licensing before those exist.
