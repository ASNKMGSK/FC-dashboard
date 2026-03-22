"""
automation/troubleshooting_engine.py - 고장대응 가이드 자동 생성 엔진
================================================
정비이력 TF-IDF 임베딩 → 실루엣 계수 최적 K → K-Means 클러스터링 → LLM 고장대응 가이드 생성
"""
import json
import random
import re
import uuid
import time
from typing import Dict, List, Any, Optional

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import MiniBatchKMeans
from sklearn.metrics import silhouette_score
from sklearn.decomposition import PCA
from core.utils import safe_str, safe_int
from core.constants import WORK_ORDER_CATEGORIES
from automation.action_logger import (
    save_faq,
    get_faq,
    get_all_faqs,
    delete_faq,
    update_faq_status,
    log_action,
    create_pipeline_run,
    update_pipeline_step,
    complete_pipeline_run,
)
import state as st



def _find_optimal_k(tfidf_matrix) -> dict:
    """실루엣 계수로 최적 K를 탐색합니다. k_max는 데이터 크기에 비례."""
    n_samples = tfidf_matrix.shape[0]
    k_max = min(max(n_samples // 8, 3), 10, n_samples - 1)
    k_min = 2
    if k_max < k_min:
        return {"optimal_k": k_min, "silhouette": 0.0, "scores": []}

    scores = []
    for k in range(k_min, k_max + 1):
        kmeans = MiniBatchKMeans(n_clusters=k, random_state=42, n_init=3, batch_size=256)
        labels = kmeans.fit_predict(tfidf_matrix)
        score = silhouette_score(tfidf_matrix, labels)
        scores.append({"k": k, "silhouette": round(float(score), 4)})

    best = max(scores, key=lambda x: x["silhouette"])
    return {
        "optimal_k": best["k"],
        "silhouette": best["silhouette"],
        "scores": scores,
    }


def _cluster_with_optimal_k(texts: List[str]) -> Dict[str, Any]:
    """TF-IDF + 실루엣 최적 K + MiniBatchKMeans 클러스터링 (메모리 효율적)."""
    if len(texts) < 3:
        return {
            "optimal_k": 1,
            "silhouette": 0.0,
            "scores": [],
            "clusters": [{"cluster_id": 0, "size": len(texts), "representative": texts[0] if texts else "", "samples": texts[:3]}],
        }

    vectorizer = TfidfVectorizer(max_features=500, max_df=0.95, min_df=1)
    tfidf_matrix = vectorizer.fit_transform(texts)

    k_result = _find_optimal_k(tfidf_matrix)
    optimal_k = k_result["optimal_k"]

    kmeans = MiniBatchKMeans(n_clusters=optimal_k, random_state=42, n_init=3, batch_size=256)
    labels = kmeans.fit_predict(tfidf_matrix)

    n_components = min(2, tfidf_matrix.shape[1])
    pca = PCA(n_components=n_components)
    coords_2d = pca.fit_transform(tfidf_matrix.toarray())
    centroids_2d = pca.transform(kmeans.cluster_centers_)

    clusters = []
    points = []
    for cid in range(optimal_k):
        mask = labels == cid
        indices = np.where(mask)[0]
        cluster_texts = [texts[i] for i in indices]

        center = kmeans.cluster_centers_[cid]
        dists = np.asarray(tfidf_matrix[indices].dot(center.T)).flatten()
        rep_idx = indices[np.argmax(dists)]

        clusters.append({
            "cluster_id": cid,
            "size": int(mask.sum()),
            "representative": texts[rep_idx],
            "samples": cluster_texts[:5],
        })

        for idx in indices:
            points.append({
                "x": round(float(coords_2d[idx][0]), 4),
                "y": round(float(coords_2d[idx][1]), 4),
                "cluster": cid,
                "text": texts[idx][:40],
            })

    clusters.sort(key=lambda x: x["size"], reverse=True)

    centroid_points = [
        {"x": round(float(centroids_2d[cid][0]), 4),
         "y": round(float(centroids_2d[cid][1]), 4),
         "cluster": cid}
        for cid in range(optimal_k)
    ]

    return {
        "optimal_k": optimal_k,
        "silhouette": k_result["silhouette"],
        "scores": k_result["scores"],
        "clusters": clusters,
        "points": points,
        "centroids": centroid_points,
    }


def _cluster_with_llm(texts: List[str], category: str = "", **_kwargs) -> Dict[str, Any]:
    """LLM 미사용 — TF-IDF+K-Means 클러스터링으로 대체합니다."""
    # LLM 제거 후 kmeans 방식으로 폴백
    return _cluster_with_optimal_k(texts)


def analyze_maintenance_patterns(
    category: Optional[str] = None,
    top_n: int = 10,
    mode: str = "kmeans",
) -> Dict[str, Any]:
    """고장/정비 이력 패턴 분석. mode='kmeans' (TF-IDF+K-Means) 또는 mode='llm' (K-Means 폴백)."""
    if st.WORK_ORDERS_DF is None or "inquiry_text" not in st.WORK_ORDERS_DF.columns:
        return _analyze_stats_fallback(category)

    df = st.WORK_ORDERS_DF.copy()
    cat_col = "category" if "category" in df.columns else None

    categories = []
    if cat_col:
        total = len(df)
        for cat, grp in df.groupby(cat_col):
            categories.append({
                "category": str(cat),
                "count": len(grp),
                "percentage": round(len(grp) / total * 100, 1),
            })
        categories.sort(key=lambda x: x["count"], reverse=True)

    cluster_fn = _cluster_with_llm if mode == "llm" else _cluster_with_optimal_k
    method_name = "llm" if mode == "llm" else "clustering"

    if category:
        if cat_col:
            df = df[df[cat_col] == category]
        if len(df) == 0:
            return {"total_records": 0, "clusters": [], "categories": categories,
                    "category_results": [], "method": method_name}

        texts = df["inquiry_text"].dropna().tolist()
        if mode == "llm":
            result = cluster_fn(texts, category=category)
        else:
            result = cluster_fn(texts)
        cat_result = {
            "category": category,
            "count": len(texts),
            "optimal_k": result["optimal_k"],
            "silhouette": result["silhouette"],
            "scores": result["scores"],
            "clusters": result["clusters"],
            "points": result.get("points", []),
            "centroids": result.get("centroids", []),
        }
        return {
            "total_records": len(texts),
            "clusters": result["clusters"],
            "categories": categories,
            "category_results": [cat_result],
            "method": method_name,
        }

    category_results = []
    all_clusters = []

    if cat_col:
        cat_groups = [(str(cat), grp) for cat, grp in df.groupby(cat_col)]

        if mode == "llm" and len(cat_groups) > 3:
            cat_groups_sorted = sorted(cat_groups, key=lambda x: len(x[1]), reverse=True)
            cat_groups = random.sample(cat_groups_sorted[:6], min(3, len(cat_groups_sorted)))

        for cat, grp in cat_groups:
            texts = grp["inquiry_text"].dropna().tolist()
            if len(texts) < 2:
                continue
            if mode == "llm":
                result = cluster_fn(texts, category=cat)
            else:
                result = cluster_fn(texts)
            for cl in result["clusters"]:
                cl["category"] = cat
            cat_result = {
                "category": cat,
                "count": len(texts),
                "optimal_k": result["optimal_k"],
                "silhouette": result["silhouette"],
                "scores": result["scores"],
                "clusters": result["clusters"],
                "points": result.get("points", []),
                "centroids": result.get("centroids", []),
            }
            category_results.append(cat_result)
            all_clusters.extend(result["clusters"])
    else:
        texts = df["inquiry_text"].dropna().tolist()
        if mode == "llm":
            result = cluster_fn(texts)
        else:
            result = cluster_fn(texts)
        all_clusters = result["clusters"]
        category_results = [{"category": "전체", "count": len(texts),
                             "optimal_k": result["optimal_k"],
                             "silhouette": result["silhouette"],
                             "scores": result["scores"],
                             "clusters": result["clusters"]}]

    all_clusters.sort(key=lambda x: x["size"], reverse=True)

    return {
        "total_records": len(df),
        "clusters": all_clusters[:top_n],
        "categories": categories,
        "category_results": category_results,
        "method": method_name,
    }


# 하위 호환성
analyze_cs_patterns = analyze_maintenance_patterns


def _analyze_stats_fallback(category: Optional[str] = None) -> Dict[str, Any]:
    """통계 기반 fallback 분석."""
    if st.MAINTENANCE_STATS_DF is None:
        return {"total_records": 0, "clusters": [], "categories": [],
                "category_results": [], "method": "no_data"}

    df = st.MAINTENANCE_STATS_DF
    cat_col = "category" if "category" in df.columns else "ticket_category"
    if cat_col not in df.columns or "total_tickets" not in df.columns:
        return {"total_records": 0, "clusters": [], "categories": [],
                "category_results": [], "method": "stats_fallback"}

    total = safe_int(df["total_tickets"].sum())
    categories = []
    for _, row in df.iterrows():
        count = safe_int(row["total_tickets"])
        pct = round(count / total * 100, 1) if total > 0 else 0.0
        categories.append({"category": safe_str(row[cat_col]), "count": count, "percentage": pct})
    categories.sort(key=lambda x: x["count"], reverse=True)

    if category:
        categories = [c for c in categories if c["category"] == category]

    return {
        "total_records": total,
        "clusters": [],
        "categories": categories,
        "category_results": [],
        "method": "stats_fallback",
    }


def _generate_guide_from_cluster(cl: Dict, category: Optional[str] = None) -> Dict:
    """클러스터 대표 텍스트를 기반으로 템플릿 가이드를 생성합니다."""
    representative = cl.get("representative", "")
    samples = cl.get("samples", [])
    cat = category or cl.get("category", "기타")
    size = cl.get("size", 0)

    question = representative if representative else (samples[0] if samples else "알 수 없는 고장")
    sample_text = ", ".join(samples[:3]) if samples else "없음"

    answer = (
        f"[대응 절차]\n"
        f"1. 현상 확인: '{question}' 증상 발생 시 즉시 설비 가동을 중단하고 안전 확보\n"
        f"2. 원인 분석: 유사 사례({size}건) 기반 — {sample_text}\n"
        f"3. 조치 실행: 해당 부위 점검 및 부품 상태 확인, 필요 시 교체\n"
        f"4. 재발 방지: 정비 이력 기록 및 예방 점검 주기 조정"
    )

    tags = [cat]
    if size > 10:
        tags.append("빈발")
    if any(kw in question for kw in ("긴급", "비상", "정지", "화재")):
        tags.append("긴급")

    return {
        "question": question,
        "answer": answer,
        "category": cat,
        "tags": tags,
    }


def generate_troubleshooting_guide(
    category: Optional[str] = None,
    count: int = 5,
    mode: str = "kmeans",
    selected_clusters: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """클러스터링 결과 기반으로 템플릿을 사용하여 고장대응 가이드를 자동 생성합니다.
    selected_clusters가 주어지면 재분석 없이 해당 클러스터만 사용합니다."""
    run_id = None
    try:
        if category and category not in WORK_ORDER_CATEGORIES:
            return {
                "generated_count": 0, "guides": [],
                "error": f"유효하지 않은 카테고리입니다: {category}. "
                         f"사용 가능: {', '.join(WORK_ORDER_CATEGORIES)}",
            }

        run_id = create_pipeline_run("troubleshooting", ["analyze", "generate", "review", "approve"])

        if selected_clusters:
            clusters = selected_clusters
            method = mode
            update_pipeline_step(run_id, "analyze", "complete", {
                "method": method,
                "clusters": len(clusters),
                "category": category or "all",
                "note": "사용자 선택 클러스터",
            })
        else:
            update_pipeline_step(run_id, "analyze", "processing")
            patterns = analyze_maintenance_patterns(category=category, top_n=count * 2, mode=mode)
            clusters = patterns.get("clusters", [])
            method = patterns.get("method", "no_data")

            update_pipeline_step(run_id, "analyze", "complete", {
                "method": method,
                "total": patterns.get("total_records", 0),
                "clusters": len(clusters),
                "category": category or "all",
            })

            if not clusters and not patterns.get("categories"):
                return {"generated_count": 0, "guides": [], "warning": "분석할 고장/정비 이력 데이터가 없습니다."}

        update_pipeline_step(run_id, "generate", "processing")

        saved_guides = []
        for cl in clusters[:count]:
            guide_item = _generate_guide_from_cluster(cl, category)
            guide_id = str(uuid.uuid4())[:8]
            guide_data = {
                "id": guide_id,
                "question": safe_str(guide_item["question"]),
                "answer": safe_str(guide_item["answer"]),
                "category": safe_str(guide_item["category"]),
                "tags": guide_item.get("tags", []),
                "status": "draft",
                "created_at": time.time(),
            }
            save_faq(guide_id, guide_data)
            saved_guides.append(guide_data)

        update_pipeline_step(run_id, "generate", "complete", {"count": len(saved_guides)})

        log_action(
            "troubleshooting_generate",
            "system",
            {"count": len(saved_guides), "category": category or "all", "method": method},
        )

        return {
            "generated_count": len(saved_guides),
            "guides": saved_guides,
            "faqs": saved_guides,  # 하위 호환성
            "pipeline_run_id": run_id,
            "method": method,
            "clusters_used": len(clusters),
        }

    except Exception as e:
        st.logger.error("고장대응 가이드 생성 실패: %s", str(e))
        if run_id:
            update_pipeline_step(run_id, "generate", "error", {"error": str(e)})
        return {"generated_count": 0, "guides": [], "error": str(e)}


# 하위 호환성
generate_faq_items = generate_troubleshooting_guide


def approve_faq(faq_id: str) -> Dict[str, Any]:
    ok = update_faq_status(faq_id, "approved")
    if not ok:
        return {"status": "error", "message": f"가이드 '{faq_id}'를 찾을 수 없습니다."}
    log_action("troubleshooting_approve", faq_id, {"guide_id": faq_id})
    return {"status": "success", "guide_id": faq_id}


def update_faq(faq_id: str, question: Optional[str] = None, answer: Optional[str] = None) -> Dict[str, Any]:
    existing = get_faq(faq_id)
    if not existing:
        return {"status": "error", "message": f"가이드 '{faq_id}'를 찾을 수 없습니다."}
    updated_fields = []
    if question is not None:
        existing["question"] = question
        updated_fields.append("question")
    if answer is not None:
        existing["answer"] = answer
        updated_fields.append("answer")
    if not updated_fields:
        return {"status": "error", "message": "수정할 필드가 없습니다."}
    existing["updated_at"] = time.time()
    save_faq(faq_id, existing)
    log_action("troubleshooting_update", faq_id, {"updated_fields": updated_fields})
    return {"status": "success", "guide_id": faq_id, "updated_fields": updated_fields}


def delete_faq_item(faq_id: str) -> Dict[str, Any]:
    ok = delete_faq(faq_id)
    if not ok:
        return {"status": "error", "message": f"가이드 '{faq_id}'를 찾을 수 없습니다."}
    log_action("troubleshooting_delete", faq_id, {"guide_id": faq_id})
    return {"status": "success", "guide_id": faq_id}


def list_faqs(status: Optional[str] = None) -> Dict[str, Any]:
    all_faqs = get_all_faqs()
    if status and status != "all":
        all_faqs = [f for f in all_faqs if f.get("status") == status]
    return {"total": len(all_faqs), "guides": all_faqs, "faqs": all_faqs}


def _parse_faq_json(raw: str) -> List[Dict[str, Any]]:
    try:
        result = json.loads(raw)
        if isinstance(result, list):
            return result
    except (json.JSONDecodeError, TypeError):
        pass
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if match:
        try:
            result = json.loads(match.group(1))
            if isinstance(result, list):
                return result
        except (json.JSONDecodeError, TypeError):
            pass
    match = re.search(r"\[[\s\S]*\]", raw)
    if match:
        try:
            result = json.loads(match.group(0))
            if isinstance(result, list):
                return result
        except (json.JSONDecodeError, TypeError):
            pass
    return []
