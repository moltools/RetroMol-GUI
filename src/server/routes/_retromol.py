"""Custom implementation for RetroMol linear backbone readouts."""

from typing import Any

from networkx import connected_components
from retromol.io import Result
from retromol.readout import (
    _graphs_with_metadata,
    _is_path_component,
    _longest_path_approx,
    _monomer_nodes_at_level,
    _order_nodes_along_path,
    _payload_from_order,
)


def retromol_linear_readout(
    result: Result,
    require_identified: bool = True,
    mode: str = "all",  # "all" | "best_per_level" | "global_best"
    nesting_depth: int | None = None,
) -> dict[str, Any]:
    """
    Linear backbone readouts.

    :param result: RetroMol Result object
    :param require_identified: if ``True``, only consider monomer nodes with an
        assigned identity. If ``False``, consider all monomer nodes
    :param nesting_depth: maximum nesting level to analyze. If ``None``, all depths are included
        - when ``nesting_depth`` is ``None``: iterate all graphs in DFS order and return
        a structure identical to the previous version (keys and shapes), but each
        entry now also includes a ``depth`` field for clarity.
        - set ``nesting_depth = k`` to restrict analysis to graphs at that **true**
        nesting level (root = 0, its children = 1, etc.).
    :param mode: determines the aggregation mode of readouts
        Supported values:
        - ``"all"``: return all depth levels and paths.

    :returns:
        Depending on the selected ``mode``:

        **mode = "all"**
            Returns:
            ``{"levels": [
                {"dfs_index": int, "depth": int,
                "strict_paths": [payload, ...],
                "fallback": payload_or_None},
                ...
            ]}``
    """
    metas = _graphs_with_metadata(result.graph)
    if nesting_depth is not None:
        metas = [m for m in metas if m["depth"] == nesting_depth]
        if not metas:
            msg = f"No graphs at nesting_depth={nesting_depth}."
            if mode == "global_best":
                return {
                    "dfs_index": -1,
                    "depth": nesting_depth,
                    "strict_path": False,
                    "backbone": {"n_monomers": 0, "ordered_monomers": []},
                    "notes": msg,
                }
            else:
                return {"levels": [], "notes": msg}

    # Per-graph analysis
    entries: list[dict[str, Any]] = []
    for m in metas:
        G = m["graph"]
        dfs_idx = m["dfs_index"]
        depth = m["depth"]

        parent_smiles_tagged = G.graph["smiles"]

        monomer_nodes = _monomer_nodes_at_level(G, require_identified)
        if not monomer_nodes:
            entries.append(
                {
                    "dfs_index": dfs_idx,
                    "depth": depth,
                    "strict_paths": [],
                    "fallback": None,
                }
            )
            continue

        MG = G.subgraph(monomer_nodes).copy()
        comps = list(connected_components(MG))

        strict_payloads: list[dict[str, Any]] = []
        for comp in comps:
            nodes = list(comp)
            if _is_path_component(MG, nodes):
                order = _order_nodes_along_path(MG, nodes)
                strict_payloads.append(_payload_from_order(G, order))

        fallback_payload = None
        if not strict_payloads and comps:
            largest = max(comps, key=len)
            approx_order = _longest_path_approx(MG, list(largest))
            fallback_payload = _payload_from_order(G, approx_order)

        entries.append(
            {
                "parent_smiles_tagged": parent_smiles_tagged,
                "dfs_index": dfs_idx,
                "depth": depth,
                "strict_paths": strict_payloads,
                "fallback": fallback_payload,
            }
        )

    entries.sort(key=lambda e: e["dfs_index"])
    return {"levels": entries}