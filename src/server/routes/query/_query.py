"""Query endpoint routes."""

import warnings
import uuid
from dataclasses import dataclass

import sqlalchemy as sa
from flask import Blueprint, current_app, jsonify, request
from Bio import BiopythonDeprecationWarning
from rdkit.DataStructs.cDataStructs import ExplicitBitVect

from retromol.model.result import Result
from retromol.model.rules import RuleSet
from retromol.model.reaction_graph import MolNode
from retromol.chem.mol import smiles_to_mol
from retromol.chem.fingerprint import mol_to_morgan_fingerprint, calculate_tanimoto_similarity
from retromol.fingerprint.fingerprint import FingerprintGenerator

from biocracker.query.modules import LinearReadout, PKSModule, NRPSModule, PKSExtenderUnit

from bionexus.db.models import CandidateCluster, Compound, Reference

from versalign.aligner import setup_aligner
from versalign.scoring import create_substitution_matrix_dynamically
from versalign.docking import dock_against_target

from routes.session_store import load_item
from routes.database import SessionLocal
from helpers.ncbi import nuccore_to_gcf

warnings.filterwarnings("ignore", category=BiopythonDeprecationWarning)


blp_query_item = Blueprint("query_item", __name__)


RULESET = RuleSet.load_default()
GENERATOR = FingerprintGenerator(RULESET.matching_rules)


def get_compound_references(s, compound_id: int) -> list[Reference]:
    """
    Return Reference rows linked to a compound via compound_reference.
    """
    stmt = (
        sa.select(Reference)
        .join(Reference.compounds)
        .where(Compound.id == compound_id)
        .order_by(Reference.database_name.asc(), Reference.database_identifier.asc())
    )
    return list(s.scalars(stmt).all())


def get_cluster_references(s, cluster_id: int) -> list[Reference]:
    """
    Return Reference rows linked to a cluster via reference_candidate_cluster.
    """
    stmt = (
        sa.select(Reference)
        .join(Reference.candidate_clusters)
        .where(CandidateCluster.id == cluster_id)
        .order_by(Reference.database_name.asc(), Reference.database_identifier.asc())
    )
    return list(s.scalars(stmt).all())


@dataclass(frozen=True)
class SequenceItem:
    """
    Represents an item in a biosynthetic sequence (e.g., NRPS/PKS module or monomer).
    
    :var name: name of the item
    :var morgan_fp: Morgan fingerprint of the item's structure (if applicable)
    """
    
    name: str
    morgan_fp: ExplicitBitVect | None = None

    def __hash__(self) -> int:
        return hash((self.name, self.morgan_fp.ToBitString() if self.morgan_fp else None))

    @classmethod
    def from_nrps_module(cls, mod: NRPSModule) -> "SequenceItem":
        """
        Create a SequenceItem from an NRPS module.
        """
        if mod.substrate.smiles is not None:
            name = mod.substrate.name
            smiles = mod.substrate.smiles
            if smiles == "O=NN(O)CCC[C@H](N)(C(=O)O":  # graminine fix (fixed in >=2.0.1 versions of BioCracker)
                smiles = "O=NN(O)CCC[C@H](N)(C(=O)O)"
            mol = smiles_to_mol(smiles)
            morgan_fp = mol_to_morgan_fingerprint(mol, radius=2, num_bits=2048, use_chirality=False)
            return cls(name, morgan_fp)
        else:
            return cls("Unknown")

    @classmethod
    def from_pks_module(cls, mod: PKSModule) -> "SequenceItem":
        """
        Create a SequenceItem from a PKS module.
        """
        match mod.substrate.extender_unit:
            case PKSExtenderUnit.PKS_A: name = "PKS_A"
            case PKSExtenderUnit.PKS_B: name = "PKS_B"
            case PKSExtenderUnit.PKS_C: name = "PKS_C"
            case PKSExtenderUnit.PKS_D: name = "PKS_D"
            case _: name = "PKS_A"
        return cls(name)

    @classmethod
    def from_molnode(cls, node: MolNode) -> "SequenceItem":
        """
        Create a SequenceItem from a MolNode.
        """
        if node.is_identified:
            rule = node.identity.matched_rule
            name = rule.name
            mol = smiles_to_mol(rule.smiles)
            morgan_fp = mol_to_morgan_fingerprint(mol, radius=2, num_bits=2048, use_chirality=False)
            return cls(name, morgan_fp)
        else:
            return cls("Unknown")


def item_compare(a: SequenceItem | str, b: SequenceItem | str) -> float:
    """
    Compare two SequenceItems or gap representations.
    """
    if a == "-" or b == "-":
        return 0.0  # gap penalty
    
    elif isinstance(a, SequenceItem) and isinstance(b, SequenceItem):
        pks_a = {'PKS_A', 'A2'}
        pks_b = {'PKS_B', 'B2', 'B6'}
        pks_d = {'PKS_D', 'D6'} 
        pks_mod_names = {"PKS_A", "PKS_B", "PKS_C", "PKS_D", "B2", "D6", "A2", "B6"}
        if a.name in pks_a and b.name in pks_a:
            return 1.0
        elif a.name in pks_b and b.name in pks_b:
            return 1.0
        elif a.name in pks_d and b.name in pks_d:
            return 1.0
        elif a.name in pks_mod_names or b.name in pks_mod_names:
            # Could be correct, but we have no info
            return 0.5

        elif a.name == "Unknown" or b.name == "Unknown":
            # Could be correct, but we have no info
            return 0.5

        elif a.morgan_fp is not None and b.morgan_fp is not None:
            return calculate_tanimoto_similarity(a.morgan_fp, b.morgan_fp)
    
    return -2.0

def label_fn (r: SequenceItem | str) -> str:
    """
    Label function for sequence items.
    """
    return str(hash(r)) if isinstance(r, SequenceItem) else r


@blp_query_item.get("/api/queryItem")
def query_item():
    """
    Query endpoint for compounds by name-like query.
    """
    session_id = request.args.get("sessionId", "").strip()
    item_id = request.args.get("itemId", "").strip()
    if not session_id:
        return jsonify({"error": "Missing sessionId"}), 400
    if not item_id:
        return jsonify({"error": "Missing itemId"}), 400
    
    query_against_compounds = request.args.get("queryAgainstCompounds", "true").lower() == "true"
    query_against_clusters = request.args.get("queryAgainstClusters", "true").lower() == "true"
    # if both set to false, return error
    if not query_against_compounds and not query_against_clusters:
        return jsonify({"error": "At least one of queryAgainstCompounds or queryAgainstClusters must be true"}), 400

    # Retrieve item from session store
    item = load_item(session_id, item_id)
    if item is None:
        return jsonify({"error": "Item not found"}), 404
    
    # Load Result
    payload_as_dict = item.get("payload", None)
    if payload_as_dict is None:
        return jsonify({"error": "No payload found in item"}), 404
    payload: Result = Result.from_dict(payload_as_dict)

    # Create fingerprints for query
    retromol_fp_counted = GENERATOR.fingerprint_from_result(payload, num_bits=1024, counted=True)
    retromol_fp_counted = retromol_fp_counted.astype(float).tolist()
    # retromol_fp_binary = [float(int(x > 0)) for x in retromol_fp_counted]  # currently not used; default is counted fingerprints
    
    # Retrieve primary sequence from payload
    linear_readouts = payload.linear_readout.paths
    linear_readouts.sort(key=lambda x: len(x), reverse=True)
    seq1_blocks: list[list[SequenceItem]] = []
    for readout in linear_readouts:
        seq1_blocks.append([SequenceItem.from_molnode(n) for n in readout])
    # Flatten seq1 for alignment
    seq1: list[SequenceItem] = []
    for block in seq1_blocks:
        seq1.extend(block)


    # NOTE: are we going to retrieve clusters/compounds based on a every block or combined?

    # ANN query against compounds and/or clusters
    keep_top = 1000

    with SessionLocal() as s:
        # Works for pgvector 0.8.0+
        s.execute(sa.text("SET LOCAL hnsw.iterative_scan = strict_order"))
        # increase how far it is allowed to scan
        s.execute(sa.text("SET LOCAL hnsw.max_scan_tuples = 1000000"))
        # optional: allow more memory for scanning
        s.execute(sa.text("SET LOCAL hnsw.scan_mem_multiplier = 2"))
        # increase ef_search for better accuracy
        s.execute(sa.text("SET LOCAL hnsw.ef_search = 1000"))

        if query_against_clusters:
            dist = CandidateCluster.retromol_fp_counted_by_region.cosine_distance(retromol_fp_counted).label("dist")
            stmt = (
                sa.select(CandidateCluster, dist)
                .where(
                    CandidateCluster.retromol_fp_counted_by_region.is_not(None),
                    # CandidateCluster.file_name.ilike("BGC%"),
                    # CandidateCluster.file_name.ilike("BGC0000336"),
                )
                .order_by(dist.asc())
                .limit(keep_top if (query_against_clusters and not query_against_compounds) else keep_top//2)
            )
            cluster_rows = s.execute(stmt).all()
        else:
            cluster_rows = []
        
        if query_against_compounds:
            dist = Compound.retromol_fp_counted.cosine_distance(retromol_fp_counted).label("dist")
            stmt = (
                sa.select(Compound, dist)
                .where(
                    Compound.retromol_fp_counted.is_not(None),
                )
                .order_by(dist.asc())
                .limit(keep_top if (query_against_compounds and not query_against_clusters) else keep_top//2)
            )
            compound_rows = s.execute(stmt).all()
        else:
            compound_rows = []

    # Rerank cluster rows through docking alignment
    best_clusters = []
    for cluster, cosine_dist in cluster_rows:
        rec = LinearReadout.from_dict(cluster.biocracker)

        # Assembly seq2 from rec
        seq2: list[list[SequenceItem]] = []
        by_orf = True
        if not by_orf: subs = [("seq", rec.biosynthetic_order(by_orf=by_orf))]
        else: subs = rec.biosynthetic_order(by_orf=by_orf)
        for _, mods in subs:
            seq2_sub = []
            for mod in mods:
                if isinstance(mod, NRPSModule): seq2_sub.append(SequenceItem.from_nrps_module(mod))
                elif isinstance(mod, PKSModule): seq2_sub.append(SequenceItem.from_pks_module(mod))
                else: raise ValueError(f"unknown module type: {type(mod)}")
            seq2.append(seq2_sub)
        
        if any(len(seq2_sub) for seq2_sub in seq2):
            # Dynamically create scoring matrix
            items = ["-"]
            items.extend(seq1)
            for seq2_sub in seq2:
                items.extend(seq2_sub)
            unique_items = list(set(items))
            sm, _ = create_substitution_matrix_dynamically(unique_items, compare=item_compare, label_fn=label_fn)
            aligner = setup_aligner(
                sm,
                "global",
                target_internal_open_gap_score=-5.0,
                target_left_open_gap_score=-2.5,
                target_right_open_gap_score=-2.5,
                query_internal_open_gap_score=-5.0,
                query_left_open_gap_score=-2.5,
                query_right_open_gap_score=-2.5,
                label_fn=label_fn,
            )
            aln = dock_against_target(
                aligner=aligner,
                target=seq1,
                candidates=seq2,
                gap_repr="-",
                allow_block_reverse=True,
                strategy="nonoverlap",
            )
            alignment_score = aln.total_score  # the higher the score the bigger and stronge the match between the two; favors long matches

            # Penalize unmatched parts; if we are using shorter blocks
            # TODO

            if len(best_clusters) < keep_top or alignment_score > best_clusters[-1][0]:
                best_clusters.append((alignment_score, 1.0 - cosine_dist, cluster, aln, seq2))
                best_clusters.sort(key=lambda x: x[0], reverse=True)
                if len(best_clusters) > keep_top:
                    best_clusters.pop()

    # Rerank compound rows through docking alignment
    best_compounds = []
    for compound, cosine_dist in compound_rows:
        rec = Result.from_dict(compound.retromol)

        # Assembly seq2 from rec
        # Retrieve primary sequence from payload
        compound_readouts = rec.linear_readout.paths
        compound_readouts.sort(key=lambda x: len(x), reverse=True)
        seq2_blocks: list[list[SequenceItem]] = []
        for readout in compound_readouts:
            seq2_blocks.append([SequenceItem.from_molnode(n) for n in readout])

        if any(len(seq2_sub) for seq2_sub in seq2_blocks):
            # Dynamically create scoring matrix
            items = ["-"]
            items.extend(seq1)
            for seq2_sub in seq2_blocks:
                items.extend(seq2_sub)
            unique_items = list(set(items))
            sm, _ = create_substitution_matrix_dynamically(unique_items, compare=item_compare, label_fn=label_fn)
            aligner = setup_aligner(
                sm,
                "global",
                target_internal_open_gap_score=-5.0,
                target_left_open_gap_score=-2.5,
                target_right_open_gap_score=-2.5,
                query_internal_open_gap_score=-5.0,
                query_left_open_gap_score=-2.5,
                query_right_open_gap_score=-2.5,
                label_fn=label_fn,
            )
            aln = dock_against_target(
                aligner=aligner,
                target=seq1,
                candidates=seq2_blocks,
                gap_repr="-",
                allow_block_reverse=True,
                strategy="nonoverlap",
            )
            alignment_score = aln.total_score  # the higher the score the bigger and stronge the match between the two; favors long matches

            # Penalize unmatched parts; if we are using shorter blocks
            # TODO

            if len(best_compounds) < keep_top or alignment_score > best_compounds[-1][0]:
                best_compounds.append((alignment_score, 1.0 - cosine_dist, compound, aln, seq2_blocks))
                best_compounds.sort(key=lambda x: x[0], reverse=True)
                if len(best_compounds) > keep_top:
                    best_compounds.pop()
    

    # Sort first on alignment score, then on cosine score
    best_clusters.sort(key=lambda x: (x[0], x[1]), reverse=True)
    best_compounds.sort(key=lambda x: (x[0], x[1]), reverse=True)

    # combine lists and resort, add little tag to indicate source
    combined = []
    for alignment_score, cosine_score, cluster, aln, blocks in best_clusters:
        combined.append((alignment_score, cosine_score, cluster, aln, blocks, "cluster"))
    for alignment_score, cosine_score, compound, aln, blocks in best_compounds:
        combined.append((alignment_score, cosine_score, compound, aln, blocks, "compound"))
    combined.sort(key=lambda x: (x[0], x[1]), reverse=True)

    # Format response
    msa: list[list[dict]] = []

    # print(linear_readout)  # MolNodes
    msa_item = {
        "id": str(uuid.uuid4()),
        "name": "Query",
        "alignment_score": None,
        "cosine_score": None,
        "sequence": [],
        "references": [],
    }
    # for x in linear_readout:
    #     subseq.append({
    #         "id": str(uuid.uuid4()),
    #         "isGap": False,
    #         "name": x.identity.matched_rule.name if x.is_identified else None,
    #         "smiles": x.identity.matched_rule.smiles if x.is_identified else None,
    #     })
    for i, block in enumerate(seq1_blocks):
        subseq = []
        for x in block:
            subseq.append({
                "id": str(uuid.uuid4()),
                "isGap": False,
                "name": x.name,
                "smiles": None,
            })
        msa_item["sequence"].append({
            "id": str(uuid.uuid4()),
            "name": f"primary sequence {i + 1}",
            "sequence": subseq,
        })
    msa.append(msa_item)

    # NOTE: if nothing from seq2 block alignst to a block original alignemtn(target) the sequence should remain emptty, not full of gaps

    for i, (alignment_score, cosine_score, cluster, aln, blocks, source) in enumerate(combined[:20], 1):

        msa_item = None

        if source == "compound":

            # get compound references
            with SessionLocal() as s:
                refs = get_compound_references(s, cluster.id)

            if refs:
                name = refs[0].name
            else:
                name = "Unnamed compound"

            msa_item = {
                "id": str(uuid.uuid4()),
                "name": name,
                "alignment_score": round(alignment_score, 3),
                "cosine_score": round(cosine_score, 3),
                "sequence": [],
                "references": [{
                    "name": ref.name,
                    "database_name": ref.database_name,
                    "database_identifier": ref.database_identifier,
                } for ref in refs],
            }

            for i, block in enumerate(seq1_blocks):
                msa_item["sequence"].append({
                    "id": str(uuid.uuid4()),
                    "name": f"primary sequence {i + 1}",
                    "sequence": [
                        {
                            "id": str(uuid.uuid4()),
                            "isGap": True,
                            "name": None,
                            "smiles": None,
                        }
                        for _ in range(len(block))
                    ],
                })

        
        if source == "cluster":

            # get cluster references
            with SessionLocal() as s:
                refs = get_cluster_references(s, cluster.id)

            msa_item = {
                "id": str(uuid.uuid4()),
                "name": cluster.file_name,
                "alignment_score": round(alignment_score, 3),
                "cosine_score": round(cosine_score, 3),
                "sequence": [],
                "references": [{
                    "name": ref.name,
                    "database_name": ref.database_name,
                    "database_identifier": ref.database_identifier,
                } for ref in refs],
            }

            for i, block in enumerate(seq1_blocks):
                msa_item["sequence"].append({
                    "id": str(uuid.uuid4()),
                    "name": f"gene {i + 1}",
                    "sequence": [
                        {
                            "id": str(uuid.uuid4()),
                            "isGap": True,
                            "name": None,
                            "smiles": None,
                        }
                        for _ in range(len(block))
                    ],
                })
        
        if msa_item:
            try:
                # sort placements by start position
                print(aln)
                placements = sorted(aln.placements, key=lambda p: p.start)
                for placement in placements:

                    is_reversed = placement.reversed

                    # get real identities instead of hashes of aligned blocks
                    block_idx = placement.block_idx  # THIS IS THE INDEX OF THE BLOCK IN THE CANDIDATE SEQUENCE
                    block = blocks[block_idx]
                    if is_reversed:
                        block = list(reversed(block))
                    # gap_inds = [i for i, x in enumerate(placement.block_aln) if x == "-"]
                    # print(len(placement.block_aln), len(block), gap_inds)

                    print("block_idx", block_idx)

                    placement_items = {}
                    placement_count = 0
                    for x in placement.block_aln:
                        if x == "-":
                            continue
                        placement_items[placement_count] = block[placement_count]
                        placement_count += 1
                    print("placement count", placement_count)

                    # NOTE: GAPS COULD BE INTRODUCED IN BOTH QUERY AND TARGET!!!!! DURING ALIGNMENT
                    # NOTE: WHY ARENT THE SUGARS MATCHING/ALIGNING WITH ERYTHROMYCIN
                    # NOTE: APPEND UNMATCHED PARTS TO THE END OF THE ALIGNMENT AS EXTRA BLOCKS, NEED TO CHECK PADDING AFTERWARDS

                    start = placement.start
                    end = placement.end
                    print("start-end", start, end)
                    it = 0
                    for idx in range(start, end + 1):
                        name = placement_items[it].name
                        if name.startswith("PKS_"):
                            name = name.strip("PKS_")
                        offset = start
                        msa_item["sequence"][0]["sequence"][idx] = {
                            "id": str(uuid.uuid4()),
                            "isGap": False,
                            # "name": None, # could be filled in if needed
                            "name": name,
                            "smiles": None,  # could be filled in if needed
                        }
                        it += 1

                for block_idx in aln.unused_blocks:
                    unused_block = blocks[block_idx]
                    msa_item["sequence"].append({
                        "id": str(uuid.uuid4()),
                        "name": f"additional sequence {block_idx + 1}",
                        "sequence": [],
                    })
                    for x in unused_block:
                        msa_item["sequence"][-1]["sequence"].append({
                            "id": str(uuid.uuid4()),
                            "isGap": False,
                            "name": x.name,
                            "smiles": None,
                        })
                
            except Exception as e:
                pass

            msa.append(msa_item)

    # For now just return error
    # return jsonify({"msa": msa}), 200
    return jsonify({"msa": msa}), 200

