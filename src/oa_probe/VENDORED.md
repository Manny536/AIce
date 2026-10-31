# VENDORED: OA probe (PROPOSED / ONGOING)

Source: cwi-main commit `97064b1` (branch `feat/oa-probe`, local; origin agreeya-org1-scout/CoWork-Inference).

## Upstream sha256 at that commit

- `kakeya_checks/causal.py` `56557f32deaab97a3674148d7c7cf1890ec0221b5babd7c82ac930b524ab207f`
- `kakeya_checks/oa_probe.py` `ac1caec7bc27d192e9897029eb22556668f70c4f85d5fe6b64a90a22a7501cbc`
- `docs/OA_PROBE_PREREG.json` `0bbecb50e7ff3dc27ee1d0b7fb5869ae7ee76043829ed43f746b5dd4ac7a8138`
- `docs/OA_PROBE_RESULTS_v2.json` `8c7e1db61c65bf17b39252725224e3227d9788ca04db7b5b0ae133797c382ace`

## sha256 of the files as vendored here

- `docs/OA_PROBE.md` `c38eaa0915f7c93129f17286c1f017f8aa26d674cce115de519153848d9d6d5e`
- `docs/OA_PROBE_EXPLORATORY_C.json` `e4a3396c80fbfa69ebedaedb42fdedb49955399488befa7d4f3f030ce7b99978`
- `docs/OA_PROBE_PREREG.json` `0bbecb50e7ff3dc27ee1d0b7fb5869ae7ee76043829ed43f746b5dd4ac7a8138`
- `docs/OA_PROBE_RESULTS.json` `7ddef9db43bc8f67023d9e247a3476ed567b4802b4fa2fcf8097f62f13360563`
- `docs/OA_PROBE_RESULTS_v2.json` `8c7e1db61c65bf17b39252725224e3227d9788ca04db7b5b0ae133797c382ace`
- `scripts/oa_experiment.py` `25c873906a169f45b1952231075d9b1a4bd5e0d23c6776c25469eb13b3aa2b59`
- `scripts/oa_mutation_smoke.py` `1ad5fbc11a9e4abd88a2f1442fbabd2b708313a1ffed7e57b36610ab1f0803c9`
- `src/oa_probe/__init__.py` `12590f3fe1cc30f2b5837bda8ef980097587e7d58e293fab3eacd096c6ea0a93`
- `src/oa_probe/causal.py` `f0f8cafe9eacbdd04f51bbfb09cdd545f8434c531d6e8eccce0e379f21efdc92`
- `src/oa_probe/oa_probe.py` `9ccee9e8868a21916f34e186190093e2ce5a25e63270a5895ccbfbdc7f9e18a8`
- `tests/oa_mutants.py` `f8e2f6355f85345c0579bfbd293045cf4f0b7b2cc5ecf7a6186f8da5c30ab946`
- `tests/test_oa_probe.py` `088686009562293cc244e62ff89f9f34e1f855d5a36dc76b849d38435064385f`

Byte-identical to upstream: docs/OA_PROBE_PREREG.json (stored here as docs/OA_PROBE_PREREG.json.gz; decompressed bytes identical), docs/OA_PROBE_RESULTS_v2.json (tests pin the prereg hash and compare outcomes to the committed results).
Changed on vendoring: import paths, test-dir paths, wording for this repo's claim-language lint; causal.py and oa_probe.py otherwise unmodified.

ANALOGY ONLY: the paper (arXiv:2501.02305) is about hash tables, not agents. Nothing here certifies an agent or closes L²_C.

## Pylint follow-up

Each of causal.py and oa_probe.py has one inline pylint pragma added, with a reason (a deliberate (b, a) argument order, and a loop that returns or raises). No logic changed. Current sha256:
- `src/oa_probe/causal.py` `be00b1b9898d44f09fe41e015644efaee10779b3737969ac55f397fe3ffdb100`
- `src/oa_probe/oa_probe.py` `fa0f50ce2fbe6bdf5ab621a79368beaa1be7d58e11e55544be8f62f59543cd84`
