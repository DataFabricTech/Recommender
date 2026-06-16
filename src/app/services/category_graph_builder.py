"""데이터 카테고리 차트용 그래프 생성 (순수 로직, numpy/sklearn/scipy 만 의존).

기존 리커맨더 임베딩(테이블 N×d)을 K-기반 클러스터링(K=카테고리 수)으로 군집화하고,
각 군집의 centroid 를 '사전정의 카테고리' 임베딩에 1:1 최적배정(헝가리안)으로 매핑한다.
출력: 루트 + 카테고리 노드(20) + 테이블 노드 + 엣지(루트→카테고리→테이블).
포털 카테고리 네트워크맵(드릴다운)이 그대로 읽는 형태.
"""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
from scipy.optimize import linear_sum_assignment
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity

ROOT_ID = "__root__"
ROOT_NAME = "전체 데이터"


def _l2_normalize(mat: np.ndarray) -> np.ndarray:
    mat = np.asarray(mat, dtype=np.float64)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


def assign_clusters_to_categories(centroids: np.ndarray, category_emb: np.ndarray):
    """centroid(K×d) ↔ category(K×d) 코사인 유사도로 1:1 최적배정.

    반환: (cluster_idx -> category_idx) dict, 유사도 행렬 K×K.
    """
    sim = cosine_similarity(centroids, category_emb)
    row, col = linear_sum_assignment(-sim)  # 유사도 최대화 = -sim 최소화
    return {int(r): int(c) for r, c in zip(row, col)}, sim


def build_category_graph(
    table_emb,
    ids,
    node_meta,
    category_names,
    category_emb,
    *,
    random_state: int = 42,
    n_init: int = 10,
) -> dict:
    """카테고리 차트 graph payload 생성.

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

    # 코사인 기반이 되도록 L2 정규화 후 K-Means (정규화 공간에서 유클리드 ≈ 코사인)
    table_norm = _l2_normalize(table_emb)
    km = KMeans(n_clusters=K, random_state=random_state, n_init=n_init)
    labels = km.fit_predict(table_norm)
    centroids = km.cluster_centers_

    cluster_to_cat, _sim = assign_clusters_to_categories(centroids, category_emb)

    cat_counts = [0] * K
    table_nodes = []
    edges = []
    for i, mid in enumerate(ids):
        cat = cluster_to_cat[int(labels[i])]
        cat_counts[cat] += 1
        meta = node_meta.get(mid, {})
        table_nodes.append({
            "id": mid,
            "label": meta.get("label") or mid,
            "system": meta.get("system") or "",
            "size": int(meta.get("size") or 0),
            "type": "table",
            "category": cat,
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
        "params": {"algorithm": "kmeans", "k": K, "mapping": "hungarian", "source": "embedding"},
        "stats": {"table_count": n, "category_count": K},
        "categories": categories,
        "nodes": nodes,
        "edges": edges,
    }
