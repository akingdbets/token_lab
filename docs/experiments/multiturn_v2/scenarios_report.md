# multiturn-v2 샘플 점검

자동 생성: `python src/multiturn/scenario_report.py` (API 호출 없음).

생성 프롬프트: v2_01_auth_switch `mt_scenario_gen_v2`, v2_02_response_design `mt_scenario_gen_v2`, v2_03_input_validation `mt_scenario_gen_v3`, v2_04_dependency_lifecycle `mt_scenario_gen_v3`, v2_05_deployment_setup `mt_scenario_gen_v3`, v2_06_middleware_cors `mt_scenario_gen_v3`, v2_07_streaming_realtime `mt_scenario_gen_v3`, v2_08_model_serialization `mt_scenario_gen_v3`, v2_09_openapi_docs `mt_scenario_gen_v3`, v2_10_app_structure `mt_scenario_gen_v3`, v2_11_testing_strategy `mt_scenario_gen_v3`, v2_12_database `mt_scenario_gen_v3`, v2_13_error_consistency `mt_scenario_gen_v3`, v2_14_files_forms_static `mt_scenario_gen_v3`, v2_15_settings_env `mt_scenario_gen_v3`, v2_16_scopes_user_model `mt_scenario_gen_v3`, v2_17_request_internals `mt_scenario_gen_v3`, v2_18_integrations `mt_scenario_gen_v3`, v2_19_first_service `mt_scenario_gen_v3`, v2_20_client_contract `mt_scenario_gen_v3`

## 요약

| 시나리오 | 턴 | new/followup/recall/synthesis/update/same_doc | recall 거리 | 마지막 턴 기록 | recall·synthesis 중 user | setup 항목 | knowledge 맞힘 | grounded 맞힘 | 생성 시도 | 손 수정 |
|---|---|---|---|---|---|---|---|---|---|---|
| v2_01_auth_switch | 19 | 8/2/3/2/2/2 | 6, 15, 7 | 18,186 | 5/12 (42%) | 6/41 | 7/19 (37%) | 0/19 (0%) | 2 | 예 |
| v2_02_response_design | 20 | 9/2/3/2/2/2 | 8, 12, 16 | 20,782 | 5/12 (42%) | 4/40 | 6/20 (30%) | 0/20 (0%) | 2 | 예 |
| v2_03_input_validation | 19 | 8/2/3/2/2/2 | 9, 8, 16 | 19,599 | 5/12 (42%) | 5/41 | 10/19 (53%) | 1/19 (5%) | 2 |  |
| v2_04_dependency_lifecycle | 19 | 8/2/3/2/2/2 | 8, 16, 12 | 17,418 | 5/12 (42%) | 6/41 | 10/19 (53%) | 2/19 (11%) | 1 |  |
| v2_05_deployment_setup | 19 | 8/2/3/2/2/2 | 9, 12, 12 | 16,693 | 6/12 (50%) | 5/42 | 9/19 (47%) | 1/19 (5%) | 2 |  |
| v2_06_middleware_cors | 19 | 8/2/3/2/2/2 | 9, 15, 15 | 17,690 | 5/12 (42%) | 5/43 | 7/19 (37%) | 0/19 (0%) | 2 |  |
| v2_07_streaming_realtime | 19 | 8/2/3/2/2/2 | 9, 15, 17 | 17,457 | 6/12 (50%) | 5/39 | 9/19 (47%) | 2/19 (11%) | 1 |  |
| v2_08_model_serialization | 19 | 8/2/3/2/2/2 | 9, 16, 9 | 19,509 | 5/13 (38%) | 6/41 | 10/19 (53%) | 1/19 (5%) | 2 |  |
| v2_09_openapi_docs | 19 | 8/2/3/2/2/2 | 9, 13, 16 | 18,668 | 6/12 (50%) | 4/40 | 7/19 (37%) | 1/19 (5%) | 2 |  |
| v2_10_app_structure | 19 | 8/2/3/2/2/2 | 7, 16, 6 | 19,664 | 6/12 (50%) | 5/40 | 9/19 (47%) | 0/19 (0%) | 1 |  |
| v2_11_testing_strategy | 19 | 8/2/3/2/2/2 | 9, 16, 14 | 17,203 | 5/12 (42%) | 4/41 | 9/19 (47%) | 1/19 (5%) | 2 |  |
| v2_12_database | 19 | 8/2/3/2/2/2 | 9, 6, 9 | 19,326 | 5/14 (36%) | 5/44 | 11/19 (58%) | 2/19 (11%) | 1 |  |
| v2_13_error_consistency | 19 | 8/2/3/2/2/2 | 9, 15, 7 | 21,275 | 6/12 (50%) | 6/40 | 11/19 (58%) | 0/19 (0%) | 2 |  |
| v2_14_files_forms_static | 19 | 8/2/3/2/2/2 | 9, 8, 6 | 18,813 | 6/12 (50%) | 6/41 | 4/19 (21%) | 0/19 (0%) | 2 |  |
| v2_15_settings_env | 19 | 8/2/3/2/2/2 | 9, 16, 5 | 17,348 | 5/12 (42%) | 4/41 | 11/19 (58%) | 0/19 (0%) | 1 |  |
| v2_16_scopes_user_model | 19 | 8/2/3/2/2/2 | 9, 6, 14 | 20,626 | 5/12 (42%) | 6/39 | 9/19 (47%) | 3/19 (16%) | 1 |  |
| v2_17_request_internals | 19 | 8/2/3/2/2/2 | 8, 12, 7 | 16,675 | 5/12 (42%) | 4/42 | 9/19 (47%) | 1/19 (5%) | 1 |  |
| v2_18_integrations | 19 | 8/2/3/2/2/2 | 8, 16, 12 | 16,972 | 5/12 (42%) | 6/40 | 11/19 (58%) | 2/19 (11%) | 2 |  |
| v2_19_first_service | 19 | 8/2/3/2/2/2 | 8, 11, 13 | 19,230 | 5/12 (42%) | 5/40 | 7/19 (37%) | 0/19 (0%) | 2 |  |
| v2_20_client_contract | 19 | 8/2/3/2/2/2 | 9, 15, 6 | 18,322 | 5/12 (42%) | 5/39 | 9/19 (47%) | 1/19 (5%) | 1 |  |
| **전체** | 381 | | | | | 102/815 | **175/381 (46%)** | **18/381 (5%)** | | |

knowledge·grounded 맞힘은 setup 을 뺀 key_fact 가 모두 충족된 턴 (accuracy_main = 1.0).

## grounded 에서 정답 일부라도 낸 턴 (기억으로 답함)

| 시나리오 | 턴 | 유형 | 정확도 (setup 제외) |
|---|---|---|---|
| v2_03_input_validation | 4 | update | 1.00 |
| v2_03_input_validation | 7 | same_doc_new_topic | 0.50 |
| v2_04_dependency_lifecycle | 2 | followup | 1.00 |
| v2_04_dependency_lifecycle | 10 | new | 1.00 |
| v2_04_dependency_lifecycle | 15 | new | 0.50 |
| v2_05_deployment_setup | 6 | followup | 1.00 |
| v2_07_streaming_realtime | 6 | followup | 1.00 |
| v2_07_streaming_realtime | 14 | same_doc_new_topic | 1.00 |
| v2_08_model_serialization | 6 | followup | 1.00 |
| v2_09_openapi_docs | 5 | new | 1.00 |
| v2_09_openapi_docs | 7 | same_doc_new_topic | 0.50 |
| v2_11_testing_strategy | 7 | same_doc_new_topic | 1.00 |
| v2_12_database | 1 | new | 1.00 |
| v2_12_database | 17 | recall | 1.00 |
| v2_16_scopes_user_model | 7 | same_doc_new_topic | 1.00 |
| v2_16_scopes_user_model | 11 | update | 1.00 |
| v2_16_scopes_user_model | 14 | same_doc_new_topic | 1.00 |
| v2_17_request_internals | 1 | new | 1.00 |
| v2_18_integrations | 1 | new | 1.00 |
| v2_18_integrations | 6 | followup | 1.00 |
| v2_20_client_contract | 14 | same_doc_new_topic | 1.00 |

## 검수 때 먼저 볼 의심 턴 (자동 점검)

| 시나리오 | 턴 | 유형 | 사유 |
|---|---|---|---|
| v2_01_auth_switch | 5 | new | 정답이 열려 있을 수 있음: fact 1 'suitable' |
| v2_01_auth_switch | 11 | update | 정답이 열려 있을 수 있음: fact 1 'suitable' |
| v2_01_auth_switch | 12 | new | 정답이 열려 있을 수 있음: fact 1 'suitable' |
| v2_01_auth_switch | 16 | recall | 턴 2 의존은 간접 채점 (턴 2 가 인용한 페이지만 같음) |
| v2_01_auth_switch | 18 | synthesis | 대안 판정 확인 (alt_judge_label) |
| v2_02_response_design | 3 | new | 근거 인용이 짧음: fact 0 '    <shampoo>' |
| v2_02_response_design | 4 | update | 턴 2 의존은 간접 채점 (턴 2 가 인용한 페이지만 같음) |
| v2_02_response_design | 9 | recall | 턴 2 의존은 간접 채점 (턴 2 가 인용한 페이지만 같음) |
| v2_02_response_design | 11 | update | 턴 2 의존은 간접 채점 (턴 2 가 인용한 페이지만 같음) |
| v2_02_response_design | 18 | recall | 턴 2 의존은 간접 채점 (턴 2 가 인용한 페이지만 같음) |
| v2_03_input_validation | 4 | update | grounded 에서 기억으로 답함 (정확도 1.00) |
| v2_03_input_validation | 7 | same_doc_new_topic | grounded 에서 기억으로 답함 (정확도 0.50) |
| v2_03_input_validation | 12 | new | 근거 인용이 짧음: fact 1 '                "normal": {' |
| v2_04_dependency_lifecycle | 2 | followup | grounded 에서 기억으로 답함 (정확도 1.00) |
| v2_04_dependency_lifecycle | 10 | new | 물음표 3개; grounded 에서 기억으로 답함 (정확도 1.00) |
| v2_04_dependency_lifecycle | 11 | update | 턴 3 의존은 setup 항목으로만 채점 |
| v2_04_dependency_lifecycle | 15 | new | grounded 에서 기억으로 답함 (정확도 0.50) |
| v2_04_dependency_lifecycle | 17 | recall | 턴 6 의존은 간접 채점 (턴 6 가 인용한 페이지만 같음) |
| v2_05_deployment_setup | 3 | new | 정답이 열려 있을 수 있음: fact 2 'appropriate' |
| v2_05_deployment_setup | 6 | followup | grounded 에서 기억으로 답함 (정확도 1.00) |
| v2_06_middleware_cors | 4 | update | 턴 2 의존은 간접 채점 (턴 2 가 인용한 페이지만 같음) |
| v2_06_middleware_cors | 8 | new | 정답이 열려 있을 수 있음: fact 1 'appropriate' |
| v2_07_streaming_realtime | 6 | followup | grounded 에서 기억으로 답함 (정확도 1.00) |
| v2_07_streaming_realtime | 14 | same_doc_new_topic | grounded 에서 기억으로 답함 (정확도 1.00) |
| v2_07_streaming_realtime | 18 | synthesis | 턴 6 의존은 간접 채점 (턴 6 가 인용한 페이지만 같음) |
| v2_08_model_serialization | 4 | update | 턴 2 의존은 간접 채점 (턴 2 가 인용한 페이지만 같음) |
| v2_08_model_serialization | 6 | followup | grounded 에서 기억으로 답함 (정확도 1.00) |
| v2_08_model_serialization | 17 | recall | recall·synthesis 인데 knowledge 로 맞힘 |
| v2_09_openapi_docs | 4 | update | 턴 0 의존은 setup 항목으로만 채점 |
| v2_09_openapi_docs | 5 | new | grounded 에서 기억으로 답함 (정확도 1.00) |
| v2_09_openapi_docs | 7 | same_doc_new_topic | grounded 에서 기억으로 답함 (정확도 0.50) |
| v2_09_openapi_docs | 13 | synthesis | 턴 7 의존은 간접 채점 (턴 7 가 인용한 페이지만 같음) |
| v2_11_testing_strategy | 2 | followup | 대안 판정 확인 (alt_judge_label) |
| v2_11_testing_strategy | 7 | same_doc_new_topic | grounded 에서 기억으로 답함 (정확도 1.00) |
| v2_11_testing_strategy | 18 | synthesis | 턴 14 의존은 간접 채점 (턴 14 가 인용한 페이지만 같음) |
| v2_12_database | 1 | new | grounded 에서 기억으로 답함 (정확도 1.00) |
| v2_12_database | 17 | recall | grounded 에서 기억으로 답함 (정확도 1.00); recall·synthesis 인데 knowledge 로 맞힘 |
| v2_13_error_consistency | 17 | recall | recall·synthesis 인데 knowledge 로 맞힘 |
| v2_15_settings_env | 0 | new | 근거 인용이 짧음: fact 2 '@lru_cache' |
| v2_15_settings_env | 12 | new | 대안 판정 확인 (alt_judge_label) |
| v2_15_settings_env | 16 | recall | 턴 7 의존은 간접 채점 (턴 7 가 인용한 페이지만 같음) |
| v2_15_settings_env | 18 | synthesis | 턴 14 의존은 간접 채점 (턴 14 가 인용한 페이지만 같음) |
| v2_16_scopes_user_model | 7 | same_doc_new_topic | grounded 에서 기억으로 답함 (정확도 1.00) |
| v2_16_scopes_user_model | 11 | update | grounded 에서 기억으로 답함 (정확도 1.00) |
| v2_16_scopes_user_model | 14 | same_doc_new_topic | grounded 에서 기억으로 답함 (정확도 1.00) |
| v2_17_request_internals | 1 | new | grounded 에서 기억으로 답함 (정확도 1.00) |
| v2_17_request_internals | 17 | recall | recall·synthesis 인데 knowledge 로 맞힘 |
| v2_17_request_internals | 18 | synthesis | 턴 14 의존은 간접 채점 (턴 14 가 인용한 페이지만 같음) |
| v2_18_integrations | 1 | new | grounded 에서 기억으로 답함 (정확도 1.00) |
| v2_18_integrations | 6 | followup | grounded 에서 기억으로 답함 (정확도 1.00) |
| v2_18_integrations | 13 | synthesis | 턴 7 의존은 간접 채점 (턴 7 가 인용한 페이지만 같음) |
| v2_18_integrations | 18 | synthesis | 턴 7 의존은 간접 채점 (턴 7 가 인용한 페이지만 같음) |
| v2_19_first_service | 11 | update | 턴 1 의존은 setup 항목으로만 채점 |
| v2_19_first_service | 13 | synthesis | 턴 2 의존은 간접 채점 (턴 2 가 인용한 페이지만 같음); 턴 6 의존은 간접 채점 (턴 6 가 인용한 페이지만 같음) |
| v2_20_client_contract | 14 | same_doc_new_topic | grounded 에서 기억으로 답함 (정확도 1.00) |
| v2_20_client_contract | 18 | synthesis | 턴 7 의존은 간접 채점 (턴 7 가 인용한 페이지만 같음) |

## 턴 유형 분포와 기록

| 시나리오 | 턴 | new | followup | recall | synthesis | update | same_doc | recall 거리 | 3턴 이상 synthesis | 마지막 턴 기록 | 스키마 오류 | 근거 확인 실패 | 경고 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v2_01_auth_switch | 19 | 8 | 2 | 3 | 2 | 2 | 2 | 6, 15, 7 | 턴 13, 18 | 18,186 | 0 | 0 | 1 |
| v2_02_response_design | 20 | 9 | 2 | 3 | 2 | 2 | 2 | 8, 12, 16 | 턴 13, 19 | 20,782 | 0 | 0 | 0 |
| v2_03_input_validation | 19 | 8 | 2 | 3 | 2 | 2 | 2 | 9, 8, 16 | 턴 13, 18 | 19,599 | 0 | 0 | 0 |
| v2_04_dependency_lifecycle | 19 | 8 | 2 | 3 | 2 | 2 | 2 | 8, 16, 12 | 턴 13, 18 | 17,418 | 0 | 1 | 0 |
| v2_05_deployment_setup | 19 | 8 | 2 | 3 | 2 | 2 | 2 | 9, 12, 12 | 턴 13 | 16,693 | 0 | 5 | 1 |
| v2_06_middleware_cors | 19 | 8 | 2 | 3 | 2 | 2 | 2 | 9, 15, 15 | 턴 13, 18 | 17,690 | 0 | 7 | 0 |
| v2_07_streaming_realtime | 19 | 8 | 2 | 3 | 2 | 2 | 2 | 9, 15, 17 | 턴 13, 18 | 17,457 | 0 | 4 | 0 |
| v2_08_model_serialization | 19 | 8 | 2 | 3 | 2 | 2 | 2 | 9, 16, 9 | 턴 13, 18 | 19,509 | 0 | 1 | 0 |
| v2_09_openapi_docs | 19 | 8 | 2 | 3 | 2 | 2 | 2 | 9, 13, 16 | 턴 13, 18 | 18,668 | 0 | 2 | 0 |
| v2_10_app_structure | 19 | 8 | 2 | 3 | 2 | 2 | 2 | 7, 16, 6 | 턴 13, 18 | 19,664 | 0 | 0 | 1 |
| v2_11_testing_strategy | 19 | 8 | 2 | 3 | 2 | 2 | 2 | 9, 16, 14 | 턴 13, 18 | 17,203 | 1 | 1 | 1 |
| v2_12_database | 19 | 8 | 2 | 3 | 2 | 2 | 2 | 9, 6, 9 | 턴 13, 18 | 19,326 | 0 | 2 | 1 |
| v2_13_error_consistency | 19 | 8 | 2 | 3 | 2 | 2 | 2 | 9, 15, 7 | 턴 13, 18 | 21,275 | 0 | 2 | 1 |
| v2_14_files_forms_static | 19 | 8 | 2 | 3 | 2 | 2 | 2 | 9, 8, 6 | 턴 13, 18 | 18,813 | 0 | 5 | 0 |
| v2_15_settings_env | 19 | 8 | 2 | 3 | 2 | 2 | 2 | 9, 16, 5 | 턴 13, 18 | 17,348 | 0 | 0 | 1 |
| v2_16_scopes_user_model | 19 | 8 | 2 | 3 | 2 | 2 | 2 | 9, 6, 14 | 턴 13 | 20,626 | 0 | 0 | 0 |
| v2_17_request_internals | 19 | 8 | 2 | 3 | 2 | 2 | 2 | 8, 12, 7 | 턴 13, 18 | 16,675 | 0 | 5 | 0 |
| v2_18_integrations | 19 | 8 | 2 | 3 | 2 | 2 | 2 | 8, 16, 12 | 턴 13, 18 | 16,972 | 0 | 3 | 1 |
| v2_19_first_service | 19 | 8 | 2 | 3 | 2 | 2 | 2 | 8, 11, 13 | 턴 13, 18 | 19,230 | 0 | 6 | 1 |
| v2_20_client_contract | 19 | 8 | 2 | 3 | 2 | 2 | 2 | 9, 15, 6 | 턴 13, 18 | 18,322 | 0 | 2 | 0 |

스키마 오류·근거 확인 실패·경고 내용:

- v2_01_auth_switch 턴 12: 서로 다른 주제 폴더의 문서 ['security/oauth2-scopes.md', 'errors/handling-errors.md'] 를 한 턴에 붙였습니다 (경고)
- v2_04_dependency_lifecycle 턴 7: key_entity '__init__' 가 근거 페이지·사용자 발화에 없음
- v2_05_deployment_setup 턴 1: key_entity 'app/main.py' 가 근거 페이지·사용자 발화에 없음
- v2_05_deployment_setup 턴 3: key_entity '--forwarded-allow-ips' 가 근거 페이지·사용자 발화에 없음
- v2_05_deployment_setup 턴 8: key_entity 'uv.lock' 가 근거 페이지·사용자 발화에 없음
- v2_05_deployment_setup 턴 10: key_entity '5' 가 근거 페이지·사용자 발화에 없음
- v2_05_deployment_setup 턴 10: 질문에 페이지 제목 'Middleware' 이 들어 있습니다 (출처 단서)
- v2_05_deployment_setup 턴 0: 서로 다른 주제 폴더의 문서 ['deployment/deployment-concepts-and-servers.md', 'quickstart.md'] 를 한 턴에 붙였습니다 (경고)
- v2_06_middleware_cors 턴 7: key_entity '5' 가 근거 페이지·사용자 발화에 없음
- v2_06_middleware_cors 턴 8: key_entity '--forwarded-allow-ips="*"' 가 근거 페이지·사용자 발화에 없음
- v2_06_middleware_cors 턴 0: 질문에 페이지 제목 'Middleware' 이 들어 있습니다 (출처 단서)
- v2_06_middleware_cors 턴 4: 질문에 페이지 제목 'Middleware' 이 들어 있습니다 (출처 단서)
- v2_06_middleware_cors 턴 7: 질문에 페이지 제목 'Middleware' 이 들어 있습니다 (출처 단서)
- v2_06_middleware_cors 턴 12: 질문에 페이지 제목 'Middleware' 이 들어 있습니다 (출처 단서)
- v2_06_middleware_cors 턴 18: 질문에 페이지 제목 'Middleware' 이 들어 있습니다 (출처 단서)
- v2_07_streaming_realtime 턴 8: key_entity '5' 가 근거 페이지·사용자 발화에 없음
- v2_07_streaming_realtime 턴 8: 질문에 페이지 제목 'Middleware' 이 들어 있습니다 (출처 단서)
- v2_07_streaming_realtime 턴 12: 질문에 페이지 제목 'Background Tasks' 이 들어 있습니다 (출처 단서)
- v2_07_streaming_realtime 턴 13: 질문에 페이지 제목 'Background Tasks' 이 들어 있습니다 (출처 단서)
- v2_08_model_serialization 턴 17: key_entity 'b"hello"' 가 근거 페이지·사용자 발화에 없음
- v2_09_openapi_docs 턴 12: 인용문이 app-structure/static-files-templates-and-frontend.md 에 없음: '"auto" — use `404.html` if that file exists;'
- v2_09_openapi_docs 턴 12: 인용문이 app-structure/static-files-templates-and-frontend.md 에 없음: '"404.html" — serve `dist/404.html` with status **404**.'
- v2_10_app_structure 턴 15: 서로 다른 주제 폴더의 문서 ['openapi/metadata-and-docs-ui.md', 'quickstart.md'] 를 한 턴에 붙였습니다 (경고)
- v2_11_testing_strategy 턴 4: standalone_question 에 원래 질문에 없던 key_entity ['Settings'] (답 누설)
- v2_11_testing_strategy 턴 7: same_doc_new_topic 이 앞서 물은 소제목과 같은 부분을 묻습니다 ['Passing data in requests']
- v2_11_testing_strategy 턴 15: 서로 다른 주제 폴더의 문서 ['integrations/websockets.md', 'security/oauth2-jwt.md'] 를 한 턴에 붙였습니다 (경고)
- v2_12_database 턴 1: 인용문이 dependencies/dependencies-with-yield.md 에 없음: '- "request" (default for `yield` dependencies): setup before'
- v2_12_database 턴 1: 인용문이 dependencies/dependencies-with-yield.md 에 없음: '- "function": teardown right after the path operation functi'
- v2_12_database 턴 15: 서로 다른 주제 폴더의 문서 ['request/query-parameters.md', 'getting-started/python-types-and-async.md'] 를 한 턴에 붙였습니다 (경고)
- v2_13_error_consistency 턴 5: 질문에 페이지 제목 'Middleware' 이 들어 있습니다 (출처 단서)
- v2_13_error_consistency 턴 6: 질문에 페이지 제목 'Middleware' 이 들어 있습니다 (출처 단서)
- v2_13_error_consistency 턴 15: 서로 다른 주제 폴더의 문서 ['internals/request-handling-internals.md', 'openapi/extending-openapi.md'] 를 한 턴에 붙였습니다 (경고)
- v2_14_files_forms_static 턴 12: key_entity 'app/main.py' 가 근거 페이지·사용자 발화에 없음
- v2_14_files_forms_static 턴 12: key_entity '--port' 가 근거 페이지·사용자 발화에 없음
- v2_14_files_forms_static 턴 8: 질문에 페이지 제목 'Middleware' 이 들어 있습니다 (출처 단서)
- v2_14_files_forms_static 턴 14: same_doc_new_topic 이 앞서 물은 소제목과 같은 부분을 묻습니다 ['Templates (Jinja2)']
- v2_14_files_forms_static 턴 16: 질문에 페이지 제목 'Middleware' 이 들어 있습니다 (출처 단서)
- v2_15_settings_env 턴 1: 서로 다른 주제 폴더의 문서 ['getting-started/development-workflow.md', 'app-structure/static-files-templates-and-frontend.md'] 를 한 턴에 붙였습니다 (경고)
- v2_17_request_internals 턴 1: 질문에 페이지 제목 'Middleware' 이 들어 있습니다 (출처 단서)
- v2_17_request_internals 턴 2: 질문에 페이지 제목 'Middleware' 이 들어 있습니다 (출처 단서)
- v2_17_request_internals 턴 9: 질문에 페이지 제목 'Middleware' 이 들어 있습니다 (출처 단서)
- v2_17_request_internals 턴 11: 질문에 페이지 제목 'Middleware' 이 들어 있습니다 (출처 단서)
- v2_17_request_internals 턴 14: 질문에 페이지 제목 'Middleware' 이 들어 있습니다 (출처 단서)
- v2_18_integrations 턴 9: key_entity 'threadpool' 가 근거 페이지·사용자 발화에 없음
- v2_18_integrations 턴 5: 질문에 페이지 제목 'Middleware' 이 들어 있습니다 (출처 단서)
- v2_18_integrations 턴 6: 질문에 페이지 제목 'Middleware' 이 들어 있습니다 (출처 단서)
- v2_18_integrations 턴 15: 서로 다른 주제 폴더의 문서 ['about/features-and-ecosystem.md', 'openapi/generating-clients.md'] 를 한 턴에 붙였습니다 (경고)
- v2_19_first_service 턴 0: key_entity '--bare' 가 근거 페이지·사용자 발화에 없음
- v2_19_first_service 턴 7: key_entity 'uvicorn.run' 가 근거 페이지·사용자 발화에 없음
- v2_19_first_service 턴 15: key_entity 'app/main.py' 가 근거 페이지·사용자 발화에 없음
- v2_19_first_service 턴 15: key_entity '--port' 가 근거 페이지·사용자 발화에 없음
- v2_19_first_service 턴 18: key_entity 'app/main.py' 가 근거 페이지·사용자 발화에 없음
- v2_19_first_service 턴 18: key_entity '--port' 가 근거 페이지·사용자 발화에 없음
- v2_19_first_service 턴 8: 서로 다른 주제 폴더의 문서 ['quickstart.md', 'getting-started/python-types-and-async.md'] 를 한 턴에 붙였습니다 (경고)
- v2_20_client_contract 턴 0: key_entity 'http://localhost:8000/openapi.json' 가 근거 페이지·사용자 발화에 없음
- v2_20_client_contract 턴 4: key_entity 'http://localhost:8000/openapi.json' 가 근거 페이지·사용자 발화에 없음

## 출처와 질문 크기

| 시나리오 | key_fact doc / user | recall·synthesis 중 user | user 값을 바꾸는 update | doc 중 example 태그 | 턴당 asks 평균 (synthesis 외 최대) | 물음표 2개 이상 턴 | 턴당 key_fact 평균 (최대) |
|---|---|---|---|---|---|---|---|
| v2_01_auth_switch | 29 / 12 | 5/12 (42%) | 턴 4, 11 | 10/29 (34%) | 2.05 (2) | 5 | 2.16 (3) |
| v2_02_response_design | 31 / 9 | 5/12 (42%) | 턴 4, 11 | 11/31 (35%) | 1.85 (2) | 8 | 2.00 (3) |
| v2_03_input_validation | 30 / 11 | 5/12 (42%) | 턴 4, 11 | 13/30 (43%) | 1.84 (2) | 0 | 2.16 (3) |
| v2_04_dependency_lifecycle | 30 / 11 | 5/12 (42%) | 턴 4, 11 | 13/30 (43%) | 2.00 (2) | 7 | 2.16 (3) |
| v2_05_deployment_setup | 31 / 11 | 6/12 (50%) | 턴 4, 11 | 9/31 (29%) | 2.05 (2) | 0 | 2.21 (3) |
| v2_06_middleware_cors | 32 / 11 | 5/12 (42%) | 턴 4, 11 | 9/32 (28%) | 2.05 (2) | 3 | 2.26 (3) |
| v2_07_streaming_realtime | 28 / 11 | 6/12 (50%) | 턴 4, 11 | 11/28 (39%) | 1.95 (2) | 0 | 2.05 (3) |
| v2_08_model_serialization | 30 / 11 | 5/13 (38%) | 턴 4, 11 | 19/30 (63%) | 1.68 (2) | 2 | 2.16 (3) |
| v2_09_openapi_docs | 30 / 10 | 6/12 (50%) | 턴 4, 11 | 16/30 (53%) | 2.05 (2) | 0 | 2.11 (3) |
| v2_10_app_structure | 29 / 11 | 6/12 (50%) | 턴 4, 11 | 11/29 (38%) | 2.05 (2) | 4 | 2.11 (3) |
| v2_11_testing_strategy | 31 / 10 | 5/12 (42%) | 턴 4, 11 | 12/31 (39%) | 1.89 (2) | 2 | 2.16 (3) |
| v2_12_database | 34 / 10 | 5/14 (36%) | 턴 4, 11 | 9/34 (26%) | 1.89 (2) | 5 | 2.32 (3) |
| v2_13_error_consistency | 27 / 13 | 6/12 (50%) | 턴 4, 11 | 12/27 (44%) | 1.79 (2) | 1 | 2.11 (3) |
| v2_14_files_forms_static | 29 / 12 | 6/12 (50%) | 턴 4, 11 | 15/29 (52%) | 2.00 (2) | 0 | 2.16 (3) |
| v2_15_settings_env | 32 / 9 | 5/12 (42%) | 턴 4, 11 | 14/32 (44%) | 2.05 (2) | 0 | 2.16 (3) |
| v2_16_scopes_user_model | 28 / 11 | 5/12 (42%) | 턴 4, 11 | 13/28 (46%) | 1.95 (2) | 5 | 2.05 (3) |
| v2_17_request_internals | 32 / 10 | 5/12 (42%) | 턴 4, 11 | 11/32 (34%) | 1.95 (2) | 4 | 2.21 (3) |
| v2_18_integrations | 29 / 11 | 5/12 (42%) | 턴 4, 11 | 15/29 (52%) | 2.00 (2) | 2 | 2.11 (3) |
| v2_19_first_service | 30 / 10 | 5/12 (42%) | 턴 4, 11 | 11/30 (37%) | 2.05 (2) | 0 | 2.11 (3) |
| v2_20_client_contract | 29 / 10 | 5/12 (42%) | 턴 4, 11 | 14/29 (48%) | 1.89 (2) | 0 | 2.05 (3) |

asks 는 생성 모델이 적은 '묻는 사항' 목록, 물음표 수는 질문 문장에서 센 교차 확인용 값이다.

## closed-book 두 종류

- knowledge: 싱글턴 CLOSED_BOOK_PROMPT (모르면 UNKNOWN). 사전 지식으로 맞히는지.
- grounded: 실험 답변 지시문 mt_answer_v2 (NOT FOUND 규칙) 로 문서·기록 없이. **압축 결과를 오염시키는 쪽.**
- 채점 fact_judge_v3 (per_fact), 맞힘 = 정확도 1.0.

| 시나리오 | 유형 | 턴 | knowledge 맞힘 | grounded 맞힘 |
|---|---|---|---|---|
| v2_01_auth_switch | new | 8 | 3 | 0 |
| v2_01_auth_switch | followup | 2 | 1 | 0 |
| v2_01_auth_switch | update | 2 | 2 | 0 |
| v2_01_auth_switch | same_doc_new_topic | 2 | 1 | 0 |
| v2_01_auth_switch | recall | 3 | 0 | 0 |
| v2_01_auth_switch | synthesis | 2 | 0 | 0 |
| v2_01_auth_switch | **전체** | 19 | **7/19 (37%)** | **0/19 (0%)** |
| v2_02_response_design | new | 9 | 4 | 0 |
| v2_02_response_design | followup | 2 | 2 | 0 |
| v2_02_response_design | update | 2 | 0 | 0 |
| v2_02_response_design | same_doc_new_topic | 2 | 0 | 0 |
| v2_02_response_design | recall | 3 | 0 | 0 |
| v2_02_response_design | synthesis | 2 | 0 | 0 |
| v2_02_response_design | **전체** | 20 | **6/20 (30%)** | **0/20 (0%)** |
| v2_03_input_validation | new | 8 | 6 | 0 |
| v2_03_input_validation | followup | 2 | 2 | 0 |
| v2_03_input_validation | update | 2 | 1 | 1 |
| v2_03_input_validation | same_doc_new_topic | 2 | 1 | 0 |
| v2_03_input_validation | recall | 3 | 0 | 0 |
| v2_03_input_validation | synthesis | 2 | 0 | 0 |
| v2_03_input_validation | **전체** | 19 | **10/19 (53%)** | **1/19 (5%)** |
| v2_04_dependency_lifecycle | new | 8 | 6 | 1 |
| v2_04_dependency_lifecycle | followup | 2 | 1 | 1 |
| v2_04_dependency_lifecycle | update | 2 | 2 | 0 |
| v2_04_dependency_lifecycle | same_doc_new_topic | 2 | 1 | 0 |
| v2_04_dependency_lifecycle | recall | 3 | 0 | 0 |
| v2_04_dependency_lifecycle | synthesis | 2 | 0 | 0 |
| v2_04_dependency_lifecycle | **전체** | 19 | **10/19 (53%)** | **2/19 (11%)** |
| v2_05_deployment_setup | new | 8 | 4 | 0 |
| v2_05_deployment_setup | followup | 2 | 2 | 1 |
| v2_05_deployment_setup | update | 2 | 2 | 0 |
| v2_05_deployment_setup | same_doc_new_topic | 2 | 1 | 0 |
| v2_05_deployment_setup | recall | 3 | 0 | 0 |
| v2_05_deployment_setup | synthesis | 2 | 0 | 0 |
| v2_05_deployment_setup | **전체** | 19 | **9/19 (47%)** | **1/19 (5%)** |
| v2_06_middleware_cors | new | 8 | 4 | 0 |
| v2_06_middleware_cors | followup | 2 | 1 | 0 |
| v2_06_middleware_cors | update | 2 | 2 | 0 |
| v2_06_middleware_cors | same_doc_new_topic | 2 | 0 | 0 |
| v2_06_middleware_cors | recall | 3 | 0 | 0 |
| v2_06_middleware_cors | synthesis | 2 | 0 | 0 |
| v2_06_middleware_cors | **전체** | 19 | **7/19 (37%)** | **0/19 (0%)** |
| v2_07_streaming_realtime | new | 8 | 4 | 0 |
| v2_07_streaming_realtime | followup | 2 | 2 | 1 |
| v2_07_streaming_realtime | update | 2 | 2 | 0 |
| v2_07_streaming_realtime | same_doc_new_topic | 2 | 1 | 1 |
| v2_07_streaming_realtime | recall | 3 | 0 | 0 |
| v2_07_streaming_realtime | synthesis | 2 | 0 | 0 |
| v2_07_streaming_realtime | **전체** | 19 | **9/19 (47%)** | **2/19 (11%)** |
| v2_08_model_serialization | new | 8 | 5 | 0 |
| v2_08_model_serialization | followup | 2 | 1 | 1 |
| v2_08_model_serialization | update | 2 | 1 | 0 |
| v2_08_model_serialization | same_doc_new_topic | 2 | 2 | 0 |
| v2_08_model_serialization | recall | 3 | 1 | 0 |
| v2_08_model_serialization | synthesis | 2 | 0 | 0 |
| v2_08_model_serialization | **전체** | 19 | **10/19 (53%)** | **1/19 (5%)** |
| v2_09_openapi_docs | new | 8 | 4 | 1 |
| v2_09_openapi_docs | followup | 2 | 0 | 0 |
| v2_09_openapi_docs | update | 2 | 2 | 0 |
| v2_09_openapi_docs | same_doc_new_topic | 2 | 1 | 0 |
| v2_09_openapi_docs | recall | 3 | 0 | 0 |
| v2_09_openapi_docs | synthesis | 2 | 0 | 0 |
| v2_09_openapi_docs | **전체** | 19 | **7/19 (37%)** | **1/19 (5%)** |
| v2_10_app_structure | new | 8 | 3 | 0 |
| v2_10_app_structure | followup | 2 | 2 | 0 |
| v2_10_app_structure | update | 2 | 2 | 0 |
| v2_10_app_structure | same_doc_new_topic | 2 | 2 | 0 |
| v2_10_app_structure | recall | 3 | 0 | 0 |
| v2_10_app_structure | synthesis | 2 | 0 | 0 |
| v2_10_app_structure | **전체** | 19 | **9/19 (47%)** | **0/19 (0%)** |
| v2_11_testing_strategy | new | 8 | 5 | 0 |
| v2_11_testing_strategy | followup | 2 | 2 | 0 |
| v2_11_testing_strategy | update | 2 | 1 | 0 |
| v2_11_testing_strategy | same_doc_new_topic | 2 | 1 | 1 |
| v2_11_testing_strategy | recall | 3 | 0 | 0 |
| v2_11_testing_strategy | synthesis | 2 | 0 | 0 |
| v2_11_testing_strategy | **전체** | 19 | **9/19 (47%)** | **1/19 (5%)** |
| v2_12_database | new | 8 | 6 | 1 |
| v2_12_database | followup | 2 | 1 | 0 |
| v2_12_database | update | 2 | 2 | 0 |
| v2_12_database | same_doc_new_topic | 2 | 1 | 0 |
| v2_12_database | recall | 3 | 1 | 1 |
| v2_12_database | synthesis | 2 | 0 | 0 |
| v2_12_database | **전체** | 19 | **11/19 (58%)** | **2/19 (11%)** |
| v2_13_error_consistency | new | 8 | 6 | 0 |
| v2_13_error_consistency | followup | 2 | 2 | 0 |
| v2_13_error_consistency | update | 2 | 1 | 0 |
| v2_13_error_consistency | same_doc_new_topic | 2 | 1 | 0 |
| v2_13_error_consistency | recall | 3 | 1 | 0 |
| v2_13_error_consistency | synthesis | 2 | 0 | 0 |
| v2_13_error_consistency | **전체** | 19 | **11/19 (58%)** | **0/19 (0%)** |
| v2_14_files_forms_static | new | 8 | 1 | 0 |
| v2_14_files_forms_static | followup | 2 | 1 | 0 |
| v2_14_files_forms_static | update | 2 | 1 | 0 |
| v2_14_files_forms_static | same_doc_new_topic | 2 | 1 | 0 |
| v2_14_files_forms_static | recall | 3 | 0 | 0 |
| v2_14_files_forms_static | synthesis | 2 | 0 | 0 |
| v2_14_files_forms_static | **전체** | 19 | **4/19 (21%)** | **0/19 (0%)** |
| v2_15_settings_env | new | 8 | 5 | 0 |
| v2_15_settings_env | followup | 2 | 2 | 0 |
| v2_15_settings_env | update | 2 | 2 | 0 |
| v2_15_settings_env | same_doc_new_topic | 2 | 2 | 0 |
| v2_15_settings_env | recall | 3 | 0 | 0 |
| v2_15_settings_env | synthesis | 2 | 0 | 0 |
| v2_15_settings_env | **전체** | 19 | **11/19 (58%)** | **0/19 (0%)** |
| v2_16_scopes_user_model | new | 8 | 4 | 0 |
| v2_16_scopes_user_model | followup | 2 | 1 | 0 |
| v2_16_scopes_user_model | update | 2 | 2 | 1 |
| v2_16_scopes_user_model | same_doc_new_topic | 2 | 2 | 2 |
| v2_16_scopes_user_model | recall | 3 | 0 | 0 |
| v2_16_scopes_user_model | synthesis | 2 | 0 | 0 |
| v2_16_scopes_user_model | **전체** | 19 | **9/19 (47%)** | **3/19 (16%)** |
| v2_17_request_internals | new | 8 | 5 | 1 |
| v2_17_request_internals | followup | 2 | 1 | 0 |
| v2_17_request_internals | update | 2 | 1 | 0 |
| v2_17_request_internals | same_doc_new_topic | 2 | 1 | 0 |
| v2_17_request_internals | recall | 3 | 1 | 0 |
| v2_17_request_internals | synthesis | 2 | 0 | 0 |
| v2_17_request_internals | **전체** | 19 | **9/19 (47%)** | **1/19 (5%)** |
| v2_18_integrations | new | 8 | 6 | 1 |
| v2_18_integrations | followup | 2 | 2 | 1 |
| v2_18_integrations | update | 2 | 2 | 0 |
| v2_18_integrations | same_doc_new_topic | 2 | 1 | 0 |
| v2_18_integrations | recall | 3 | 0 | 0 |
| v2_18_integrations | synthesis | 2 | 0 | 0 |
| v2_18_integrations | **전체** | 19 | **11/19 (58%)** | **2/19 (11%)** |
| v2_19_first_service | new | 8 | 2 | 0 |
| v2_19_first_service | followup | 2 | 2 | 0 |
| v2_19_first_service | update | 2 | 2 | 0 |
| v2_19_first_service | same_doc_new_topic | 2 | 1 | 0 |
| v2_19_first_service | recall | 3 | 0 | 0 |
| v2_19_first_service | synthesis | 2 | 0 | 0 |
| v2_19_first_service | **전체** | 19 | **7/19 (37%)** | **0/19 (0%)** |
| v2_20_client_contract | new | 8 | 4 | 0 |
| v2_20_client_contract | followup | 2 | 2 | 0 |
| v2_20_client_contract | update | 2 | 1 | 0 |
| v2_20_client_contract | same_doc_new_topic | 2 | 2 | 1 |
| v2_20_client_contract | recall | 3 | 0 | 0 |
| v2_20_client_contract | synthesis | 2 | 0 | 0 |
| v2_20_client_contract | **전체** | 19 | **9/19 (47%)** | **1/19 (5%)** |

| 시나리오 | knowledge UNKNOWN | grounded NOT FOUND |
|---|---|---|
| v2_01_auth_switch | 7 | 19 |
| v2_02_response_design | 8 | 19 |
| v2_03_input_validation | 4 | 17 |
| v2_04_dependency_lifecycle | 5 | 16 |
| v2_05_deployment_setup | 6 | 18 |
| v2_06_middleware_cors | 5 | 19 |
| v2_07_streaming_realtime | 7 | 17 |
| v2_08_model_serialization | 4 | 18 |
| v2_09_openapi_docs | 6 | 17 |
| v2_10_app_structure | 5 | 19 |
| v2_11_testing_strategy | 8 | 18 |
| v2_12_database | 4 | 17 |
| v2_13_error_consistency | 4 | 19 |
| v2_14_files_forms_static | 5 | 19 |
| v2_15_settings_env | 5 | 19 |
| v2_16_scopes_user_model | 5 | 16 |
| v2_17_request_internals | 3 | 18 |
| v2_18_integrations | 4 | 17 |
| v2_19_first_service | 6 | 19 |
| v2_20_client_contract | 4 | 18 |

key_fact 단위 충족률 (출처별):

| 시나리오 | 검사 | source=doc | source=user |
|---|---|---|---|
| v2_01_auth_switch | knowledge | 14/29 (48%) | 6/12 (50%) |
| v2_01_auth_switch | grounded | 0/29 (0%) | 0/12 (0%) |
| v2_02_response_design | knowledge | 12/31 (39%) | 2/9 (22%) |
| v2_02_response_design | grounded | 0/31 (0%) | 0/9 (0%) |
| v2_03_input_validation | knowledge | 21/30 (70%) | 5/11 (45%) |
| v2_03_input_validation | grounded | 2/30 (7%) | 1/11 (9%) |
| v2_04_dependency_lifecycle | knowledge | 20/30 (67%) | 5/11 (45%) |
| v2_04_dependency_lifecycle | grounded | 5/30 (17%) | 0/11 (0%) |
| v2_05_deployment_setup | knowledge | 19/31 (61%) | 5/11 (45%) |
| v2_05_deployment_setup | grounded | 2/31 (6%) | 0/11 (0%) |
| v2_06_middleware_cors | knowledge | 17/32 (53%) | 5/11 (45%) |
| v2_06_middleware_cors | grounded | 0/32 (0%) | 0/11 (0%) |
| v2_07_streaming_realtime | knowledge | 14/28 (50%) | 4/11 (36%) |
| v2_07_streaming_realtime | grounded | 3/28 (11%) | 0/11 (0%) |
| v2_08_model_serialization | knowledge | 18/30 (60%) | 3/11 (27%) |
| v2_08_model_serialization | grounded | 2/30 (7%) | 0/11 (0%) |
| v2_09_openapi_docs | knowledge | 14/30 (47%) | 4/10 (40%) |
| v2_09_openapi_docs | grounded | 3/30 (10%) | 0/10 (0%) |
| v2_10_app_structure | knowledge | 17/29 (59%) | 5/11 (45%) |
| v2_10_app_structure | grounded | 0/29 (0%) | 0/11 (0%) |
| v2_11_testing_strategy | knowledge | 17/31 (55%) | 2/10 (20%) |
| v2_11_testing_strategy | grounded | 1/31 (3%) | 0/10 (0%) |
| v2_12_database | knowledge | 21/34 (62%) | 5/10 (50%) |
| v2_12_database | grounded | 4/34 (12%) | 0/10 (0%) |
| v2_13_error_consistency | knowledge | 17/27 (63%) | 5/13 (38%) |
| v2_13_error_consistency | grounded | 0/27 (0%) | 0/13 (0%) |
| v2_14_files_forms_static | knowledge | 12/29 (41%) | 6/12 (50%) |
| v2_14_files_forms_static | grounded | 0/29 (0%) | 0/12 (0%) |
| v2_15_settings_env | knowledge | 22/32 (69%) | 4/9 (44%) |
| v2_15_settings_env | grounded | 0/32 (0%) | 0/9 (0%) |
| v2_16_scopes_user_model | knowledge | 17/28 (61%) | 5/11 (45%) |
| v2_16_scopes_user_model | grounded | 4/28 (14%) | 1/11 (9%) |
| v2_17_request_internals | knowledge | 22/32 (69%) | 4/10 (40%) |
| v2_17_request_internals | grounded | 1/32 (3%) | 1/10 (10%) |
| v2_18_integrations | knowledge | 18/29 (62%) | 6/11 (55%) |
| v2_18_integrations | grounded | 2/29 (7%) | 2/11 (18%) |
| v2_19_first_service | knowledge | 15/30 (50%) | 5/10 (50%) |
| v2_19_first_service | grounded | 0/30 (0%) | 0/10 (0%) |
| v2_20_client_contract | knowledge | 19/29 (66%) | 4/10 (40%) |
| v2_20_client_contract | grounded | 1/29 (3%) | 0/10 (0%) |

## standalone_question 누설 (원래 질문에 없던 key_entity)

- v2_11_testing_strategy 턴 4: ['Settings']

## source=user key_fact

| 시나리오 | 턴 | 유형 | key_fact |
|---|---|---|---|
| v2_01_auth_switch | 0 | new | Configure OAuth2PasswordBearer with the project's relative token URL auth/issue. |
| v2_01_auth_switch | 1 | new | Use APIKeyHeader with the project's X-Orbit-Key header name. |
| v2_01_auth_switch | 2 | followup | The browser-cookie extractor must use the project's orbit_session cookie name. |
| v2_01_auth_switch | 3 | new | Pass timedelta(minutes=23) for the project's access-token lifetime. |
| v2_01_auth_switch | 4 | update | The project's access-token lifetime is now 41 minutes, replacing 23 minutes. |
| v2_01_auth_switch | 5 | new | The cookie set at login is the project's orbit_session cookie. |
| v2_01_auth_switch | 9 | recall | The current project lifetime is 41 minutes. |
| v2_01_auth_switch | 11 | update | The browser authentication cookie is now named orbit_session_v2 rather than orbit_session. |
| v2_01_auth_switch | 13 | synthesis | The current project settings are cookie orbit_session_v2 and a 41-minute token lifetime. |
| v2_01_auth_switch | 16 | recall | The project's machine-client header is X-Orbit-Key. |
| v2_01_auth_switch | 17 | recall | The current browser authentication cookie is orbit_session_v2. |
| v2_01_auth_switch | 18 | synthesis | The project's settings are auth/issue for token issuance, X-Orbit-Key for machine keys, and orbit_session_v2 for browser authentication. |
| v2_02_response_design | 0 | new | The project's upsert route is /artifacts/{artifact_id}. |
| v2_02_response_design | 1 | new | The project uses X-Forge-Stamp and forge_ticket with a lifetime of 1380 seconds. |
| v2_02_response_design | 4 | update | The cookie remains forge_ticket, but its lifetime is now 2460 seconds. |
| v2_02_response_design | 9 | recall | The current settings are X-Forge-Stamp, forge_ticket, and 2460 seconds. |
| v2_02_response_design | 11 | update | The project header is now X-Forge-Receipt, replacing X-Forge-Stamp. |
| v2_02_response_design | 13 | synthesis | Use /artifacts/{artifact_id}, X-Forge-Receipt, and forge_ticket with max_age=2460. |
| v2_02_response_design | 17 | recall | The current custom response header is X-Forge-Receipt. |
| v2_02_response_design | 18 | recall | The current cookie is forge_ticket with a lifetime of 2460 seconds. |
| v2_02_response_design | 19 | synthesis | The active project settings are /artifacts/{artifact_id}, X-Forge-Receipt, and forge_ticket with a lifetime of 2460 seconds. |
| v2_03_input_validation | 0 | new | The project query alias is catalog-needle and its maximum length is 43. |
| v2_03_input_validation | 1 | new | The item ID ceiling is inclusive at 730. |
| v2_03_input_validation | 4 | update | The inclusive item ID ceiling is now 941. |
| v2_03_input_validation | 8 | new | The project requires the X-Archive-Shard header, represented by x_archive_shard without a default. |
| v2_03_input_validation | 9 | recall | The catalog search alias is catalog-needle. |
| v2_03_input_validation | 11 | update | The search maximum length is now 61. |
| v2_03_input_validation | 11 | update | The unchanged external alias is catalog-needle. |
| v2_03_input_validation | 13 | synthesis | The current search alias is catalog-needle and the maximum length is 61. |
| v2_03_input_validation | 16 | recall | The required shard header is X-Archive-Shard and its Python parameter is x_archive_shard. |
| v2_03_input_validation | 17 | recall | The current inclusive item ID ceiling is 941. |
| v2_03_input_validation | 18 | synthesis | The current inclusive item ID ceiling is 941. |
| v2_04_dependency_lifecycle | 0 | new | The project's streaming route is /vault-feed. |
| v2_04_dependency_lifecycle | 1 | new | The reusable Annotated alias must be named SliceDep83. |
| v2_04_dependency_lifecycle | 3 | new | The project's lifespan state key is relay_client_83. |
| v2_04_dependency_lifecycle | 4 | update | The stream route is now /sealed-feed rather than /vault-feed. |
| v2_04_dependency_lifecycle | 5 | new | The gate's rejection detail must be Seal missing 83. |
| v2_04_dependency_lifecycle | 9 | recall | The chosen pagination alias is SliceDep83. |
| v2_04_dependency_lifecycle | 11 | update | The new client state key is relay_client_94, so endpoint access is request.state.relay_client_94. |
| v2_04_dependency_lifecycle | 13 | synthesis | The current stream route is /sealed-feed. |
| v2_04_dependency_lifecycle | 13 | synthesis | The current shared-client state key is relay_client_94. |
| v2_04_dependency_lifecycle | 16 | recall | The renamed streaming route is /sealed-feed. |
| v2_04_dependency_lifecycle | 17 | recall | The chosen rejection detail is Seal missing 83. |
| v2_05_deployment_setup | 0 | new | The project's launch command must use port 8137 and 3 workers. |
| v2_05_deployment_setup | 3 | new | The configured external prefix must be /edge/r7. |
| v2_05_deployment_setup | 4 | update | The new root-path option is --root-path /edge/r9. |
| v2_05_deployment_setup | 5 | new | The deployment's ADMIN_EMAIL value is release-otter@ops.example.org. |
| v2_05_deployment_setup | 9 | recall | The initial deployment uses internal port 8137 and 3 workers. |
| v2_05_deployment_setup | 11 | update | The project's updated worker count is 1 per container. |
| v2_05_deployment_setup | 13 | synthesis | The current project configuration is internal port 8137, public prefix /edge/r9, and 1 worker per container. |
| v2_05_deployment_setup | 16 | recall | The current public prefix is /edge/r9. |
| v2_05_deployment_setup | 17 | recall | The chosen deployment admin email is release-otter@ops.example.org. |
| v2_05_deployment_setup | 18 | synthesis | The current worker count is 1 per container. |
| v2_05_deployment_setup | 18 | synthesis | The current advertised public prefix is /edge/r9. |
| v2_06_middleware_cors | 0 | new | The project's elapsed-time response header is X-Trace-Lag. |
| v2_06_middleware_cors | 1 | new | Set the cookie under the project name orbit_session. |
| v2_06_middleware_cors | 2 | followup | Configure the project's origin as https://console.aster-lab.net:5447 and max_age as 731 seconds. |
| v2_06_middleware_cors | 2 | followup | The project timing header to expose is X-Trace-Lag. |
| v2_06_middleware_cors | 4 | update | The project's new preflight cache duration is 947 seconds. |
| v2_06_middleware_cors | 9 | recall | The project's timing response header is X-Trace-Lag. |
| v2_06_middleware_cors | 11 | update | The session cookie is now named orbit_session_v2. |
| v2_06_middleware_cors | 13 | synthesis | The current project pair is X-Trace-Lag and a 947-second preflight cache. |
| v2_06_middleware_cors | 16 | recall | The current session cookie name is orbit_session_v2. |
| v2_06_middleware_cors | 17 | recall | The selected frontend origin is https://console.aster-lab.net:5447. |
| v2_06_middleware_cors | 18 | synthesis | The frontend allowlist origin is https://console.aster-lab.net:5447. |
| v2_07_streaming_realtime | 0 | new | The project's GET route is /pulse-73 and its named event is kiln_tick. |
| v2_07_streaming_realtime | 1 | new | The cookie parameter must read kiln_session9. |
| v2_07_streaming_realtime | 4 | update | The named progress event is now kiln_delta. |
| v2_07_streaming_realtime | 5 | new | The audit task writes to kiln-audit-43.log. |
| v2_07_streaming_realtime | 9 | recall | The current progress event name is kiln_delta. |
| v2_07_streaming_realtime | 11 | update | The control-connection cookie is now kiln_session12. |
| v2_07_streaming_realtime | 13 | synthesis | The current event name is kiln_delta. |
| v2_07_streaming_realtime | 13 | synthesis | The chosen audit filename is kiln-audit-43.log. |
| v2_07_streaming_realtime | 16 | recall | The current session cookie name is kiln_session12. |
| v2_07_streaming_realtime | 17 | recall | The project uses GET /pulse-73 and the current named event kiln_delta. |
| v2_07_streaming_realtime | 18 | synthesis | The audit filename is kiln-audit-43.log. |
| v2_08_model_serialization | 0 | new | The creation handler uses /crew-47/. |
| v2_08_model_serialization | 1 | new | The project's currently stored tax is 23.7. |
| v2_08_model_serialization | 2 | followup | The project Item tax default is 6.25. |
| v2_08_model_serialization | 4 | update | The project's active Item tax default is now 8.75. |
| v2_08_model_serialization | 8 | new | The model's default description is Copper moth. |
| v2_08_model_serialization | 9 | recall | The chosen crew creation route is /crew-47/. |
| v2_08_model_serialization | 11 | update | The active public crew creation route is now /crew-83/. |
| v2_08_model_serialization | 13 | synthesis | The current public crew creation route is /crew-83/. |
| v2_08_model_serialization | 13 | synthesis | The current project Item tax default is 8.75. |
| v2_08_model_serialization | 16 | recall | The active crew creation route is /crew-83/. |
| v2_08_model_serialization | 18 | synthesis | Under the changed project default, replacement-style PUT saves tax 8.75 when tax is omitted. |
| v2_09_openapi_docs | 0 | new | The initialization uses title Copper Finch Relay, openapi_url /spec/finch-27.json, and docs_url /workbench-27. |
| v2_09_openapi_docs | 1 | new | The parcel operation's explicit operation_id is dispatchParcelQ8. |
| v2_09_openapi_docs | 4 | update | The generated API title must now be Copper Finch Dispatch. |
| v2_09_openapi_docs | 9 | recall | The chosen schema URL is /spec/finch-27.json. |
| v2_09_openapi_docs | 11 | update | The Swagger UI route is now configured with docs_url="/console-63". |
| v2_09_openapi_docs | 13 | synthesis | The current API title is Copper Finch Dispatch. |
| v2_09_openapi_docs | 13 | synthesis | The current Swagger UI route is /console-63. |
| v2_09_openapi_docs | 16 | recall | The current Swagger UI route is /console-63. |
| v2_09_openapi_docs | 17 | recall | The parcel operation's explicit ID is dispatchParcelQ8. |
| v2_09_openapi_docs | 18 | synthesis | The client generator should fetch the schema at /spec/finch-27.json. |
| v2_10_app_structure | 0 | new | The project's router configuration uses prefix /vault/r7 and tag relics. |
| v2_10_app_structure | 2 | followup | The project's router-only dependency function is verify_archive_pass. |
| v2_10_app_structure | 3 | new | The project's audit API mount path is /auditbox. |
| v2_10_app_structure | 4 | update | The project's router prefix is now /vault/r9, replacing /vault/r7. |
| v2_10_app_structure | 9 | recall | The chosen router-only check is verify_archive_pass. |
| v2_10_app_structure | 11 | update | The audit API mount path is now /audit-hub rather than /auditbox. |
| v2_10_app_structure | 13 | synthesis | The current router prefix is /vault/r9. |
| v2_10_app_structure | 13 | synthesis | The chosen router-only dependency is verify_archive_pass. |
| v2_10_app_structure | 16 | recall | The current project router prefix is /vault/r9. |
| v2_10_app_structure | 17 | recall | The current audit API mount path is /audit-hub. |
| v2_10_app_structure | 18 | synthesis | The current router version prefix is /vault/r9. |
| v2_11_testing_strategy | 0 | new | The project's request uses X-Experiment-Seal with value violet-62. |
| v2_11_testing_strategy | 3 | new | The override constructs Settings with admin_email qa-orbit@sample.net. |
| v2_11_testing_strategy | 4 | update | The settings override now returns Settings with admin_email qa-comet@sample.net. |
| v2_11_testing_strategy | 9 | recall | The chosen header pair is X-Experiment-Seal: violet-62. |
| v2_11_testing_strategy | 11 | update | The new header value is amber-93. |
| v2_11_testing_strategy | 11 | update | The retained header name is X-Experiment-Seal. |
| v2_11_testing_strategy | 13 | synthesis | The current settings-test admin email is qa-comet@sample.net. |
| v2_11_testing_strategy | 16 | recall | The current custom header is X-Experiment-Seal with value amber-93. |
| v2_11_testing_strategy | 17 | recall | The current settings-test admin email is qa-comet@sample.net. |
| v2_11_testing_strategy | 18 | synthesis | The current custom HTTP header pair is X-Experiment-Seal: amber-93. |
| v2_12_database | 0 | new | The configured SQLite URL is sqlite:///basalt-ledger.db. |
| v2_12_database | 4 | update | The replacement engine uses sqlite:///basalt-rehearsal.db. |
| v2_12_database | 6 | followup | The POST collection route is /vault-heroes/. |
| v2_12_database | 9 | recall | The current database URL uses basalt-rehearsal.db, not the original filename. |
| v2_12_database | 10 | new | The project's app_name default is Basalt Registry. |
| v2_12_database | 11 | update | The default limit is now 61. |
| v2_12_database | 13 | synthesis | The current default list size is 61. |
| v2_12_database | 16 | recall | The selected app name is Basalt Registry. |
| v2_12_database | 18 | synthesis | The collection POST route is /vault-heroes/. |
| v2_12_database | 18 | synthesis | The service's current configured SQLite filename is basalt-rehearsal.db. |
| v2_13_error_consistency | 0 | new | Both handlers use the project envelope key fault. |
| v2_13_error_consistency | 0 | new | The request-validation handler returns status 409. |
| v2_13_error_consistency | 1 | new | The body wrapper and parameter name are parcel. |
| v2_13_error_consistency | 4 | update | Request-validation errors now return 400 instead of 409. |
| v2_13_error_consistency | 4 | update | The envelope key remains fault. |
| v2_13_error_consistency | 5 | new | The response trace header is X-Fault-Trace. |
| v2_13_error_consistency | 9 | recall | The current envelope key is fault. |
| v2_13_error_consistency | 9 | recall | The current request-validation status is 400. |
| v2_13_error_consistency | 11 | update | Both error handlers now use problem instead of fault. |
| v2_13_error_consistency | 13 | synthesis | The current error envelope key is problem. |
| v2_13_error_consistency | 16 | recall | The required inventory body wrapper is parcel. |
| v2_13_error_consistency | 18 | synthesis | The current envelope key is problem. |
| v2_13_error_consistency | 18 | synthesis | The current request-validation status is 400. |
| v2_14_files_forms_static | 0 | new | The multiple-upload parameter must use the project field name artifacts. |
| v2_14_files_forms_static | 1 | new | The asset mount uses the project prefix /atelier-assets. |
| v2_14_files_forms_static | 3 | new | The filename argument must be review-pack-83.zip. |
| v2_14_files_forms_static | 4 | update | The active asset URL prefix is now /sealed-assets. |
| v2_14_files_forms_static | 8 | new | The middleware writes the project header X-Intake-Elapsed. |
| v2_14_files_forms_static | 9 | recall | The upload field is artifacts. |
| v2_14_files_forms_static | 11 | update | The current filename argument is review-pack-97.zip. |
| v2_14_files_forms_static | 13 | synthesis | The current asset URL prefix is /sealed-assets. |
| v2_14_files_forms_static | 13 | synthesis | The timing response header is X-Intake-Elapsed. |
| v2_14_files_forms_static | 16 | recall | The chosen timing header is X-Intake-Elapsed. |
| v2_14_files_forms_static | 17 | recall | The current browser download filename is review-pack-97.zip. |
| v2_14_files_forms_static | 18 | synthesis | The chosen upload field name is artifacts. |
| v2_15_settings_env | 0 | new | The project settings use app_name Copper Finch Console, admin_email ops@finch.example, and integer items_per_user 73. |
| v2_15_settings_env | 3 | new | The project's openapi_url default is /schema/finch.json and is passed into FastAPI at construction. |
| v2_15_settings_env | 4 | update | The new project per-user item limit is 91. |
| v2_15_settings_env | 9 | recall | The response uses the chosen name Copper Finch Console, email ops@finch.example, and updated limit 91. |
| v2_15_settings_env | 11 | update | The project's schema URL is now /internal/finch-schema.json. |
| v2_15_settings_env | 13 | synthesis | The current schema URL is /internal/finch-schema.json. |
| v2_15_settings_env | 13 | synthesis | The current per-user item limit is 91. |
| v2_15_settings_env | 16 | recall | The chosen application name is Copper Finch Console and the administrator email is ops@finch.example. |
| v2_15_settings_env | 18 | synthesis | The current project schema URL is /internal/finch-schema.json. |
| v2_16_scopes_user_model | 0 | new | The project's custom scope is vault:scan and belongs in the available-scopes mapping. |
| v2_16_scopes_user_model | 1 | new | Pass timedelta(minutes=23) as expires_delta. |
| v2_16_scopes_user_model | 3 | new | AccountCard is the project's public user model. |
| v2_16_scopes_user_model | 4 | update | The new explicit token lifetime is 41 minutes. |
| v2_16_scopes_user_model | 9 | recall | The scan route's custom permission is vault:scan. |
| v2_16_scopes_user_model | 10 | new | Set docs_url to the project's /bench-62 path. |
| v2_16_scopes_user_model | 11 | update | The updated Swagger UI path is /bench-94. |
| v2_16_scopes_user_model | 13 | synthesis | The current explicit access-token lifetime is 41 minutes. |
| v2_16_scopes_user_model | 16 | recall | The final Swagger UI path is /bench-94. |
| v2_16_scopes_user_model | 17 | recall | The public model is named AccountCard. |
| v2_16_scopes_user_model | 18 | synthesis | The custom scan permission is vault:scan. |
| v2_17_request_internals | 1 | new | The middleware writes the duration into X-Quartz-Latency. |
| v2_17_request_internals | 3 | new | The cookie is named ember_session and uses max_age=1380. |
| v2_17_request_internals | 4 | update | The cookie now uses max_age=2460 seconds. |
| v2_17_request_internals | 4 | update | Its name remains ember_session. |
| v2_17_request_internals | 9 | recall | The chosen timing header is X-Quartz-Latency. |
| v2_17_request_internals | 11 | update | The timing header is now X-Quartz-Elapsed. |
| v2_17_request_internals | 13 | synthesis | The current cookie lifetime is 2460 seconds. |
| v2_17_request_internals | 13 | synthesis | The current timing header is X-Quartz-Elapsed. |
| v2_17_request_internals | 16 | recall | The session cookie is ember_session with max_age=2460 seconds. |
| v2_17_request_internals | 18 | synthesis | The current timing header is X-Quartz-Elapsed. |
| v2_18_integrations | 0 | new | The router inclusion must use the project's /query-cedar prefix. |
| v2_18_integrations | 1 | new | The writer uses audit-73.log as its output filename. |
| v2_18_integrations | 3 | new | The project's stripped prefix is configured as root_path="/edge/r9". |
| v2_18_integrations | 4 | update | The new root_path is /edge/r11. |
| v2_18_integrations | 6 | followup | The project's GZip minimum_size is 1379 bytes. |
| v2_18_integrations | 9 | recall | The configured writer filename is audit-73.log. |
| v2_18_integrations | 11 | update | The revised GraphQL inclusion uses /query-larch. |
| v2_18_integrations | 13 | synthesis | The current stripped public prefix is /edge/r11. |
| v2_18_integrations | 13 | synthesis | The chosen GZip minimum_size is 1379 bytes. |
| v2_18_integrations | 16 | recall | The current GraphQL prefix is /query-larch. |
| v2_18_integrations | 18 | synthesis | The notification output filename is audit-73.log. |
| v2_19_first_service | 1 | new | The configured entrypoint must be service.api:app. |
| v2_19_first_service | 3 | new | The project's item ID ceiling is 731 and must be used as the inclusive upper bound. |
| v2_19_first_service | 4 | update | The revised inclusive ceiling is 947, while the positive-only constraint remains. |
| v2_19_first_service | 5 | new | The public query alias is lookup-key, while the Python parameter remains q. |
| v2_19_first_service | 9 | recall | The configured application target is service.api:app. |
| v2_19_first_service | 11 | update | The entrypoint must now be service.gateway:app. |
| v2_19_first_service | 13 | synthesis | The current import target is service.gateway:app. |
| v2_19_first_service | 16 | recall | The public search alias is lookup-key. |
| v2_19_first_service | 17 | recall | The current declaration enforces positive IDs with an inclusive ceiling of 947. |
| v2_19_first_service | 18 | synthesis | The project's current application target is service.gateway:app. |
| v2_20_client_contract | 0 | new | Write the generated client to src/nebula-sdk. |
| v2_20_client_contract | 1 | new | The project's public response model is named RelicPublic. |
| v2_20_client_contract | 3 | new | Pin the project's ID with operation_id="relics-fetch_relic". |
| v2_20_client_contract | 4 | update | The generated client directory is now packages/aster-client. |
| v2_20_client_contract | 9 | recall | The current output directory is packages/aster-client, not the original directory. |
| v2_20_client_contract | 11 | update | The public fetch operation now uses operation_id="relics-load_relic". |
| v2_20_client_contract | 13 | synthesis | The current public fetch operation ID is relics-load_relic. |
| v2_20_client_contract | 16 | recall | The chosen public response model name is RelicPublic. |
| v2_20_client_contract | 17 | recall | The current explicit setting is operation_id="relics-load_relic". |
| v2_20_client_contract | 18 | synthesis | The current generated client output directory is packages/aster-client. |

## 비율 압축 강도의 overflow (기록 4k 이상 턴)

예산 = ⌈r × 과거 기록⌉. 최근 1턴(keep_recent)만으로 예산을 넘으면 overflow. 과거 답변 자리에 참고 정답을 넣어 셌다.

| 시나리오 | 센 턴 | r25 | r50 | r75 |
|---|---|---|---|---|
| v2_01_auth_switch | 17 | 18% | 6% | 0% |
| v2_02_response_design | 16 | 12% | 0% | 0% |
| v2_03_input_validation | 17 | 12% | 0% | 0% |
| v2_04_dependency_lifecycle | 17 | 6% | 0% | 0% |
| v2_05_deployment_setup | 18 | 17% | 6% | 6% |
| v2_06_middleware_cors | 17 | 18% | 0% | 0% |
| v2_07_streaming_realtime | 17 | 12% | 0% | 0% |
| v2_08_model_serialization | 17 | 12% | 6% | 0% |
| v2_09_openapi_docs | 17 | 12% | 0% | 0% |
| v2_10_app_structure | 15 | 20% | 0% | 0% |
| v2_11_testing_strategy | 17 | 12% | 6% | 0% |
| v2_12_database | 17 | 18% | 6% | 0% |
| v2_13_error_consistency | 17 | 12% | 6% | 0% |
| v2_14_files_forms_static | 17 | 12% | 0% | 0% |
| v2_15_settings_env | 17 | 12% | 6% | 0% |
| v2_16_scopes_user_model | 17 | 12% | 0% | 0% |
| v2_17_request_internals | 17 | 6% | 0% | 0% |
| v2_18_integrations | 15 | 13% | 0% | 0% |
| v2_19_first_service | 15 | 20% | 0% | 0% |
| v2_20_client_contract | 17 | 12% | 6% | 0% |

## confusable 태그 key_fact

| 시나리오 | 턴 | key_fact |
|---|---|---|
| v2_01_auth_switch | 2 | HTTPBearer returns HTTPAuthorizationCredentials with scheme and credentials fields, unlike the password-flow extractor's string. |
| v2_01_auth_switch | 3 | The helper's fallback lifetime is 15 minutes when expires_delta is not provided. |
| v2_01_auth_switch | 4 | The project's access-token lifetime is now 41 minutes, replacing 23 minutes. |
| v2_01_auth_switch | 7 | The timing-safe Basic-auth example checks stanleyjobson and swordfish. |
| v2_01_auth_switch | 8 | The example lists both HTTP and HTTPS localhost.tiangolo.com, plus http://localhost and http://localhost:8080. |
| v2_01_auth_switch | 9 | The current project lifetime is 41 minutes. |
| v2_01_auth_switch | 9 | Omitting expires_delta uses the helper's 15-minute fallback. |
| v2_01_auth_switch | 11 | The browser authentication cookie is now named orbit_session_v2 rather than orbit_session. |
| v2_01_auth_switch | 12 | The scoped example returns 401 Not enough permissions when items is missing for /users/me/items/. |
| v2_01_auth_switch | 12 | FastAPI 0.122.0 changed built-in authentication errors from 403 to 401 with a suitable WWW-Authenticate header. |
| v2_01_auth_switch | 13 | The current project settings are cookie orbit_session_v2 and a 41-minute token lifetime. |
| v2_01_auth_switch | 13 | The middleware handles preflight requests itself with 200 or 400, without passing them to endpoints. |
| v2_01_auth_switch | 16 | APIKeyHeader returns str, while HTTPBearer returns HTTPAuthorizationCredentials with a credentials field. |
| v2_01_auth_switch | 17 | The current browser authentication cookie is orbit_session_v2. |
| v2_01_auth_switch | 18 | The project's settings are auth/issue for token issuance, X-Orbit-Key for machine keys, and orbit_session_v2 for browser authentication. |
| v2_02_response_design | 1 | The injected-response example sets fakesession to fake-cookie-session-value. |
| v2_02_response_design | 4 | The cookie remains forge_ticket, but its lifetime is now 2460 seconds. |
| v2_02_response_design | 5 | exclude_unset retains explicitly set values even when they equal the default, including baz's tax of 10.5. |
| v2_02_response_design | 7 | FastAPI recognizes codes below 200 and codes 204, 205, and 304 as forbidding a response body. |
| v2_02_response_design | 8 | Output that violates the response model raises ResponseValidationError and defaults to a 500 response. |
| v2_02_response_design | 10 | The create-item example sets response_description to 'The created item', rather than the default 'Successful Response'. |
| v2_02_response_design | 11 | The project header is now X-Forge-Receipt, replacing X-Forge-Stamp. |
| v2_02_response_design | 12 | The example documents 404 with Message and explicitly returns {"message": "Item not found"}. |
| v2_02_response_design | 14 | RedirectResponse defaults to status 307. |
| v2_02_response_design | 14 | The pydantic redirect example overrides the status to 302 and returns https://docs.pydantic.dev/. |
| v2_02_response_design | 15 | The replacement example resets an omitted stored tax of 20.2 to 10.5. |
| v2_02_response_design | 17 | The current custom response header is X-Forge-Receipt. |
| v2_02_response_design | 18 | The current cookie is forge_ticket with a lifetime of 2460 seconds. |
| v2_02_response_design | 19 | Default request validation failures produce 422, while response-model validation failures produce 500. |
| v2_03_input_validation | 1 | An integer item_id receiving foo produces 422, int_parsing, and ["path", "item_id"]. |
| v2_03_input_validation | 5 | RequestValidationError defaults to 422 with errors under detail. |
| v2_03_input_validation | 5 | ResponseValidationError is a server bug and results in 500 by default, not a client validation response. |
| v2_03_input_validation | 10 | The optional UploadFile example returns the message No upload file sent. |
| v2_03_input_validation | 12 | openapi_examples provides multiple named examples in a Swagger UI dropdown. |
| v2_03_input_validation | 13 | Request validation defaults to 422 with errors under detail. |
| v2_03_input_validation | 13 | Response validation defaults to 500. |
| v2_03_input_validation | 15 | In the Item example, description is optional on input but required in the output schema because output always contains it, possibly null. |
| v2_03_input_validation | 18 | The missing-item HTTPException example returns 404 and {"detail": "Item not found"}. |
| v2_04_dependency_lifecycle | 0 | Request scope, the default for yield dependencies, keeps the resource available during streaming and tears it down after the response is sent. |
| v2_04_dependency_lifecycle | 1 | common_parameters defaults q to None, skip to 0, and limit to 100. |
| v2_04_dependency_lifecycle | 4 | Function scope is unsuitable here because it cleans up before the response is sent; the streaming iterator still needs request scope. |
| v2_04_dependency_lifecycle | 5 | The sample reads X-Token, accepts fake-super-secret-token, and rejects with status 400. |
| v2_04_dependency_lifecycle | 6 | The app-wide /items/ example returns Portal Gun and Plumbus. |
| v2_04_dependency_lifecycle | 9 | The wrapped common_parameters function defaults q to None, skip to 0, and limit to 100. |
| v2_04_dependency_lifecycle | 10 | The sample override fixes skip at 5 and limit at 10. |
| v2_04_dependency_lifecycle | 12 | A missing hero raises status 404 with detail Hero not found. |
| v2_04_dependency_lifecycle | 15 | For yolo, the custom handler returns 418 with message Oops! yolo did something. There goes a rainbow.... |
| v2_04_dependency_lifecycle | 16 | Request scope keeps the yielded resource available during streaming and cleans it up after the response is sent. |
| v2_04_dependency_lifecycle | 17 | The app-wide example's item names are Portal Gun and Plumbus. |
| v2_04_dependency_lifecycle | 18 | The original pagination callable defaults skip to 0 and limit to 100. |
| v2_04_dependency_lifecycle | 18 | A missing hero produces status 404 with detail Hero not found. |
| v2_05_deployment_setup | 0 | Use fastapi run for production; its defaults are 0.0.0.0:8000 with auto-reload off. |
| v2_05_deployment_setup | 2 | The single-machine multi-worker container example uses 4 workers. |
| v2_05_deployment_setup | 6 | The test override uses testing_admin@example.com. |
| v2_05_deployment_setup | 9 | fastapi run has auto-reload off by default. |
| v2_05_deployment_setup | 10 | GZipMiddleware defaults to minimum_size=500 bytes. |
| v2_05_deployment_setup | 10 | GZipMiddleware defaults to compresslevel=9. |
| v2_05_deployment_setup | 17 | The chosen deployment admin email is release-otter@ops.example.org. |
| v2_06_middleware_cors | 5 | The default RequestValidationError handler returns 422. |
| v2_06_middleware_cors | 5 | The plain-text validation override example uses status 400 and starts its message with Validation errors:. |
| v2_06_middleware_cors | 7 | The configured GZip example uses minimum_size=1000 and compresslevel=5, while the defaults are 500 and 9. |
| v2_06_middleware_cors | 10 | A missing API key with default auto_error=True raises 401 with WWW-Authenticate: APIKey. |
| v2_06_middleware_cors | 13 | A rejected CORS preflight receives 400. |
| v2_06_middleware_cors | 13 | A missing API key defaults to 401 with WWW-Authenticate: APIKey. |
| v2_06_middleware_cors | 18 | ServerErrorMiddleware is outside user middleware and generates unhandled 500 responses. |
| v2_07_streaming_realtime | 1 | When neither credential is present, raise WebSocketException with status.WS_1008_POLICY_VIOLATION, code 1008. |
| v2_07_streaming_realtime | 8 | The configuration example sets minimum_size=1000 and compresslevel=5. |
| v2_07_streaming_realtime | 8 | The defaults are minimum_size=500 and compresslevel=9. |
| v2_07_streaming_realtime | 10 | The replacement returns skip=5 and limit=10. |
| v2_07_streaming_realtime | 16 | Missing both credentials is rejected with WebSocketException and status.WS_1008_POLICY_VIOLATION, code 1008. |
| v2_08_model_serialization | 1 | The illustrated replacement-style PUT saves the default tax 10.5 when tax is omitted. |
| v2_08_model_serialization | 7 | The illustrated baz retains tax 10.5 because it was explicitly set, even though it equals the default. |
| v2_08_model_serialization | 8 | val_json_bytes="base64" decodes input, while ser_json_bytes="base64" encodes output. |
| v2_08_model_serialization | 10 | The illustrated PATCH handler applies its update dictionary with hero_db.sqlmodel_update(hero_data). |
| v2_08_model_serialization | 13 | The current project Item tax default is 8.75. |
| v2_08_model_serialization | 15 | Explicit response_class=JSONResponse still filters through the response model but then uses jsonable_encoder and class serialization. |
| v2_08_model_serialization | 16 | A directly returned JSONResponse instance bypasses response-model validation, filtering and conversion. |
| v2_08_model_serialization | 17 | val_json_bytes="base64" controls input decoding rather than output encoding. |
| v2_08_model_serialization | 18 | Under the changed project default, replacement-style PUT saves tax 8.75 when tax is omitted. |
| v2_08_model_serialization | 18 | The illustrated SQLModel PATCH applies its dictionary with hero_db.sqlmodel_update(hero_data). |
| v2_09_openapi_docs | 0 | redoc_url=None disables ReDoc only; it does not disable the schema. |
| v2_09_openapi_docs | 1 | The default ID for the read_items GET /items/ example is read_items_items__get. |
| v2_09_openapi_docs | 5 | openapi_examples provides named examples that Swagger UI displays in a dropdown. |
| v2_09_openapi_docs | 6 | The invalid example sends name Baz and price "thirty five point four". |
| v2_09_openapi_docs | 8 | The example custom generator produces items-create_item. |
| v2_09_openapi_docs | 9 | openapi_url=None disables both automatic documentation UIs as well as the schema. |
| v2_09_openapi_docs | 10 | update_item documents both 404 and 403 responses. |
| v2_09_openapi_docs | 11 | Changing docs_url does not require changing openapi_url. |
| v2_09_openapi_docs | 15 | Missing items permission produces 401 with detail Not enough permissions. |
| v2_09_openapi_docs | 18 | The own-items demo without items permission returns 401 with detail Not enough permissions. |
| v2_10_app_structure | 1 | The example verify_token accepts fake-super-secret-token. |
| v2_10_app_structure | 2 | The example verify_key accepts fake-super-secret-key. |
| v2_10_app_structure | 12 | The item-testing example's successful X-Token value is coneofsilence. |
| v2_10_app_structure | 12 | The hailhydra bad-token test expects 400 and detail Invalid X-Token header. |
| v2_10_app_structure | 15 | The documented FastAPI framework release is 0.142.2. |
| v2_10_app_structure | 15 | Application version metadata describes your API and defaults to 0.1.0, not the framework or OpenAPI version. |
| v2_11_testing_strategy | 0 | The sample rejects a bad token with 400 and detail Invalid X-Token header. |
| v2_11_testing_strategy | 1 | The returned params are q=foo, skip=5, limit=10, ignoring the supplied skip and limit. |
| v2_11_testing_strategy | 14 | A connection rejected with code 1008 raises WebSocketDisconnect in TestClient. |
| v2_11_testing_strategy | 15 | When both session cookie and query token are absent, the WebSocket sample raises WebSocketException with code 1008. |
| v2_11_testing_strategy | 15 | An expired JWT produces HTTP 401 with WWW-Authenticate: Bearer. |
| v2_11_testing_strategy | 16 | Use data for form data rather than json. |
| v2_12_database | 8 | PUT replacement resets omitted tax from 20.2 to the model default 10.5. |
| v2_12_database | 9 | The current database URL uses basalt-rehearsal.db, not the original filename. |
| v2_12_database | 10 | The unchanged items_per_user default is 50. |
| v2_12_database | 11 | The retained maximum is 100, enforced with Query(le=100). |
| v2_12_database | 13 | The current default list size is 61. |
| v2_12_database | 16 | The unchanged items_per_user default is 50. |
| v2_12_database | 18 | The service's current configured SQLite filename is basalt-rehearsal.db. |
| v2_13_error_consistency | 0 | The request-validation handler returns status 409. |
| v2_13_error_consistency | 3 | Wrong login credentials in the example produce 400 with Incorrect username or password. |
| v2_13_error_consistency | 3 | A missing bearer header produces 401 with WWW-Authenticate: Bearer. |
| v2_13_error_consistency | 4 | Request-validation errors now return 400 instead of 409. |
| v2_13_error_consistency | 6 | The timing example uses time.perf_counter() and X-Process-Time. |
| v2_13_error_consistency | 8 | The task example initializes foo to Listen to the Bar Fighters. |
| v2_13_error_consistency | 9 | The current request-validation status is 400. |
| v2_13_error_consistency | 13 | A missing bearer header produces 401 with WWW-Authenticate: Bearer. |
| v2_13_error_consistency | 14 | Override make_not_authenticated_error to return a 403 HTTPException with detail Not authenticated. |
| v2_13_error_consistency | 15 | Invalid JSON becomes RequestValidationError with type json_invalid and default status 422. |
| v2_13_error_consistency | 18 | The current request-validation status is 400. |
| v2_13_error_consistency | 18 | A response-model mismatch raises ResponseValidationError and defaults to 500, not a client-validation status. |
| v2_14_files_forms_static | 7 | An extra field produces status 422 with type extra_forbidden. |
| v2_14_files_forms_static | 8 | Measure around await call_next(request) with time.perf_counter(), then set the response header. |
| v2_14_files_forms_static | 15 | The sample adds image/png under responses[200].content alongside the JSON response model. |
| v2_14_files_forms_static | 16 | time.perf_counter() is more precise than time.time() for duration measurement. |
| v2_15_settings_env | 1 | With check_dir="auto", a missing frontend directory only warns when FASTAPI_ENV is development. |
| v2_15_settings_env | 2 | An inherited development value keeps the automatic missing-directory check in warning-only mode. |
| v2_15_settings_env | 3 | An empty openapi_url disables the schema and both docs UIs; the default-path example returns 404 at /openapi.json, /docs, and /redoc. |
| v2_15_settings_env | 7 | The settings override example supplies testing_admin@example.com as admin_email. |
| v2_15_settings_env | 12 | The example request receives q foo, skip 5, and limit 10 because the override does not declare skip or limit. |
| v2_15_settings_env | 15 | The package-layout container example runs fastapi run app/main.py on port 80 using exec-form CMD. |
| v2_15_settings_env | 18 | An empty openapi_url disables the schema and docs UIs, with /openapi.json, /docs, and /redoc returning 404 in the default-path example. |
| v2_16_scopes_user_model | 2 | When expires_delta is omitted, the helper uses 15 minutes. |
| v2_16_scopes_user_model | 8 | Function-scoped exit code runs after the endpoint returns and before sending the response. |
| v2_16_scopes_user_model | 9 | A missing required scope produces 401 Not enough permissions with a Bearer challenge containing the required scopes. |
| v2_16_scopes_user_model | 12 | A missing API key produces 401 with WWW-Authenticate: APIKey under the default auto_error behavior. |
| v2_16_scopes_user_model | 13 | The helper still defaults to 15 minutes when its expiry argument is omitted. |
| v2_16_scopes_user_model | 15 | ResponseValidationError is an application-output bug and produces 500 by default. |
| v2_16_scopes_user_model | 15 | RequestValidationError normally produces 422, not the output-validation status. |
| v2_16_scopes_user_model | 18 | A token missing a required scope receives 401 with detail Not enough permissions. |
| v2_17_request_internals | 7 | strict_content_type=False permits JSON parsing for an absent header, not for a non-JSON type such as text/plain. |
| v2_17_request_internals | 10 | /items/foo yields 422 with type int_parsing and loc ["path", "item_id"]. |
| v2_17_request_internals | 12 | Invalid JSON produces RequestValidationError with type json_invalid and status 422. |
| v2_17_request_internals | 12 | Other parsing failures produce HTTPException(400, "There was an error parsing the body"). |
| v2_17_request_internals | 13 | Malformed JSON produces error type json_invalid and HTTP 422. |
| v2_17_request_internals | 14 | GZipMiddleware defaults are minimum_size=500 and compresslevel=9. |
| v2_17_request_internals | 14 | It compresses responses for clients advertising gzip in Accept-Encoding. |
| v2_17_request_internals | 17 | The integer-path failure has type int_parsing and loc ["path", "item_id"]. |
| v2_17_request_internals | 18 | The untouched compression defaults are minimum_size=500 bytes and compresslevel=9. |
| v2_18_integrations | 1 | The basic notification example opens the file with mode="w", not append mode. |
| v2_18_integrations | 6 | The default GZip compresslevel is 9. |
| v2_18_integrations | 10 | When neither credential is present, it raises WebSocketException with policy-violation close code 1008. |
| v2_18_integrations | 12 | fastapi run listens on 0.0.0.0:8000 by default. |
| v2_18_integrations | 12 | The explicit Uvicorn single-process example uses port 80. |
| v2_18_integrations | 18 | Normal WebSocket close codes 1000 and 1001 do not produce error logs. |
| v2_19_first_service | 2 | The development command listens on 127.0.0.1:8000 and enables auto-reload. |
| v2_19_first_service | 7 | The debugging example calls uvicorn.run(app, host="0.0.0.0", port=8000) under the main guard. |
| v2_19_first_service | 8 | Type-driven validation produces automatic 422 errors. |
| v2_19_first_service | 9 | fastapi run binds to 0.0.0.0 with no reload and leaves FASTAPI_ENV unchanged. |
| v2_19_first_service | 10 | The duplicate-item test asserts 409 with detail Item already exists. |
| v2_19_first_service | 14 | The default OpenAPI version is 3.1.0. |
| v2_19_first_service | 15 | The package-layout proxy example uses fastapi run app/main.py with --proxy-headers and port 80 in exec-form CMD. |
| v2_19_first_service | 18 | The proxy container example uses exec-form CMD with fastapi run, app/main.py, --proxy-headers, and port 80. |
| v2_20_client_contract | 5 | The sample upsert returns 200 for existing items and 201 for new items. |
| v2_20_client_contract | 8 | Use openapi_examples for selectable named examples; they are operation media-type examples, not JSON Schema examples. |
| v2_20_client_contract | 9 | The current output directory is packages/aster-client, not the original directory. |
| v2_20_client_contract | 13 | The current public fetch operation ID is relics-load_relic. |
| v2_20_client_contract | 15 | get_token_header accepts fake-super-secret-token. |
| v2_20_client_contract | 17 | The current explicit setting is operation_id="relics-load_relic". |

## same_doc_new_topic 소제목

| 시나리오 | 턴 | source_turn | 페이지 | 첨부 때 물은 소제목 | 이번에 묻는 소제목 | 다른가 |
|---|---|---|---|---|---|---|
| v2_01_auth_switch | 7 | 1 | security/http-basic-and-api-keys.md | (머리말) | Checking credentials safely | 예 |
| v2_01_auth_switch | 14 | 5 | responses/response-headers-and-cookies.md | 1. A `Response` parameter (recommended when returning data); `set_cookie` options | 2. Returning a `Response` directly | 예 |
| v2_02_response_design | 7 | 0 | responses/status-codes.md | Changing the status code per request | Status code ranges | 예 |
| v2_02_response_design | 14 | 3 | responses/custom-responses.md | Returning a `Response` directly | `RedirectResponse` | 예 |
| v2_03_input_validation | 7 | 0 | request/query-parameters.md | Metadata, aliases and deprecation; `Query()`: validation and metadata | Query parameter models | 예 |
| v2_03_input_validation | 14 | 3 | request/request-body.md | Field validation and metadata: `Field()` | Bodies that are lists or dicts | 예 |
| v2_04_dependency_lifecycle | 7 | 0 | dependencies/dependencies-with-yield.md | Early exit with `scope` |  | 예 |
| v2_04_dependency_lifecycle | 7 | 0 | dependencies/advanced-dependencies.md | Dependency `scope` for `yield` dependencies | Parameterized dependencies with callable instances | 예 |
| v2_04_dependency_lifecycle | 14 | 3 | app-structure/lifespan-events.md | Lifespan state | Lifespans on routers | 예 |
| v2_05_deployment_setup | 7 | 0 | deployment/deployment-concepts-and-servers.md | Running the server: `fastapi run` | Pinning FastAPI versions | 예 |
| v2_05_deployment_setup | 7 | 0 | quickstart.md |  |  | 예 |
| v2_05_deployment_setup | 14 | 5 | app-structure/settings.md | Define a `Settings` class | Reading a `.env` file | 예 |
| v2_06_middleware_cors | 7 | 0 | middleware/middleware.md | Execution order; Writing HTTP middleware | `GZipMiddleware` | 예 |
| v2_06_middleware_cors | 7 | 0 | middleware/cors.md |  |  | 예 |
| v2_06_middleware_cors | 14 | 1 | responses/response-headers-and-cookies.md | 1. A `Response` parameter (recommended when returning data); `set_cookie` options | 2. Returning a `Response` directly | 예 |
| v2_07_streaming_realtime | 7 | 0 | responses/streaming-and-sse.md | Basic SSE; Controlling event fields: `ServerSentEvent` | JSON Lines | 예 |
| v2_07_streaming_realtime | 14 | 1 | integrations/websockets.md | Parameters and dependencies | Disconnects and multiple clients | 예 |
| v2_08_model_serialization | 7 | 0 | models/response-model.md | Filtering output | Response model encoding options | 예 |
| v2_08_model_serialization | 14 | 1 | models/extra-models-and-updates.md | Replace with `PUT` | Union responses (`anyOf`) | 예 |
| v2_09_openapi_docs | 7 | 0 | openapi/metadata-and-docs-ui.md | URLs of the schema and docs | Configuring Swagger UI | 예 |
| v2_09_openapi_docs | 14 | 1 | app-structure/path-operation-configuration.md | Operation IDs | Excluding from OpenAPI | 예 |
| v2_10_app_structure | 7 | 0 | app-structure/bigger-applications.md | Shared settings on the router | Telling the CLI where the app is | 예 |
| v2_10_app_structure | 14 | 5 | app-structure/path-operation-configuration.md | Operation IDs | Excluding from OpenAPI | 예 |
| v2_11_testing_strategy | 7 | 0 | testing/testing-basics.md | Extended example: headers, bodies, error cases; Passing data in requests | Passing data in requests | 아니오 |
| v2_11_testing_strategy | 14 | 1 | testing/testing-dependencies-events-websockets.md | Overriding dependencies | Testing WebSockets | 예 |
| v2_12_database | 7 | 0 | integrations/sql-databases.md | Building blocks | Multiple models | 예 |
| v2_12_database | 14 | 1 | dependencies/dependencies-with-yield.md | ? | Background tasks | 예 |
| v2_13_error_consistency | 7 | 0 | errors/handling-errors.md | Custom headers; Overriding the default handlers | Reusing FastAPI's default handlers | 예 |
| v2_13_error_consistency | 14 | 0 | errors/handling-errors.md | Custom headers; Overriding the default handlers | Authentication errors: 401 vs 403 | 예 |
| v2_14_files_forms_static | 7 | 0 | request/forms-and-files.md | Files: `File()` and `UploadFile`; Multiple files | Form models | 예 |
| v2_14_files_forms_static | 14 | 1 | app-structure/static-files-templates-and-frontend.md | Static files | Templates (Jinja2) | 예 |
| v2_15_settings_env | 7 | 0 | app-structure/settings.md | Define a `Settings` class; Settings as a dependency (recommended); Why `@lru_cache` | Overriding settings in tests | 예 |
| v2_15_settings_env | 14 | 0 | app-structure/settings.md | Define a `Settings` class; Settings as a dependency (recommended); Why `@lru_cache` | Reading a `.env` file | 예 |
| v2_16_scopes_user_model | 7 | 0 | security/oauth2-scopes.md | 3. Require scopes with `Security()` | Choosing a flow | 예 |
| v2_16_scopes_user_model | 7 | 0 | security/oauth2-password-flow.md |  |  | 예 |
| v2_16_scopes_user_model | 14 | 3 | models/extra-models-and-updates.md | Multiple models per entity | Partial update with `PATCH` | 예 |
| v2_17_request_internals | 7 | 0 | request/using-request-directly.md | Using the `Request` directly | Allowing requests without `Content-Type`; Strict `Content-Type` checking | 예 |
| v2_17_request_internals | 14 | 1 | middleware/middleware.md | Writing HTTP middleware | `GZipMiddleware` | 예 |
| v2_18_integrations | 7 | 0 | integrations/graphql-and-opentelemetry.md | Strawberry example | Configuring with `telemetry=` | 예 |
| v2_18_integrations | 14 | 1 | integrations/background-tasks.md | Basic usage | Resources and `yield` dependencies | 예 |
| v2_19_first_service | 7 | 0 | getting-started/development-workflow.md | Virtual environments with `uv` | Debugging | 예 |
| v2_19_first_service | 14 | 1 | getting-started/first-steps.md | Configure the entrypoint once | Interactive docs | 예 |
| v2_20_client_contract | 7 | 0 | openapi/generating-clients.md | Generate a TypeScript client | Group with tags | 예 |
| v2_20_client_contract | 14 | 3 | app-structure/path-operation-configuration.md | Operation IDs | Truncating the docstring with `\f` | 예 |

## update 턴

| 시나리오 | 턴 | 변경 | 영향 턴 | user 값 |
|---|---|---|---|---|
| v2_01_auth_switch | 4 | Project access-token lifetime in minutes: 23 → 41 | [9, 13] | 예 |
| v2_01_auth_switch | 11 | Browser authentication cookie name: orbit_session → orbit_session_v2 | [13, 17, 18] | 예 |
| v2_02_response_design | 4 | Project cookie lifetime in seconds: 1380 → 2460 | [9, 13, 18, 19] | 예 |
| v2_02_response_design | 11 | Project custom response header name: X-Forge-Stamp → X-Forge-Receipt | [13, 17, 19] | 예 |
| v2_03_input_validation | 4 | Inclusive catalog item ID ceiling: 730 → 941 | [17, 18] | 예 |
| v2_03_input_validation | 11 | Catalog search maximum length: 43 → 61 | [13] | 예 |
| v2_04_dependency_lifecycle | 4 | Streaming route path: /vault-feed → /sealed-feed | [13, 16] | 예 |
| v2_04_dependency_lifecycle | 11 | Lifespan outbound-client state key: relay_client_83 → relay_client_94 | [13] | 예 |
| v2_05_deployment_setup | 4 | Public path prefix: /edge/r7 → /edge/r9 | [13, 16, 18] | 예 |
| v2_05_deployment_setup | 11 | Worker count per container: 3 → 1; Deployment topology: one machine → Kubernetes | [13, 18] | 예 |
| v2_06_middleware_cors | 4 | Project preflight cache duration in seconds: 731 → 947 | [13] | 예 |
| v2_06_middleware_cors | 11 | Project session cookie name: orbit_session → orbit_session_v2 | [16] | 예 |
| v2_07_streaming_realtime | 4 | Named progress event: kiln_tick → kiln_delta | [9, 13, 17] | 예 |
| v2_07_streaming_realtime | 11 | Control-connection session cookie: kiln_session9 → kiln_session12 | [16] | 예 |
| v2_08_model_serialization | 4 | Project Item tax default: 6.25 → 8.75 | [13, 18] | 예 |
| v2_08_model_serialization | 11 | Public crew creation route: /crew-47/ → /crew-83/ | [13, 16] | 예 |
| v2_09_openapi_docs | 4 | API title: Copper Finch Relay → Copper Finch Dispatch | [13] | 예 |
| v2_09_openapi_docs | 11 | Swagger UI URL: /workbench-27 → /console-63 | [13, 16] | 예 |
| v2_10_app_structure | 4 | Project router prefix: /vault/r7 → /vault/r9 | [13, 16, 18] | 예 |
| v2_10_app_structure | 11 | Audit API mount path: /auditbox → /audit-hub | [17] | 예 |
| v2_11_testing_strategy | 4 | settings-test admin_email: qa-orbit@sample.net → qa-comet@sample.net | [13, 17] | 예 |
| v2_11_testing_strategy | 11 | HTTP test header value: violet-62 → amber-93 | [16, 18] | 예 |
| v2_12_database | 4 | SQLite filename: basalt-ledger.db → basalt-rehearsal.db | [9, 18] | 예 |
| v2_12_database | 11 | Default list size: 37 → 61 | [13] | 예 |
| v2_13_error_consistency | 4 | Request-validation response status: 409 → 400 | [9, 18] | 예 |
| v2_13_error_consistency | 11 | Error envelope key: fault → problem | [13, 18] | 예 |
| v2_14_files_forms_static | 4 | asset URL prefix: /atelier-assets → /sealed-assets | [13] | 예 |
| v2_14_files_forms_static | 11 | browser download filename: review-pack-83.zip → review-pack-97.zip | [17] | 예 |
| v2_15_settings_env | 4 | Project per-user item limit: 73 → 91 | [9, 13] | 예 |
| v2_15_settings_env | 11 | Project schema URL: /schema/finch.json → /internal/finch-schema.json | [13, 18] | 예 |
| v2_16_scopes_user_model | 4 | Explicit access-token lifetime in minutes: 23 → 41 | [13] | 예 |
| v2_16_scopes_user_model | 11 | Swagger UI URL: /bench-62 → /bench-94 | [16] | 예 |
| v2_17_request_internals | 4 | Session cookie max_age in seconds: 1380 → 2460 | [13, 16] | 예 |
| v2_17_request_internals | 11 | Timing response header name: X-Quartz-Latency → X-Quartz-Elapsed | [13, 18] | 예 |
| v2_18_integrations | 4 | Stripped public prefix: /edge/r9 → /edge/r11 | [13] | 예 |
| v2_18_integrations | 11 | GraphQL router prefix: /query-cedar → /query-larch | [16] | 예 |
| v2_19_first_service | 4 | Inclusive item ID ceiling: 731 → 947 | [17] | 예 |
| v2_19_first_service | 11 | Application import target: service.api:app → service.gateway:app | [13, 18] | 예 |
| v2_20_client_contract | 4 | Generated client output directory: src/nebula-sdk → packages/aster-client | [9, 18] | 예 |
| v2_20_client_contract | 11 | Public fetch operation ID: relics-fetch_relic → relics-load_relic | [13, 17] | 예 |
