"""Module defining sequence item data structures for query results."""

from dataclasses import dataclass, field
from typing import Literal

from rdkit.DataStructs.cDataStructs import ExplicitBitVect

from retromol.model.reaction_graph import MolNode
from retromol.chem.mol import smiles_to_mol
from retromol.chem.fingerprint import mol_to_morgan_fingerprint

from biocracker.query.modules import (
    Module,
    PKSModule,
    NRPSModule,
    PKSSubstrate,
    PKSExtenderUnit,
    NRPSSubstrate,
)

DEFAULT_GAP_REPR = "-"
DEFAULT_MASK_REPR = "X"

MORGAN_RADIUS = 2
MORGAN_SIZE = 2048

DISPLAY_NAME_UNIDENTIFIED = "unknown"
DISPLAY_NAME_MASK = "masked"


@dataclass(frozen=True)
class SequenceItem:
    """
    Base class for sequence items in query results.
    """

    ...


@dataclass(frozen=True)
class Mask(SequenceItem):
    """
    Mask sequence item representing a masked or unknown module.
    """

    display_name: str = DEFAULT_MASK_REPR

    def __str__(self) -> str:
        """
        String representation of the SequenceItem.

        :return: string representation
        """
        return self.display_name
    
    def __hash__(self) -> int:
        """
        Hash function for SequenceItem.

        :return: hash value
        """
        return hash(self.display_name)
    
    @classmethod
    def alignment_representation(cls) -> str:
        """
        Representation used in alignments.

        :return: alignment representation string
        """
        return str(hash(cls(DEFAULT_MASK_REPR)))


@dataclass(frozen=True)
class Gap(SequenceItem):
    """
    Gap sequence item representing an unknown or missing module.
    """

    display_name: str = DEFAULT_GAP_REPR

    def __str__(self) -> str:
        """
        String representation of the SequenceItem.

        :return: string representation
        """
        return self.display_name
    
    def __hash__(self) -> int:
        """
        Hash function for SequenceItem.

        :return: hash value
        """
        return hash(self.display_name)
    
    @classmethod
    def alignment_representation(cls) -> str:
        """
        Representation used in alignments.

        :return: alignment representation string
        """
        return str(hash(cls(DEFAULT_GAP_REPR)))


@dataclass(frozen=True)
class NonGap(SequenceItem):
    """
    Non-gap sequence item representing a module or identified molecule.

    :var display_name: Name to display for the item.
    :var morgan_fp: Morgan fingerprint of the molecule.
    """

    display_name: str
    morgan_fp: ExplicitBitVect | None = None
    family_tokens: list[str] | None = field(default_factory=list)
    ancestor_tokens: list[str] | None = field(default_factory=list)

    def __hash__(self) -> int:
        """
        Hash based on display name and Morgan fingerprint.

        :return: hash value
        """
        return hash((
            self.display_name,
            self.morgan_fp.ToBitString() if self.morgan_fp else None,
            "|".join(self.family_tokens) if self.family_tokens else None,
            "|".join(self.ancestor_tokens) if self.ancestor_tokens else None,
        ))

    @classmethod
    def from_retromol_molnode(cls, n: MolNode) -> "SequenceItem":
        """
        Create a SequenceItem from a RetroMol MolNode.

        :param n: RetroMol MolNode
        :return: SequenceItem
        """
        assert isinstance(n, MolNode), f"expected RetroMol MolNode, got {type(molnode)}"
        
        if n.is_identified:
            matched_rule = n.identity.matched_rule
            display_name = matched_rule.name
            mol = smiles_to_mol(matched_rule.smiles)
            morgan_fp = mol_to_morgan_fingerprint(mol, radius=MORGAN_RADIUS, num_bits=MORGAN_SIZE)
            family_tokens = list(matched_rule.family_tokens)
            ancestor_tokens = list(matched_rule.ancestor_tokens)

            return cls(
                display_name=display_name,
                morgan_fp=morgan_fp,
                family_tokens=family_tokens,
                ancestor_tokens=ancestor_tokens,
            )
        else:
            display_name = DISPLAY_NAME_UNIDENTIFIED
            mol = smiles_to_mol(n.smiles)
            morgan_fp = mol_to_morgan_fingerprint(mol, radius=MORGAN_RADIUS, num_bits=MORGAN_SIZE)
            
            return cls(display_name=display_name, morgan_fp=morgan_fp)

    @classmethod
    def from_biocracker_module(cls, m: Module) -> "SequenceItem":
        """
        Create a SequenceItem from a BioCracker module.

        :param m: BioCracker Module
        :return: SequenceItem
        """
        assert isinstance(m, Module), f"expected BioCracker Module, got {type(module)}"
        
        match m:
            case PKSModule(substrate=PKSSubstrate(extender_unit=PKSExtenderUnit.PKS_A)):
                return cls(display_name="A", ancestor_tokens=["PKS", "A"])
            case PKSModule(substrate=PKSSubstrate(extender_unit=PKSExtenderUnit.PKS_B)):
                return cls(display_name="B", ancestor_tokens=["PKS", "B"])
            case PKSModule(substrate=PKSSubstrate(extender_unit=PKSExtenderUnit.PKS_C)):
                return cls(display_name="C", ancestor_tokens=["PKS", "C"])
            case PKSModule(substrate=PKSSubstrate(extender_unit=PKSExtenderUnit.PKS_D)):
                return cls(display_name="D", ancestor_tokens=["PKS", "D"])
            case PKSModule(substrate=PKSSubstrate(extender_unit=PKSExtenderUnit.UNCLASSIFIED)):
                return cls(display_name="A", ancestor_tokens=["PKS", "A"])
            case NRPSModule(substrate=NRPSSubstrate(smiles=None)):
                return cls(display_name=DISPLAY_NAME_UNIDENTIFIED, ancestor_tokens=["NRPS"])
            case NRPSModule(substrate=NRPSSubstrate(name=name, smiles=smiles)):
                display_name = name if name is not None else DISPLAY_NAME_UNIDENTIFIED

                # Graminine SMILES fix (fixed in >=2.0.1 versions of BioCracker)
                if smiles == "O=NN(O)CCC[C@H](N)(C(=O)O": 
                    smiles = "O=NN(O)CCC[C@H](N)C(=O)O"

                mol = smiles_to_mol(smiles)
                morgan_fp = mol_to_morgan_fingerprint(mol, radius=MORGAN_RADIUS, num_bits=MORGAN_SIZE)
                return cls(display_name=display_name, morgan_fp=morgan_fp, ancestor_tokens=["NRPS"])
            case NRPSModule(substrate=None):
                return cls(display_name=DISPLAY_NAME_UNIDENTIFIED, ancestor_tokens=["NRPS"])
            case _:
                raise NotImplementedError(f"BioCracker module type {type(m)} not supported yet")
    
    @classmethod
    def from_biocracker_modifier(cls, modifier: str) -> "SequenceItem":
        """
        Create a SequenceItem from a BioCracker modifier.

        :param modifier: BioCracker modifier string
        :return: SequenceItem
        """
        return cls(display_name=modifier, family_tokens=[modifier])


@dataclass(frozen=True)
class SequenceItemReadout:
    """
    Readout of sequence items in query results.

    :var kind: either "compound" or "cluster"
    :var block_ids: list of block identifiers for display purposes
    :var blocks: list of blocks, where each block is a list of SequenceItems
    :var db_id: database identifier, if applicable
    """

    kind: Literal["compound", "cluster"]
    block_ids: list[str]  # only for display purposes
    blocks: list[list[SequenceItem]]

    db_id: int | None

    def flatten_items(self) -> list[SequenceItem]:
        """
        Flatten the blocks into a single list of SequenceItems.

        :return: flattened list of SequenceItems
        """
        blocks = self.blocks
        if self.kind == "compound":
            # Only for compounds: sort blocks on size; longer blocks first
            blocks = sorted(blocks, key=lambda b: len(b), reverse=True)

        return [item for block in blocks for item in block]