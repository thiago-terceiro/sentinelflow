# SentinelPulse Independent Technical Review: Audit Bundle Manifest

This manifest lists every file included in `sentinelpulse_audit_bundle.zip`, along with its repository origin path, byte size, and cryptographic SHA-256 checksum.

## Archive Summary
- **Archive File:** `sentinelpulse_audit_bundle.zip`
- **Total Files:** 82
- **Repository Head:** `dfdaaf64c2597b1c52b4cce99930e3ea728f96e8`
- **Branch:** `master`

## Manifest Table

| # | Archive Relative Path | Original Repository Path | Size (Bytes) | SHA-256 Checksum |
|:---:|:---|:---|:---:|:---|
| 1 | `audit_artifacts/environment_metadata.json` | `[Generated Audit Artifact: environment_metadata.json]` | 676 | `661abab37ef0b8bb277334c645558eed7537c7b0dd3af6bd9645070bfc7a58fb` |
| 2 | `audit_artifacts/telecom_held_out_eval_dataset_400.json` | `[Generated Audit Artifact: telecom_held_out_eval_dataset_400.json]` | 69,182 | `272d522913386afc74003f1bfa63965577d7c290c6852cb474596757fc5e8db5` |
| 3 | `audit_artifacts/telecom_training_corpus.json` | `[Generated Audit Artifact: telecom_training_corpus.json]` | 100,722 | `8cb5608e5607509d6897f28496c1d43fab2838ec2f4a36f957076a72c40960e1` |
| 4 | `audit_artifacts/onnx_graph_summary.txt` | `[Generated Audit Artifact: onnx_graph_summary.txt]` | 2,071 | `e14e840fbe96f53324815468706225437035c3c013ee6b36999cc55baacf7363` |
| 5 | `audit_artifacts/onnx_parity_verification.txt` | `[Generated Audit Artifact: onnx_parity_verification.txt]` | 848 | `76f2d371f9b269ffd65f9532c575f5c848a19e3a57e272ed593082d1c2d8ac81` |
| 6 | `audit_artifacts/verification_execution_log.json` | `[Generated Audit Artifact: test_verification_results.json]` | 3,568 | `d4d114d5371a87748ad2fc9aaac88b5e1c093c2927c51e0ac24015bf0d928e35` |
| 7 | `sentinelflow/backend/app/telecom/train_onnx_model.py` | `sentinelflow/backend/app/telecom/train_onnx_model.py` | 26,009 | `6564ef3bf9f6ef43da6494a87bd577fed9ad3ff799aa502b51541dab55c3d8b8` |
| 8 | `sentinelflow/backend/app/telecom/evaluate_model.py` | `sentinelflow/backend/app/telecom/evaluate_model.py` | 33,217 | `34ca860d26f36a3db469d090fb06d2bb3030e3cd9baec146498a601fc4bd9cec` |
| 9 | `sentinelflow/backend/app/telecom/ml_metrics.json` | `sentinelflow/backend/app/telecom/ml_metrics.json` | 5,872 | `cd71eb0b0123233e54580633d0b2823a2988a52176f9b6acb186e76fcce2155b` |
| 10 | `sentinelflow/backend/app/telecom/models/sms_fraud_model.onnx` | `sentinelflow/backend/app/telecom/models/sms_fraud_model.onnx` | 185,436 | `91576d807d4df180efdfea7b1c94dd220c85b13e870b6bb082fad1d2ce7d7b93` |
| 11 | `sentinelflow/backend/app/telecom/models/sms_fraud_metadata.json` | `sentinelflow/backend/app/telecom/models/sms_fraud_metadata.json` | 4,133 | `f63676dabe5e42615bec43bd0abb6e19590ec99e882de116bd13292c15c483de` |
| 12 | `sentinelflow/backend/app/telecom/onnx_engine.py` | `sentinelflow/backend/app/telecom/onnx_engine.py` | 16,907 | `8e8e6886960a101acf024133ff35d9d6b9ea8c8afa12a6c5e6503e2a4f120467` |
| 13 | `sentinelflow/backend/app/telecom/velocity_store.py` | `sentinelflow/backend/app/telecom/velocity_store.py` | 16,630 | `17826893d998ea8b2f5d129344ae368d52ccb08326944beedf6667392b366fe8` |
| 14 | `sentinelflow/backend/app/telecom/drift_monitor.py` | `sentinelflow/backend/app/telecom/drift_monitor.py` | 11,856 | `66f8ece64b7097d54a6aa6a860dd0182523674f345d84542f89f6961509278fb` |
| 15 | `sentinelflow/backend/app/telecom/telecom_metrics.py` | `sentinelflow/backend/app/telecom/telecom_metrics.py` | 6,826 | `fbea76d738bf871849b0fa3839101cdb09a4e543a9d6f55781952e20e712ff1e` |
| 16 | `sentinelflow/backend/scripts/benchmark_pulse.py` | `sentinelflow/backend/scripts/benchmark_pulse.py` | 29,056 | `73a30efb6ae31857bf74400d9a85a948559ba98e74c3a2948249431283e069d1` |
| 17 | `sentinelflow/backend/app/api/telecom.py` | `sentinelflow/backend/app/api/telecom.py` | 31,020 | `b7d8994375b301ea2242fdf57925c0dcfb5d80f03068ed3e75dea5f94a9543ae` |
| 18 | `sentinelflow/backend/app/api/approvals.py` | `sentinelflow/backend/app/api/approvals.py` | 3,111 | `a7642fcf3d5dc4459ab1f4a4f2ab2f9331852156230c3fbf566d3eea7aa4e303` |
| 19 | `sentinelflow/backend/app/api/disputes.py` | `sentinelflow/backend/app/api/disputes.py` | 16,168 | `6e0b262ac3ef3b9f791f9f711cb4f59e9463153bbbaf821c89c7252d49fbf9db` |
| 20 | `sentinelflow/backend/app/api/health.py` | `sentinelflow/backend/app/api/health.py` | 3,739 | `953f257f5b38957b1989abbb443c65c6296a96274575d619de4ecdfee991d77d` |
| 21 | `sentinelflow/backend/app/worker.py` | `sentinelflow/backend/app/worker.py` | 1,701 | `ef59b6c47a7b5371e275e3daabd0f2ff54835a6fd5962e28b62b61fe63c156a8` |
| 22 | `sentinelflow/backend/app/worker_server.py` | `sentinelflow/backend/app/worker_server.py` | 1,557 | `039f1e20dde083091d17244be7bf4f99eed6e61ce5bd6d98f2c98bf5866bfb8a` |
| 23 | `sentinelflow/backend/app/config.py` | `sentinelflow/backend/app/config.py` | 4,788 | `165a232a2934385e38cedcc13b0900736d89b0f60727de2d1e01fc1ea23b0a35` |
| 24 | `sentinelflow/backend/app/main.py` | `sentinelflow/backend/app/main.py` | 3,461 | `87c8d60fa1203ab51c39e6017b0dc646026f09c62c12f93cb056dde81722337e` |
| 25 | `sentinelflow/backend/app/security.py` | `sentinelflow/backend/app/security.py` | 8,591 | `ba989b3f63e451469da67fa58f1695da7f1d8d701766ed20a0417053b871e586` |
| 26 | `sentinelflow/backend/app/graph/graph.py` | `sentinelflow/backend/app/graph/graph.py` | 5,225 | `b72c9e5128ff88ccbaf75ec721af8fdb815b7d640bd9ef1709ef7bed9d491d52` |
| 27 | `sentinelflow/backend/app/graph/nodes.py` | `sentinelflow/backend/app/graph/nodes.py` | 49,156 | `c7bbea2a2a986307cab31f1a80c62e544cf3b79da01b4b1e87251de6c9b63294` |
| 28 | `sentinelflow/backend/app/graph/state.py` | `sentinelflow/backend/app/graph/state.py` | 1,514 | `8fc3a71fb9f88c7e356a6b0be8bd3e1741d853f97656e13214336f9c975a53b4` |
| 29 | `sentinelflow/backend/app/graph/routing.py` | `sentinelflow/backend/app/graph/routing.py` | 1,242 | `ba05e1ad8b6743fc5a16a379f8a5df31e7fa5e69bb72ad1d81e1acfebd4a8919` |
| 30 | `sentinelflow/backend/app/graph/prompts.py` | `sentinelflow/backend/app/graph/prompts.py` | 1,154 | `489b77c0abfe0a019b3341c2c4b745ecf7850b9cd94f991546ab4fb8c9c38461` |
| 31 | `sentinelflow/backend/app/services/investigations.py` | `sentinelflow/backend/app/services/investigations.py` | 43,276 | `cd96714db094e948f7cf5768ef59e8356adb89d9671edab08a9c4c5947f90d8b` |
| 32 | `sentinelflow/backend/app/services/risk.py` | `sentinelflow/backend/app/services/risk.py` | 4,555 | `cbfc2c41b8a0d631705504788f00b18148ca7e1a42f206c8cab8bb94f8be3d95` |
| 33 | `sentinelflow/backend/app/services/trace_safety.py` | `sentinelflow/backend/app/services/trace_safety.py` | 7,445 | `cffc2146cd5bf88b6fd4326c6b016446c1e80380326f093e2acda6e838446391` |
| 34 | `sentinelflow/backend/app/db/models.py` | `sentinelflow/backend/app/db/models.py` | 4,750 | `c496f6d54e29c9b77ca13505419e2ae5c4ea269732c3774f496e079827c2542d` |
| 35 | `sentinelflow/backend/app/db/session.py` | `sentinelflow/backend/app/db/session.py` | 806 | `ef10022b3d8e8d8c13d364c8252116caa63e9ec37ca23817df08db736a87eac5` |
| 36 | `sentinelflow/docker-compose.yml` | `sentinelflow/docker-compose.yml` | 6,858 | `58acb48ebbf19eb4848bf2c51c56749cad20e35e283a0dd2157ef47a262088f3` |
| 37 | `sentinelflow/docker-compose.prod.yml` | `sentinelflow/docker-compose.prod.yml` | 2,579 | `83c6b7c6aca7f980f3ba542f37dd1029bf64d47e4da9f944ee1cd83d18ea7179` |
| 38 | `sentinelflow/backend/Dockerfile` | `sentinelflow/backend/Dockerfile` | 696 | `ea77005fc8edeedb571f18285f3a62f07405af6cf0e1b2c7541bea7fd3e8c565` |
| 39 | `sentinelflow/backend/pyproject.toml` | `sentinelflow/backend/pyproject.toml` | 2,405 | `6f4e9b9691962545747f1f9558941a94d8d19a7ca3a0f7529ff73aebbd527cb4` |
| 40 | `sentinelflow/backend/app/tests/test_telecom_gateway.py` | `sentinelflow/backend/app/tests/test_telecom_gateway.py` | 30,822 | `7d3c3af0f46769bdcf7fd961e465e2ae0aed1bbfb346c4cb0317a041b23c0083` |
| 41 | `sentinelflow/backend/app/tests/test_ai_first_protocols.py` | `sentinelflow/backend/app/tests/test_ai_first_protocols.py` | 8,476 | `82c7f4d64382aff091810ab39112da478889e5366d1a3072216f85bc10a713e6` |
| 42 | `sentinelflow/backend/app/tests/test_approvals.py` | `sentinelflow/backend/app/tests/test_approvals.py` | 5,634 | `a4902e0b086b6c0d1edc1a2df89459bdbd3bb13ede47dfc2dd49f90da64d5cd0` |
| 43 | `sentinelflow/backend/app/tests/test_audit_artifacts.py` | `sentinelflow/backend/app/tests/test_audit_artifacts.py` | 5,963 | `0355842cfd4eef809f25682a757c9232ffa55d1da6a5047f0510fd38a61575fb` |
| 44 | `sentinelflow/backend/app/tests/test_audit_export.py` | `sentinelflow/backend/app/tests/test_audit_export.py` | 6,577 | `0d49bf37c35666646d7ee1adb22df0cf4aa5b4b07452a1668248aff2af7b1846` |
| 45 | `sentinelflow/backend/app/tests/test_audit_integrity.py` | `sentinelflow/backend/app/tests/test_audit_integrity.py` | 9,770 | `a66cb605245afa33308126701ece714294016170398144831975b2731b56b0eb` |
| 46 | `sentinelflow/backend/app/tests/test_audit_projection.py` | `sentinelflow/backend/app/tests/test_audit_projection.py` | 2,006 | `ad7dd955b12fee3294ec8f0224524332f9a25964e8a0c7de9acce6adb01e713b` |
| 47 | `sentinelflow/backend/app/tests/test_database_integration.py` | `sentinelflow/backend/app/tests/test_database_integration.py` | 25,001 | `5a6531b668ffb219a53b697a8fca5b5524902e69b1353fd0d675cc07d99edbe4` |
| 48 | `sentinelflow/backend/app/tests/test_evals.py` | `sentinelflow/backend/app/tests/test_evals.py` | 5,756 | `38bd344765080d083dbca701d439aeb543db21381876eb371539d299ab6dc1d9` |
| 49 | `sentinelflow/backend/app/tests/test_graph_compile.py` | `sentinelflow/backend/app/tests/test_graph_compile.py` | 6,591 | `13a014e509bbcf110d93bda96890b3e817581a4f5cc88a7882a375caa7b100bc` |
| 50 | `sentinelflow/backend/app/tests/test_graph_nodes.py` | `sentinelflow/backend/app/tests/test_graph_nodes.py` | 12,253 | `f9a8dd4452e24438e44aca67c2a631438d321654207da39e8682aaf24dbe3fb7` |
| 51 | `sentinelflow/backend/app/tests/test_guardrails.py` | `sentinelflow/backend/app/tests/test_guardrails.py` | 6,515 | `970fa9fe30c621d5580c8a9098e821f4d8c4e0bf50dd4f192e39696ca750e730` |
| 52 | `sentinelflow/backend/app/tests/test_health_readiness.py` | `sentinelflow/backend/app/tests/test_health_readiness.py` | 5,788 | `43db40c9f89b0be462dd9957a4b9265cbd91a50c287697cf1fd8e6bbfcc1920b` |
| 53 | `sentinelflow/backend/app/tests/test_investigation_service.py` | `sentinelflow/backend/app/tests/test_investigation_service.py` | 45,019 | `2bb174a4882112424f130d684a2ee952aba0e4259bebcf60cb015fa12eb9aa97` |
| 54 | `sentinelflow/backend/app/tests/test_migrations.py` | `sentinelflow/backend/app/tests/test_migrations.py` | 1,440 | `d643b80ac929b05ea7a10e0b60074e64c6689658715bc30a729037163bff37e8` |
| 55 | `sentinelflow/backend/app/tests/test_risk.py` | `sentinelflow/backend/app/tests/test_risk.py` | 1,074 | `c1eadb4faf3c564bce76a9cf38433212abc391bb491ce8229d3f81503d5bc1c5` |
| 56 | `sentinelflow/backend/app/tests/test_security.py` | `sentinelflow/backend/app/tests/test_security.py` | 6,674 | `121052c09d0ecefbcdcebf3426bc501f89a763cbd9970efc9bd3f0774d663fea` |
| 57 | `sentinelflow/backend/app/tests/test_trace_safety.py` | `sentinelflow/backend/app/tests/test_trace_safety.py` | 3,406 | `a7c1182506c7576978e5865262518ef724a6dfb012c5c8fd53e108b78a8708b4` |
| 58 | `sentinelflow/frontend/package.json` | `sentinelflow/frontend/package.json` | 1,141 | `0745ca34f56c0ce898ca13bd86afedd80b150daf64e57ec5302e2c9696962e4d` |
| 59 | `sentinelflow/frontend/tsconfig.json` | `sentinelflow/frontend/tsconfig.json` | 691 | `f3ed79b53d8d812b496c9ebac98b5638b7a839a5910e7353ffb22a0429b792fd` |
| 60 | `sentinelflow/frontend/playwright.config.ts` | `sentinelflow/frontend/playwright.config.ts` | 711 | `c06d3f151d767a0fb2d36d2f38cc824949c28548e8d78e433b00c67263c7fd76` |
| 61 | `sentinelflow/frontend/scripts/test-a11y-aaa.mjs` | `sentinelflow/frontend/scripts/test-a11y-aaa.mjs` | 10,121 | `b635376d3302a733431182b875925036e5ad34010ec3367960ebcb7bd0bfc260` |
| 62 | `sentinelflow/frontend/scripts/check-rules.js` | `sentinelflow/frontend/scripts/check-rules.js` | 2,313 | `5f75b31a7bf9b2d18d5b4b9b14b7fed4572a50dfd0753035b908ebce1f88622d` |
| 63 | `sentinelflow/frontend/tests/auth-routes.test.js` | `sentinelflow/frontend/tests/auth-routes.test.js` | 5,022 | `e9cc15a61f36eed75a0919ed9c16d79bde35ebc4d9550dd560f44fe0a653599d` |
| 64 | `sentinelflow/frontend/tests/background-patterns.test.js` | `sentinelflow/frontend/tests/background-patterns.test.js` | 3,000 | `c065f437c063f3d49ea46640c67eb57b3042d652fe44ff92cdd70d8929746e57` |
| 65 | `sentinelflow/frontend/tests/geo.test.js` | `sentinelflow/frontend/tests/geo.test.js` | 3,546 | `050ed5488f956d92f05d8ceb5469e295464b1ee5f46f3bdff480f9d18a9ee06d` |
| 66 | `sentinelflow/frontend/tests/investigation-state.test.js` | `sentinelflow/frontend/tests/investigation-state.test.js` | 16,857 | `605f83db2e00dea693b25b774432385054f4f0fb91a78ae2eec4aef155656932` |
| 67 | `sentinelflow/frontend/tests/oidc.test.js` | `sentinelflow/frontend/tests/oidc.test.js` | 694 | `4964e4d8aa03efe074ba9b9ecaa1792969ae9a882909b84dcb0b3a899b76028a` |
| 68 | `sentinelflow/frontend/tests/placeholder.test.js` | `sentinelflow/frontend/tests/placeholder.test.js` | 3,513 | `33620186b79c9dbef52945dc327f15ef8dc5de75519da8ba6c14d24658d45699` |
| 69 | `sentinelflow/frontend/tests/sse.test.js` | `sentinelflow/frontend/tests/sse.test.js` | 6,208 | `3766f860ec32e249a0dc54eeeedf63e857fdb00820d0e2549f1ac869e28b16fc` |
| 70 | `sentinelflow/frontend/tests/stream-cleanup-and-selectors.test.js` | `sentinelflow/frontend/tests/stream-cleanup-and-selectors.test.js` | 4,892 | `217e35378bfe0a609d70638d882a7124548123ce6b89a79a37067525496c048e` |
| 71 | `README.md` | `README.md` | 3,440 | `516e07cbee9950c36a7019fbe773bde9cd32fa1b8c6d1f7196b7af763e5dc040` |
| 72 | `SYSTEM_DESIGN.md` | `SYSTEM_DESIGN.md` | 22,788 | `7e475c4c0be19f96d5270c5099065c37e2a7aedf0e4ab28eb4547300e9d9fea0` |
| 73 | `OVERVIEW.md` | `OVERVIEW.md` | 10,703 | `f8b8f1df5708d63450957868593efefbc3b7dbc333d6edfb7faec0e1ac0f76fa` |
| 74 | `PROJECT_CONTEXT.md` | `PROJECT_CONTEXT.md` | 16,920 | `43c367c6220fc97477f170b0be905240d2fbd1ec26b10aeee4b2d96f5bc67ce5` |
| 75 | `docs/architecture.md` | `docs/architecture.md` | 30,159 | `0b5e3a89dace80b474d405f97a4e4d712de07d37cd6cced936cd9b0da0594e42` |
| 76 | `docs/architecture-review.md` | `docs/architecture-review.md` | 58,836 | `85e45e4d8b47c5ee6c094aca113b5fd2357cf92811d25d790ea2134c081ba824` |
| 77 | `docs/cloud-deploy-options.md` | `docs/cloud-deploy-options.md` | 4,905 | `f6fe04a3152d31431f92c63187615497c7d1935dea3d5c5ec2380cb89f648b84` |
| 78 | `docs/ml_evaluation_report.md` | `docs/ml_evaluation_report.md` | 8,075 | `4d78ff3ea745cca61f4e21054ac8aa3ebb52da47b82ffc50253b3f4753aa7c49` |
| 79 | `sentinelflow/README.md` | `sentinelflow/README.md` | 15,904 | `3b5364c4c3e38164178258f289ce319f9628ddfba9b01930d1315750dadd4e3d` |
| 80 | `sentinelflow/SYSTEM_DESIGN.md` | `sentinelflow/SYSTEM_DESIGN.md` | 22,788 | `7e475c4c0be19f96d5270c5099065c37e2a7aedf0e4ab28eb4547300e9d9fea0` |
| 81 | `sentinelflow/OVERVIEW.md` | `sentinelflow/OVERVIEW.md` | 10,703 | `f8b8f1df5708d63450957868593efefbc3b7dbc333d6edfb7faec0e1ac0f76fa` |
| 82 | `sentinelflow/docs/ml_evaluation_report.md` | `sentinelflow/docs/ml_evaluation_report.md` | 8,075 | `4d78ff3ea745cca61f4e21054ac8aa3ebb52da47b82ffc50253b3f4753aa7c49` |
