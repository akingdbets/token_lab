# 파일

- [본문 업데이트(PUT/PATCH)와 jsonable_encoder](body-updates-and-encoder.md) - fastapi.encoders.jsonable_encoder로 Pydantic 모델·datetime 등을 JSON 호환 dict/list로 변환하는 방법과 지원 타입·옵션, PUT으로 전체 교체할 때 기본값이 덮어쓰는 함정, PATCH 부분 업데이트(model_dump(exclude_unset=True) + model_copy(update=...)) 패턴을 설명한다.
- [추가 모델, Union 응답, dataclasses](extra-models-and-dataclasses.md) - 입력(UserIn)·출력(UserOut)·DB(UserInDB) 모델을 분리하고 상속(UserBase)으로 중복을 줄이는 방법, model_dump()와 ** 언패킹으로 모델 간 변환, Union(anyOf)·list·dict 응답 모델, 표준 dataclasses와 pydantic.dataclasses를 요청·응답에 사용하는 방법을 설명한다.
- [Pydantic v1에서 v2로 마이그레이션](pydantic-v1-to-v2.md) - 현재 FastAPI가 Pydantic v2만 지원하게 된 버전 이력(0.100.0, 0.119.0, 0.126.0, 0.128.0), Python 3.14에서 pydantic.v1 미지원, 테스트와 bump-pydantic으로 마이그레이션하는 방법, 과거 0.119~0.127에서 제공된 pydantic.v1 임시 지원과 현재 버전에서 pydantic.v1 모델 사용 시 PydanticV1NotSupportedError가 발생한다는 점을 설명한다.
- [스키마 예제 선언](schema-examples.md) - 문서(/docs)에 요청 예제를 표시하는 방법—Pydantic model_config의 json_schema_extra, Field(examples=[...]), Path/Query/Header/Cookie/Body/Form/File의 examples(JSON Schema 예제 리스트)와 openapi_examples(summary·description·value를 가진 OpenAPI 전용 예제 dict)—와 example/examples의 역사적 차이를 설명한다.
