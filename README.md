# Recommender

## 개요

- 본 서비스는 데이터에 대한 `유사도 측정 기반의 추천 시스템`으로, 기존에 수집된 데이터들과의 유사도를 판단하여 관련된 데이터를 추천합니다.
  사용자는 특정 데이터 ID를 입력하면 관련된 추천 데이터를 응답 받을 수 있습니다.
- 본 시스템은 빠르고 간단한 추천이 필요한 경우에는 `클러스터링 기반 추천`, 고정밀의 결과가 필요한 경우에는 `임베딩 기반 추천`을 수행합니다.

## 주요 기능 및 서비스 흐름

### Clustering 기반 추천

- 빠르게 유사 데이터를 추천하는 데 사용
- 사전 학습된 클러스터 정보를 바탕으로 동작
- `/clustering` 관련 라우터에서 처리

### Embedding 기반 추천

- 문장 임베딩을 기반으로 정밀한 유사도 측정
- 처리 시간이 오래 걸리기 때문에 **Scheduler 기반 주기적 실행**
- `/embedding` 관련 라우터에서 처리

## 입출력 구조
- 입력
  - 사용자로부터 전달되는 `id` 값 또는 `데이터 요청 객체`
  - 대부분 FastAPI 기반의 `POST` 요청으로 전달됨
- 출력
  - 공통적으로 `response_model.py`에 정의된 구조 사용

## 사용자 / 운영자 관점 흐름
- 운영자(데이터 처리자)
  - 신규 데이터 수집(Scheduler를 통한 주기적 수집)
  - 수집 데이터를 기반으로 Clustering 및 Embedding 처리
  - 결과를 DB 혹은 File로 저장
- 사용자
  - 기존 데이터 추천
    - 사용자 요청 : 특정 ID를 API에 요청
    - 처리 흐름 : 해당 ID에 대한 데이터 조회
    - 응답 결과 : 유사한 기존 데이터 목록 반환
  - 신규 데이터 추천
    - 사용자 요청 : 특정 ID와 Data의 유형(Table, Storage)을 API예 요청
    - 처리 흐름 : 기존 학습 값과 신규 데이터간 유사도 계산
    - 응답 결과 : 가장 유사한 기존 데이터의 대표명을 기준으로 추천

## 모델 / 알고리즘 교체를 위한 수정 지점 안내
- Clustering (training_router.py/__init_clustering)
  - vectorizer 라이브러리 변경 (현재 : from sklearn.feature_extraction.text import TfidfVectorizer)
  - cluster 방식 변경 (현재 : hdbscan.HDBSCAN, metric: cosine)
- 대표값 알고리즘 (training_router.py/__get_representative_value_by_similarity)
  - 밀집도 계산 라이브러리 변경 (현재 : from sklearn.metrics import pairwise_distances) 
- Embedding (training_router.py/__)
  - 유사도 계산 라이브러리 변경 (현재 : from sklearn.metrics.pairwise import cosine_similarity)
  - tokenizer 변경 (현재 : from transformers import BertTokenizer, BertModel)
  - bert 사전 학습 모델 (현재 : klue/bert-base)
- 각 알고리즘 / 라이브러리를 선택한 이유
  - docs/recommender 문서들

## 실제 데이터 예시
- Clustering
  - Request
    - Method: Get
    - URL: http://0.0.0.0:8080/api/recommend/clustering?target_id={target_id}
  - Resposne
    - ```json  
      {
          "status": 200,
          "code": null,
          "data": {
              "recommended": [
                  "5b7254e5-a46d-430f-b237-9baa2697cf56",
                  "06bda172-b828-40e3-ac79-e1f61c34bc5e",
                  "c73a9692-91a4-4ad2-9793-1a9e493c975a",
                  "393b2921-2a8f-45fe-aed7-f00b2a6a65df"
              ]
          },
          "error": null
      }
- Embedding
  - Request
    - Method: Get
    - URL: http://0.0.0.0:8080/api/recommend/embedding?target_id={target_id}
  - Resposne
    - ```json  
      {
          "status": 200,
          "code": null,
          "data": {
              "recommended": [
                  "393b2921-2a8f-45fe-aed7-f00b2a6a65df",
                  "06bda172-b828-40e3-ac79-e1f61c34bc5e",
                  "5b7254e5-a46d-430f-b237-9baa2697cf56",
                  "562d5b7c-d5ac-4f45-90e1-dfa6fcfc3bc1",
                  "344fe071-0ccb-4ee3-98f8-c70721853fc4"
              ]
          },
          "error": null
      }

## 실행 방법

- docker run -it --rm -v ${ConfigFilePath}:/app/config_templates/config.yml -p 8080:8080
  repo.iris.tools/datafabric/recommender:${ImageTag}

## 시스템 구조
```
main.py
├── app/
│   ├── init/config.py
│   ├── models/
│   │   ├── dictionary_enum.py
│   │   ├── recommend_classes.py
│   │   └── response_model.py         <- 응답 모델
│   ├── routers/
│   │   ├── cataloging_router.py      <- 신규 데이터 추천 
│   │   ├── clustering_router.py      <- 클러스터링 추천
│   │   ├── embedding_router.py       <- 임베딩 추천
│   │   ├── training_router.py        <- 학습/스케줄 관리
│   │   └── check.py                  <- 헬스 체크
├── services/
│   └── open_metadata_service.py      <- 외부 데이터 연동
├── common/
│   ├── config/
│   │   ├── base_config.py 
│   │   └── user_config.py
│   ├── errors/exceptions.py
│   ├── async_loop.py                 <- 비동기 로직
│   └── log.py                        <- 로깅
└── server.py
```

## Swagger 문서

- http://127.0.0.1:8080/recommender/docs
- http://192.168.109.254:30628/recommender/docs