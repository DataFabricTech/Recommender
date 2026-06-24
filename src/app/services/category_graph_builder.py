"""데이터 카테고리 차트용 그래프 생성 (순수 로직, numpy 만 의존).

기존 리커맨더 임베딩(테이블 N×d)을 '사전정의 카테고리' 임베딩(K×d)과 직접 비교하여,
각 테이블을 코사인 유사도가 가장 높은 카테고리 1개에 직접 배정한다(다대일).
출력: 루트 + 카테고리 노드(K) + 테이블 노드 + 엣지(루트→카테고리→테이블).
포털 카테고리 네트워크맵(드릴다운)이 그대로 읽는 형태.

직접 배정을 쓰는 이유: 군집화(K-Means)+1:1 최적배정(헝가리안)은 군집 전체를 한 카테고리에
'억지로' 짝지어, 잘 안 맞는 군집의 테이블이 엉뚱한 카테고리로 끌려간다. 테이블마다 가장
비슷한 카테고리를 직접 고르면 그 떠밀림이 사라져 분류 정확도가 높다.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

ROOT_ID = "__root__"
ROOT_NAME = "전체 데이터"


def _l2_normalize(mat: np.ndarray) -> np.ndarray:
    mat = np.asarray(mat, dtype=np.float64)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


def build_category_graph(
    table_emb,
    ids,
    node_meta,
    category_names,
    category_emb,
    *,
    random_state: int = 42,  # 하위호환용(미사용)
    n_init: int = 10,        # 하위호환용(미사용)
) -> dict:
    """카테고리 차트 graph payload 생성 (직접 배정).

    table_emb: 테이블 임베딩 N×d
    ids: meta_id N개 (table_emb 행 순서와 동일)
    node_meta: {meta_id: {label, system, size}}
    category_names: 사전정의 카테고리 이름 K개
    category_emb: 카테고리 임베딩 K×d (table_emb 와 동일 임베딩 공간)
    """
    table_emb = np.asarray(table_emb, dtype=np.float64)
    category_emb = np.asarray(category_emb, dtype=np.float64)
    K = len(category_names)
    n = len(ids)
    if table_emb.shape[0] != n:
        raise ValueError(f"임베딩 수({table_emb.shape[0]})와 ids 수({n})가 다릅니다")
    if category_emb.shape[0] != K:
        raise ValueError(f"카테고리 임베딩 수({category_emb.shape[0]})와 이름 수({K})가 다릅니다")

    # L2 정규화 후 내적 = 코사인 유사도. 각 테이블을 가장 가까운 카테고리에 직접 배정.
    table_norm = _l2_normalize(table_emb)
    cat_norm = _l2_normalize(category_emb)
    sims = table_norm @ cat_norm.T        # N×K 코사인 유사도
    assign = sims.argmax(axis=1)          # 테이블별 최적 카테고리
    best = sims.max(axis=1)               # 그 유사도(대표성)

    cat_counts = [0] * K
    table_nodes = []
    edges = []
    for i, mid in enumerate(ids):
        cat = int(assign[i])
        cat_counts[cat] += 1
        similarity = float(best[i])  # 대표성: 높을수록 카테고리에 가까움
        meta = node_meta.get(mid, {})
        table_nodes.append({
            "id": mid,
            "label": meta.get("label") or mid,
            "system": meta.get("system") or "",
            "size": int(meta.get("size") or 0),
            "type": "table",
            "category": cat,
            "similarity": round(similarity, 6),
        })
        edges.append({"source": f"cat_{cat}", "target": mid})

    categories = []
    nodes = [{"id": ROOT_ID, "label": ROOT_NAME, "type": "root"}]
    for c, name in enumerate(category_names):
        categories.append({"id": c, "name": name, "size": cat_counts[c]})
        nodes.append({"id": f"cat_{c}", "label": name, "type": "category", "size": cat_counts[c]})
        edges.append({"source": ROOT_ID, "target": f"cat_{c}"})
    nodes.extend(table_nodes)

    return {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "params": {"algorithm": "direct", "k": K, "mapping": "argmax", "source": "embedding"},
        "stats": {"table_count": n, "category_count": K},
        "categories": categories,
        "nodes": nodes,
        "edges": edges,
    }
