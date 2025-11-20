"""Module for defining database query endpoints."""

import os
import time

import psycopg
from flask import Blueprint, request, jsonify
from psycopg import sql
from pgvector import Vector
from pgvector.psycopg import register_vector

from routes.helpers import hex_to_bits


blp = Blueprint("query", __name__)


# Knobs
DEFAULT_LIMIT = 500
MAX_OFFSET = 50_000
STATEMENT_TIMEOUT_MS = 3000  # 3 seconds


def dsn_from_env() -> str:
    """
    Construct the Postgres DSN from environment variables.

    :return: the Postgres DSN string
    """
    dsn = os.getenv("DATABASE_URL")
    if dsn:
        return dsn
    host = os.getenv("DB_HOST", "db")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "bionexus")
    user = os.getenv("DB_USER", "app_ro")
    pwd = os.getenv("DB_PASS") or os.getenv("DB_PASSWORD", "apppass_ro")
    return f"postgresql://{user}:{pwd}@{host}:{port}/{name}"


def preprocess_cross_modal_params(typed: dict) -> dict:
    """
    Preprocess parameters for the cross-modal retrieval query.

    :param typed: the typed parameters dictionary
    :return: the preprocessed parameters dictionary
    """
    fp_hex_string = typed["fingerprint512"]
    fp = hex_to_bits(fp_hex_string)
    fp = [float(x) for x in fp]
    typed["qv"] = Vector(fp)

    score_threshold = typed.get("querySettings", {}).get("scoreThreshold", 0.0)
    print(score_threshold)
    typed["score_threshold"] = score_threshold

    return typed


QUERIES = {
    "binned_coverage": {
        "sql": """
            SELECT
                width_bucket(LEAST(coverage, 1 - 1e-12), 0.0, 1.0, 20) AS bin_id,
                0.05 * (width_bucket(LEAST(coverage, 1 - 1e-12), 0.0, 1.0, 20) - 1) AS bin_start,
                0.05 *  width_bucket(LEAST(coverage, 1 - 1e-12), 0.0, 1.0, 20)       AS bin_end,
                COUNT(*) AS count
            FROM retromol_compound
            WHERE coverage IS NOT NULL
            GROUP BY bin_id
            ORDER BY {order_col} {order_dir}
        """,
        "allowed_order_cols": {"bin_id", "bin_start", "bin_end", "count"},
        "default_order_col": "bin_start",
        "default_order_dir": "ASC",
        "required": {},
        "optional": {},
    },
    "fingerprint_source_counts": {
        "sql": """
            SELECT cpr.source, COUNT(*) AS count_per_source
            FROM retrofingerprint AS rfp
            JOIN retromol_compound AS rcp ON rfp.retromol_compound_id = rcp.id
            JOIN compound_record AS cpr ON rfp.retromol_compound_id = cpr.compound_id
            WHERE rcp.coverage >= 0.95
            GROUP BY cpr.source
            ORDER BY {order_col} {order_dir}
        """,
        "allowed_order_cols": {"source", "count_per_source"},
        "default_order_col": "count_per_source",
        "default_order_dir": "DESC",
        "required": {},
        "optional": {},
    },
    "search_compound_by_name": {
        "sql": """
            SELECT cpr.name, MIN(cp.smiles) as smiles
            FROM compound as cp
            JOIN compound_record as cpr ON cp.id = cpr.compound_id
            WHERE cpr.name ILIKE %(q)s || '%%'
            GROUP BY cpr.name
            ORDER BY {order_col} {order_dir}
        """,
        "allowed_order_cols": {"name", "smiles"},
        "default_order_col": "name",
        "default_order_dir": "ASC",
        "required": {"q": str},
        "optional": {},
    },
    "cross_modal_retrieval": {
        "sql": """
            SELECT
                rf.id AS identifier,
                CASE
                    WHEN rf.retromol_compound_id IS NOT NULL AND rf.biocracker_genbank_id IS NULL THEN 'compound'
                    WHEN rf.biocracker_genbank_id IS NOT NULL AND rf.retromol_compound_id IS NULL THEN 'gene_cluster'
                    ELSE 'unknown'
                END AS type,
                cr.source AS source,
                cr.ext_id AS ext_id,
                cr.name AS name,
                (1.0 - (rf.fp_retro_b512_vec_binary <=> %(qv)s)) AS score
            FROM retrofingerprint AS rf
            JOIN retromol_compound rmc
            ON rmc.id = rf.retromol_compound_id
            JOIN compound c
            ON c.id = rmc.compound_id
            LEFT join compound_record cr
            ON cr.compound_id = c.id
            WHERE vector_norm(rf.fp_retro_b512_vec_binary) > 0
            AND vector_norm(%(qv)s) > 0
            AND (1.0 - (rf.fp_retro_b512_vec_binary <=> %(qv)s)) >= %(score_threshold)s
            ORDER BY {order_col} {order_dir}
        """,
        "allowed_order_cols": {"identifier", "name", "source", "ext_id", "score"},
        "default_order_col": "score",
        "default_order_dir": "DESC",
        "required": { "fingerprint512": str, "querySettings": dict },
        "optional": {},
        "preprocess_params": preprocess_cross_modal_params,
    },
    "compound_info_by_id": {
        "sql": """
            SELECT
                cr.name,
                c.smiles
            FROM retrofingerprint AS rfp
            JOIN retromol_compound AS rmc
            ON rfp.retromol_compound_id = rmc.id
            JOIN compound AS c
            ON rmc.compound_id = c.id
            JOIN compound_record AS cr
            ON c.id = cr.compound_id
            WHERE rfp.id = %(compound_id)s;
        """,
        "allowed_order_cols": set(),
        "default_order_col": "",
        "default_order_dir": "ASC",
        "required": { "compound_id": int },
        "optional": {},
    },
    "annotation_counts_full": {
        "sql": """
            SELECT
                scheme,
                key,
                value,
                COUNT(*) AS annotation_count,
                COUNT(DISTINCT compound_id) AS n_compounds,
                COUNT(DISTINCT genbank_region_id) AS n_genbank_regions
            FROM annotation
            GROUP BY scheme, key, value
            ORDER BY {order_col} {order_dir}
        """,
        "allowed_order_cols": {"scheme", "key", "value", "annotation_count", "n_compounds", "n_genbank_regions"},
        "default_order_col": "annotation_count",
        "default_order_dir": "DESC",
        "required": {},
        "optional": {},
    },
    "annotation_counts_subset": {
        "sql": """
            SELECT
                scheme,
                key,
                value,
                COUNT(*) AS annotation_count,
                COUNT(DISTINCT compound_id) AS n_compounds,
                COUNT(DISTINCT genbank_region_id) AS n_genbank_regions
            FROM annotation
            WHERE
                (
                    (:compound_ids IS NULL OR compound_id = ANY(:compound_ids))
                    OR
                    (:genbank_region_ids IS NULL OR genbank_region_id = ANY(:genbank_region_ids))
                )
            GROUP BY scheme, key, value
            ORDER BY annotation_count DESC;
        """,
        "allowed_order_cols": {"scheme", "key", "value", "annotation_count", "n_compounds", "n_genbank_regions"},
        "default_order_col": "annotation_count",
        "default_order_dir": "DESC",
        "required": {},
        "optional": {
            "compound_ids": list,
            "genbank_region_ids": list,
        },
    }
}


def coerce_params(spec: dict[str, type], data: dict) -> tuple[dict, str | None]:
    """
    Coerce and validate parameters from the request data according to the spec.

    :param spec: a dictionary mapping parameter names to expected types
    :param data: the input data dictionary
    :return: a tuple containing the coerced parameters dictionary and an error message (or None
    """
    out = {}
    for k, typ in spec.items():
        if k not in data:
            return {}, f"Missing param: {k}"
        v = data[k]
        try:
            if typ is float: out[k] = float(v)
            elif typ is int: out[k] = int(v)
            elif typ is str: out[k] = str(v)
            else: out[k] = v
        except Exception:
            return {}, f"Invalid type for {k}"
    return out, None


def execute_named_query(
    name: str,
    params: dict | None = None,
    paging: dict | None = None,
    order: dict | None = None,
) -> dict:
    """
    Execute a predefined database query with parameters, paging, and ordering.

    :param name: the name of the predefined query
    :param params: a dictionary of query parameters
    :param paging: a dictionary with 'limit' and 'offset' for paging
    :param order: a dictionary with 'column' and 'dir' for ordering
    :return: a dictionary with query results
    :raises ValueError: if there is a parameter validation error
    :raises TimeoutError: if the query times out
    :raises RuntimeError: if there is a database error
    """
    params = params or {}
    paging = paging or {}
    order = order or {}

    if not name or name not in QUERIES:
        raise ValueError("Invalid or missing query name")
    
    qinfo = QUERIES[name]

    # Validate required/optional params
    req_spec = qinfo.get("required", {})
    opt_spec = qinfo.get("optional", {})
    typed, err = coerce_params(req_spec, params)
    if err:
        raise ValueError(err)
    # Optional params (coerce if present)
    for k, typ in opt_spec.items():
        if k in params:
            try:
                if typ is float: typed[k] = float(params[k])
                elif typ is int: typed[k] = int(params[k])
                elif typ is str: typed[k] = str(params[k])
                else: typed[k] = params[k]
            except Exception:
                raise ValueError(f"Invalid type for {k}")
            
    # Preprocess params for specific queries
    preprocess = qinfo.get("preprocess_params")
    if preprocess:
        try:
            typed = preprocess(typed) or typed
        except Exception as e:
            raise ValueError(f"Parameter preprocessing error: {str(e)}")
            
    # Paging
    limit = int(paging.get("limit", DEFAULT_LIMIT))
    offset = int(paging.get("offset", 0))
    offset = max(0, min(MAX_OFFSET, offset))
    typed["limit"] = limit
    typed["offset"] = offset

    # Order-by (whitelisted)
    allowed_cols = qinfo.get("allowed_order_cols", set())
    order_col = (order.get("column") if isinstance(order, dict) else None) or qinfo.get("default_order_col")
    if order_col not in allowed_cols:
        order_col = qinfo.get("default_order_col")
    order_dir = (order.get("dir", qinfo.get("default_order_dir", "ASC")) if isinstance(order, dict) else qinfo.get("default_order_dir", "ASC"))
    order_dir = "DESC" if str(order_dir).upper().startswith("D") else "ASC"

    # Render final SQL safely for the ORDER BY identifier
    base_sql = qinfo["sql"]
    rendered = (
        base_sql.format(
            order_col=sql.Identifier(order_col).as_string(psycopg.connect(dsn_from_env())),
            order_dir=order_dir,
        ).rstrip().rstrip(";")
        + f" LIMIT %(limit)s OFFSET %(offset)s"
    )

    # Exec (read-only, short timeout, public schema)
    dsn = dsn_from_env()
    t0 = time.time()
    try:
        with psycopg.connect(
            dsn,
            options=f"-c statement_timeout={STATEMENT_TIMEOUT_MS} "
                    f"-c idle_in_transaction_session_timeout={STATEMENT_TIMEOUT_MS} "
                    f"-c search_path=public",
        ) as conn:
            register_vector(conn)
            with conn.cursor() as cur:
                cur.execute(rendered, typed)
                rows = cur.fetchall()
                cols = [d.name for d in cur.description]
    except psycopg.errors.QueryCanceled:
        raise TimeoutError(f"Query timeout (>{STATEMENT_TIMEOUT_MS} ms)")
    except Exception as e:
        raise RuntimeError(f"Database error: {str(e)}")
    
    elapsed = int((time.time() - t0) * 1000)
    out_rows = [dict(zip(cols, r)) for r in rows]

    return {
        "name": name,
        "columns": cols,
        "rows": out_rows,
        "rowCount": len(out_rows),
        "limit": limit,
        "offset": offset,
        "elapsed_ms": elapsed,
    }


@blp.post("/api/query")
def run_query():
    """
    Run a predefined database query with parameters, paging, and ordering.

    :return: JSON response with query results or error message
    """
    payload = request.get_json(force=True) or {}
    name = payload.get("name")
    params = payload.get("params", {})
    paging = payload.get("paging", {})
    order = payload.get("order", {})

    try:
        result = execute_named_query(name, params=params, paging=paging, order=order)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except TimeoutError as e:
        return jsonify({"error": str(e)}), 408
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400
    
    return jsonify(result), 200
