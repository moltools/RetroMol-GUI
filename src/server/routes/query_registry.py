"""Module defining the available SQL queries for the query registry."""


from pgvector import Vector

from routes.helpers import hex_to_bits


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
        "allowed_order_cols": {
            "scheme", "key", "value",
            "annotation_count", "n_compounds", "n_genbank_regions"
        },
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
                compound_id = ANY(%(compound_ids)s::bigint[])
                OR genbank_region_id = ANY(%(genbank_region_ids)s::bigint[])
            GROUP BY scheme, key, value
            ORDER BY {order_col} {order_dir}
        """,
        "allowed_order_cols": {
            "scheme", "key", "value",
            "annotation_count", "n_compounds", "n_genbank_regions"
        },
        "default_order_col": "annotation_count",
        "default_order_dir": "DESC",
        "required": {
            "compound_ids": list,
            "genbank_region_ids": list,
        },
        "optional": {},
    },
    "retrieve_items_by_fingerprint_ids": {
        "sql": """
            SELECT DISTINCT
                rmc.compound_id,
                bkg.genbank_region_id
            FROM retrofingerprint AS rf
            LEFT JOIN retromol_compound AS rmc
                ON rf.retromol_compound_id = rmc.id
            LEFT JOIN biocracker_genbank AS bkg
                ON rf.biocracker_genbank_id = bkg.id
            WHERE rf.id = ANY(%(rf_ids)s::bigint[]);
        """,
        "allowed_order_cols": set(),
        "default_order_col": "",
        "default_order_dir": "ASC",
        "required": { "rf_ids": list },
        "optional": {},
    },
    "target_counts": {
        "sql": """
            SELECT
                (SELECT COUNT(*) FROM compound) AS n_compounds,
                (SELECT COUNT(*) FROM genbank_region) AS n_genbank_regions
        """,
        "allowed_order_cols": set(),
        "default_order_col": "",
        "default_order_dir": "ASC",
        "required": {},
        "optional": {},
    },
}