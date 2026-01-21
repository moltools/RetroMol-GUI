"""Enrichment analysis for query items using annotation labels."""

from __future__ import annotations

from collections import defaultdict
import math
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import selectinload
from flask import current_app

from bionexus.db.models import CandidateCluster, Compound

from routes.database import SessionLocal
from routes.query.align import score_by_alignment
from routes.query.featurize import featurize_item, format_payload_readout, load_payload
from routes.query.retrieve import ann_search, ANN_SEARCH_RADIUS


LabelKey = tuple[str, str, str]


def _log_comb(n: int, k: int) -> float:
    if k < 0 or k > n:
        return float("-inf")
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def _log_hypergeom_pmf(k: int, K: int, N: int, n: int) -> float:
    if k < 0 or k > K or k > n or n > N:
        return float("-inf")
    return _log_comb(K, k) + _log_comb(N - K, n - k) - _log_comb(N, n)


def _hypergeom_sf(k: int, K: int, N: int, n: int) -> float:
    max_i = min(K, n)
    if k > max_i:
        return 0.0
    log_terms = [_log_hypergeom_pmf(i, K, N, n) for i in range(k, max_i + 1)]
    max_log = max(log_terms)
    total = sum(math.exp(term - max_log) for term in log_terms)
    return math.exp(max_log) * total


def _benjamini_hochberg(pvals: list[float]) -> list[float]:
    m = len(pvals)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvals[i])
    adjusted = [0.0] * m
    min_adj = 1.0
    for rank in range(m, 0, -1):
        idx = order[rank - 1]
        adj = pvals[idx] * m / rank
        if adj < min_adj:
            min_adj = adj
        adjusted[idx] = min(min_adj, 1.0)
    return adjusted


def _annotation_labels(obj: Any) -> set[LabelKey]:
    labels: set[LabelKey] = set()
    annotations = getattr(obj, "annotations", None) or []
    for ann in annotations:
        scheme = getattr(ann, "scheme", None)
        key = getattr(ann, "key", None)
        value = getattr(ann, "value", None)
        if scheme is None or key is None or value is None:
            continue
        labels.add((str(scheme), str(key), str(value)))
    return labels


def _label_counts_for_model(
    session: Any,
    model: type[CandidateCluster] | type[Compound],
) -> dict[LabelKey, int]:
    rel = sa.inspect(model).relationships.get("annotations")
    ann_attr = getattr(model, "annotations", None)
    if rel is None or ann_attr is None:
        return {}

    ann_cls = rel.mapper.class_
    stmt = (
        sa.select(
            ann_cls.scheme,
            ann_cls.key,
            ann_cls.value,
            sa.func.count(sa.distinct(model.id)),
        )
        .select_from(model)
        .join(ann_attr)
        .group_by(ann_cls.scheme, ann_cls.key, ann_cls.value)
    )
    rows = session.execute(stmt).all()
    return {
        (str(scheme), str(key), str(value)): int(count)
        for scheme, key, value, count in rows
    }


def _population_label_counts(
    query_against_clusters: bool,
    query_against_compounds: bool,
) -> tuple[dict[LabelKey, int], int]:
    counts: dict[LabelKey, int] = defaultdict(int)
    total = 0

    with SessionLocal() as session:
        if query_against_clusters:
            total += int(session.execute(
                sa.select(sa.func.count(CandidateCluster.id))
            ).scalar_one() or 0)
            for label, count in _label_counts_for_model(session, CandidateCluster).items():
                counts[label] += count

        if query_against_compounds:
            total += int(session.execute(
                sa.select(sa.func.count(Compound.id))
            ).scalar_one() or 0)
            for label, count in _label_counts_for_model(session, Compound).items():
                counts[label] += count

    return counts, total


def _load_annotation_map(
    items: list[CandidateCluster | Compound],
) -> dict[tuple[str, int], set[LabelKey]]:
    cluster_ids = [i.id for i in items if isinstance(i, CandidateCluster)]
    compound_ids = [i.id for i in items if isinstance(i, Compound)]

    labels_by_key: dict[tuple[str, int], set[LabelKey]] = {}

    with SessionLocal() as session:
        if cluster_ids:
            clusters = session.execute(
                sa.select(CandidateCluster)
                .where(CandidateCluster.id.in_(cluster_ids))
                .options(selectinload(CandidateCluster.annotations))
            ).scalars().all()
            for cluster in clusters:
                labels_by_key[("cluster", cluster.id)] = _annotation_labels(cluster)

        if compound_ids:
            compounds = session.execute(
                sa.select(Compound)
                .where(Compound.id.in_(compound_ids))
                .options(selectinload(Compound.annotations))
            ).scalars().all()
            for compound in compounds:
                labels_by_key[("compound", compound.id)] = _annotation_labels(compound)

    return labels_by_key


def enrichment_study(
    payload_type: str,
    payload_blob: dict[str, Any],
    query_against_clusters: bool,
    query_against_compounds: bool,
    threshold_pct: float,
) -> dict[str, Any]:
    if threshold_pct < 0.0 or threshold_pct > 100.0:
        raise ValueError("threshold_pct must be between 0 and 100")

    query_vec, query_blocks = featurize_item(payload_type, payload_blob)

    nns: list[tuple[CandidateCluster | Compound, float]] = ann_search(
        query_vec,
        query_against_clusters=query_against_clusters,
        query_against_compounds=query_against_compounds,
    )
    current_app.logger.debug("enrichment: found %s nearest neighbors", len(nns))

    if not nns or not query_blocks:
        raise ValueError("no nearest neighbors found or query blocks are empty")

    nns_featurized = []
    retrieved_items: list[CandidateCluster | Compound] = []
    retrieved_keys: list[tuple[str, int] | None] = []

    for item, _distance in nns:
        assert isinstance(item, (CandidateCluster, Compound))
        item_type = "cluster" if isinstance(item, CandidateCluster) else "compound"
        item_blob = item.biocracker if item_type == "cluster" else item.retromol
        item_payload = load_payload(item_type, item_blob)
        item_db_id = getattr(item, "id", None)
        item_readout = format_payload_readout(item_type, item_payload, item_db_id)
        nns_featurized.append(item_readout)
        retrieved_items.append(item)
        retrieved_keys.append((item_type, item_db_id) if item_db_id is not None else None)

    if not nns_featurized:
        raise ValueError("failed to featurize nearest neighbors")

    _, self_scores, _ = score_by_alignment(query_blocks, [query_blocks])
    if not self_scores:
        raise ValueError("failed to compute self alignment score")

    self_score = float(self_scores[0])
    if self_score <= 0.0:
        raise ValueError("self alignment score is non-positive; threshold invalid")

    alignment_results = score_by_alignment(query_blocks, nns_featurized)
    _aln_results, aln_scores, _match_scores = alignment_results

    threshold_score = self_score * (threshold_pct / 100.0)

    in_group_indices = [i for i, score in enumerate(aln_scores) if score >= threshold_score]
    in_group_set = set(in_group_indices)

    total_neighbors = len(retrieved_items)
    in_group_count = len(in_group_set)

    warnings: list[str] = []
    if in_group_count == 0:
        warnings.append("No candidates meet the alignment threshold; enrichment cannot be computed.")
    if in_group_count == total_neighbors and total_neighbors > 0:
        warnings.append(
            "All candidates are in the in-group; enrichment results may be unreliable."
        )

    labels_by_key = _load_annotation_map(retrieved_items)
    population_counts, population_total = _population_label_counts(
        query_against_clusters=query_against_clusters,
        query_against_compounds=query_against_compounds,
    )
    out_group_count = population_total - in_group_count
    if out_group_count < 0:
        warnings.append("In-group exceeds population size; check background query scope.")
        out_group_count = 0
    if population_total == 0:
        warnings.append("No items available in the database for the selected types.")

    in_group_counts: dict[LabelKey, int] = defaultdict(int)

    for idx, key in enumerate(retrieved_keys):
        if key is None:
            continue
        labels = labels_by_key.get(key, set())
        for label in labels:
            if idx in in_group_set:
                in_group_counts[label] += 1

    if not in_group_counts:
        warnings.append("No annotations found in the in-group.")
    if not population_counts:
        warnings.append("No annotations found in the database background.")

    results: list[dict[str, Any]] = []

    if in_group_count > 0 and population_counts:
        pvals: list[float] = []
        labels: list[LabelKey] = []
        for label, hits_in_group in in_group_counts.items():
            total_hits = population_counts.get(label, 0)
            if total_hits <= 0:
                continue
            if hits_in_group <= 0:
                continue
            pval = _hypergeom_sf(hits_in_group, total_hits, population_total, in_group_count)
            pvals.append(pval)
            labels.append(label)

        adjusted = _benjamini_hochberg(pvals)
        for (scheme, key, value), pval, padj in zip(labels, pvals, adjusted):
            in_hits = in_group_counts.get((scheme, key, value), 0)
            total_hits = population_counts.get((scheme, key, value), 0)
            results.append({
                "label": {"scheme": scheme, "key": key, "value": value},
                "p_value": pval,
                "p_adjusted": padj,
                "in_group_count": in_hits,
                "background_count": total_hits,
                "in_group_fraction": in_hits / in_group_count if in_group_count else 0.0,
                "background_fraction": total_hits / population_total if population_total else 0.0,
            })

    results.sort(key=lambda r: (r["p_adjusted"], r["p_value"]))

    return {
        "summary": {
            "neighbors_requested": ANN_SEARCH_RADIUS,
            "total_neighbors": total_neighbors,
            "population_total": population_total,
            "in_group": in_group_count,
            "out_group": out_group_count,
            "threshold_pct": threshold_pct,
            "self_alignment_score": self_score,
            "alignment_threshold": threshold_score,
        },
        "warnings": warnings,
        "results": results,
    }
