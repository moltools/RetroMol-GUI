"""Approximate nearest neighbor search using HNSW index in Postgres."""

from typing import Any, Sequence

import sqlalchemy as sa
from sqlalchemy.orm import Session

from bionexus.db.models import CandidateCluster, Compound, Reference

from routes.database import SessionLocal


ANN_SEARCH_RADIUS = 1000

HNSW_SETTINGS = {
    "hnsw.iterative_scan": "strict_order",
    "hnsw.max_scan_tuples": 1_000_000,
    "hnsw.scan_mem_multiplier": 2,
    "hnsw.ef_search": 1000,
}


def _set_local(session: Session, settings: dict[str, Any]) -> None:
    """
    Set local session settings for Postgres.

    :param session: the SQLAlchemy session
    :param settings: a dictionary of settings to apply
    :raises ValueError: if an unsupported setting value type is provided
    """
    for k, v in settings.items():
        # Numbers must not be quoted; strings should be quoted
        if isinstance(v, str):
            session.execute(sa.text(f"SET LOCAL {k} = '{v}'"))
        elif isinstance(v, (int, float)):
            session.execute(sa.text(f"SET LOCAL {k} = {v}"))
        else:
            raise ValueError(f"unsupported setting value type: {type(v)} for key {k}")
        

def _ann_query(
    session: Session,
    model: type[CandidateCluster] | type[Compound],
    vector_col: Any,
    query_vec: list[float],
    where: Sequence[Any],
    limit: int,
) -> list[tuple[CandidateCluster | Compound, float]]:
    """
    Perform an approximate nearest neighbor search using the HNSW index.

    :param session: the SQLAlchemy session
    :param model: the SQLAlchemy model to query
    :param vector_col: the vector column to search against
    :param query_vec: the query vector
    :param where: additional filtering conditions
    :param limit: the maximum number of results to return
    :return: a list of tuples of (model instance, distance)
    """
    dist = vector_col.cosine_distance(query_vec).label("dist")
    stmt = (
        sa.select(model, dist)
        .where(*where)
        .order_by(dist.asc())
        .limit(limit)
    )
    return session.execute(stmt).all()


def ann_search(
    query_vec: list[float],
    query_against_clusters: bool,
    query_against_compounds: bool,
) -> list[tuple[CandidateCluster | Compound, float]]:
    """
    Perform an approximate nearest neighbor search against clusters and/or compounds.

    :param query_vec: the query vector
    :param query_against_clusters: whether to query against candidate clusters
    :param query_against_compounds: whether to query against compounds
    :return: a list of tuples of (model instance, distance)
    """
    if not query_against_clusters and not query_against_compounds:
        return []

    only_one = query_against_clusters ^ query_against_compounds
    per_type_limit = ANN_SEARCH_RADIUS if only_one else ANN_SEARCH_RADIUS // 2

    with SessionLocal() as session:
        _set_local(session, HNSW_SETTINGS)

        cluster_rows = (
            _ann_query(
                session=session,
                model=CandidateCluster,
                vector_col=CandidateCluster.retromol_fp_counted_by_region,
                query_vec=query_vec,
                where=[CandidateCluster.retromol_fp_counted_by_region.is_not(None)],
                limit=per_type_limit,
            )
            if query_against_clusters
            else []
        )

        compound_rows = (
            _ann_query(
                session=session,
                model=Compound,
                vector_col=Compound.retromol_fp_counted,
                query_vec=query_vec,
                where=[Compound.retromol_fp_counted.is_not(None)],
                limit=per_type_limit,
            )
            if query_against_compounds
            else []
        )

    combined = cluster_rows + compound_rows
    combined.sort(key=lambda x: x[1])  # sort by distance

    # Should not have more than ANN_SEARCH_RADIUS items now, but just in case
    return combined[:ANN_SEARCH_RADIUS]


def get_references(
    session: Session,
    model: type[CandidateCluster] | type[Compound],
    model_id: int,
) -> list[Reference]:
    """
    Get references for a given model instance.

    :param session: the SQLAlchemy session
    :param model: the SQLAlchemy model (CandidateCluster or Compound)
    :param model_id: the ID of the model instance
    :return: a list of Reference instances
    """
    stmt = (
        sa.select(Reference)
        .join(Reference.compounds if model is Compound else Reference.candidate_clusters)
        .where((Compound.id if model is Compound else CandidateCluster.id) == model_id)
        .order_by(Reference.database_name.asc(), Reference.database_identifier.asc())
    )

    return list(session.scalars(stmt).all())
