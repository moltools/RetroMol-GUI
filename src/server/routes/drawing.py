"""Endpoint to draw compounds or clusters as SVG."""

from enum import Enum

from flask import Blueprint, current_app, jsonify, request

from rdkit.Chem.rdchem import Mol
from rdkit.Chem.Draw.rdMolDraw2D import MolDraw2DSVG, MolDrawOptions

from retromol.chem.tagging import get_tags_mol

from routes.session_store import load_item
from routes.query.featurize import load_payload


blp_draw_item = Blueprint("draw_item", __name__)


class Palette(Enum):
    Red = (230, 25, 75)
    Blue = (0, 130, 200)
    Green = (60, 180, 75)
    Maroon = (128, 0, 0)
    Brown = (170, 110, 40)
    Olive = (128, 128, 0)
    Teal = (0, 128, 128)
    Navy = (0, 0, 128)
    Orange = (245, 130, 48)
    Yellow = (255, 225, 25)
    Lime = (210, 245, 60)
    Cyan = (70, 240, 240)
    Purple = (145, 30, 180)
    Magenta = (240, 50, 230)
    Pink = (255, 190, 212)
    Apricot = (255, 215, 180)
    Beige = (255, 250, 200)
    Mint = (170, 255, 195)
    Lavender = (220, 190, 255)

    def hex(self, alpha: float) -> str:
        """
        Get hex representation of the color with specified alpha transparency.
        
        :param alpha: alpha transparency (0.0 to 1.0)
        :return: hex color string with alpha
        """
        return f"#{self.value[0]:02x}{self.value[1]:02x}{self.value[2]:02x}{int(alpha * 255):02x}"

    def normalize(self, min_val: float = 0.0, max_val: float = 255.0) -> tuple[float, float, float]:
        """
        Get normalized RGB tuple of the color.
        
        :param min_val: minimum value for normalization
        :param max_val: maximum value for normalization
        :return: normalized RGB tuple
        """
        r, g, b = self.value
        return (
            (r - min_val) / (max_val - min_val),
            (g - min_val) / (max_val - min_val),
            (b - min_val) / (max_val - min_val),
        )
    

def hex_to_rgb_tuple(hex_str: str) -> tuple[float, float, float]:
    """
    Convert hex color string to normalized RGB tuple.
    
    :param hex_str: hex color string (e.g. "#ff5733" or "#ff5733ff")
    :return: normalized RGB tuple
    """
    hex_str = hex_str.lstrip("#")
    if len(hex_str) == 6:
        r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
    elif len(hex_str) == 8:
        r, g, b = int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16)
        # alpha = int(hex_str[6:8], 16)  # Alpha is ignored in this function
    else:
        raise ValueError(f"Invalid hex color string: {hex_str}")
    return (r / 255.0, g / 255.0, b / 255.0)


def draw_compound(
    mol: Mol,
    sub_mols: list[Mol] = [],
    window_size: tuple[int, int] = (300, 300),
    background_color: str | None = None,
):
    """
    Draw the compound as an SVG image.

    :param mol: RDKit molecule object to draw
    :param window_size: size of the drawing window (width, height)
    :return: SVG string of the drawn molecule
    """
    drawing: MolDraw2DSVG = MolDraw2DSVG(*window_size)
    palette = [c.normalize() for c in Palette]

    atoms_to_highlight: list[int] = []
    bonds_to_highlight: list[int] = []
    atom_highlight_colors: dict[int, tuple[float, float, float]] = {}
    bond_highlight_colors: dict[int, tuple[float, float, float]] = {}

    for sub_mol_idx, sub_mol in enumerate(sub_mols):
        color = palette[sub_mol_idx % len(palette)]
        sub_tags = get_tags_mol(sub_mol)

        for atom in mol.GetAtoms():
            a_tag = atom.GetIsotope()
            if a_tag in sub_tags:
                a_idx = atom.GetIdx()
                atoms_to_highlight.append(a_idx)
                atom_highlight_colors[a_idx] = color

        for bond in mol.GetBonds():
            b_begin_idx = bond.GetBeginAtom()
            b_end_idx = bond.GetEndAtom()
            b_begin_tag = b_begin_idx.GetIsotope()
            b_end_tag = b_end_idx.GetIsotope()
            if b_begin_tag in sub_tags and b_end_tag in sub_tags:
                b_idx = bond.GetIdx()
                bonds_to_highlight.append(b_idx)
                bond_highlight_colors[b_idx] = color

    options: MolDrawOptions = drawing.drawOptions()
    options.bondLineWidth = 1.2
    options.multipleBondOffset = 0.18
    options.fixedBondLength = 25
    options.minFontSize = 10
    options.maxFontSize = 16
    options.annotationFontScale = 0.9
    options.highlightBondWidthMultiplier = 20
    options.padding = 0.05

    if background_color is not None:
        options.setBackgroundColour(hex_to_rgb_tuple(background_color))
    options.useBWAtomPalette()

    options.atomLabelDeuteriumTritium = False
    options.drawMolsSameScale = True
    options.explicitMethyl = False
    options.addAtomIndices = False

    # Remove isotopic labels for drawing
    cp_mol = Mol(mol)
    for atom in cp_mol.GetAtoms():
        atom.SetIsotope(0)

    drawing.DrawMolecule(
        cp_mol,
        highlightAtoms=atoms_to_highlight,
        highlightBonds=bonds_to_highlight,
        highlightAtomColors=atom_highlight_colors,
        highlightBondColors=bond_highlight_colors,
    )

    drawing.FinishDrawing()
    svg_str = drawing.GetDrawingText().replace("svg:", "")

    return svg_str


@blp_draw_item.get("/api/drawItem")
def draw_item():
    """
    Endpoint to draw a query item (compound or cluster) as SVG.
    """
    session_id = (request.args.get("sessionId") or "").strip()
    item_id = (request.args.get("itemId") or "").strip()

    if not session_id or not item_id:
        return jsonify({"ok": False, "error": "Missing sessionId or itemId"}), 400
    
    # Retrieve item from session store
    current_app.logger.info(f"Retrieving query item: session_id={session_id} item_id={item_id}")
    item = load_item(session_id, item_id)
    if item is None:
        return jsonify({"ok": False, "error": "Item not found"}), 404
    current_app.logger.info(f"Loaded item for querying: session_id={session_id} item_id={item_id} kind={item.get('kind')}")

    payload_type = item.get("kind", None)
    payload_blob = item.get("payload", None)
    if not payload_type or payload_type not in ["cluster", "compound"]:
        current_app.logger.error(f"Invalid item kind for querying: {payload_type}")
        return jsonify({"ok": False, "error": "Invalid item kind"}), 400
    if not payload_blob:
        current_app.logger.error("Missing item payload for querying")
        return jsonify({"ok": False, "error": "Missing item payload"}), 400

    if payload_type == "compound":
        payload = load_payload(payload_type, payload_blob)
        root_mol = payload.submission.mol
        leaf_nodes = payload.reaction_graph.get_leaf_nodes(identified_only=True)
        leaf_mols = [node.mol for node in leaf_nodes if node.mol is not None]
        svg = draw_compound(root_mol, leaf_mols, background_color="#ffffff")
        return jsonify({"ok": True, "svg": svg}), 200
    else:
        return jsonify({"ok": False, "error": "Drawing is only supported for compounds"}), 400
