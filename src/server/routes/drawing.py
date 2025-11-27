"""Module for handling drawing-related routes."""

import re
from copy import deepcopy
from enum import Enum
from dataclasses import dataclass

from flask import Blueprint, request, jsonify
from rdkit.Chem.Draw.rdMolDraw2D import DrawMoleculeACS1996, MolDraw2DSVG, MolDrawOptions
from retromol.chem import smiles_to_mol


blp_draw_compound_item = Blueprint("draw_compound_item", __name__)


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


@dataclass
class Highlight:
    """
    Class representing a highlight for drawing.
    
    :param tags: set of integer tags to highlight
    :param color: RGBA color tuple for the highlight
    """

    display_name: str
    tags: set[int]
    color: tuple[float, float, float]


def rgba_to_hex_opacity(rgba: tuple[float, float, float]) -> str:
    """
    Convert RGBA tuple to hex color string and opacity.
    
    :param rgba: RGBA color tuple
    :return: tuple of hex color string and opacity
    """
    r, g, b = rgba
    r_i = int(r * 255)
    g_i = int(g * 255)
    b_i = int(b * 255)
    return f"#{r_i:02x}{g_i:02x}{b_i:02x}"


def add_motif_legend_to_svg(
    svg_str: str,
    highlights: list[Highlight],
    legend_height: float = 40.0,
) -> str:
    """
    Extend RDKit SVG with a legend row of motif boxes under the molecule.
    Boxes have a fixed width that fits 3 characters.
    """
    if not highlights:
        return svg_str

    # Parse current width/height from <svg ...> tag
    width_match = re.search(r"width=(['\"])([\d.]+)(?:px)?\1", svg_str)
    height_match = re.search(r"height=(['\"])([\d.]+)(?:px)?\1", svg_str)
    if not width_match or not height_match:
        return svg_str  # bail out safely

    width_quote = width_match.group(1)
    width = float(width_match.group(2))
    old_height = float(height_match.group(2))
    new_height = old_height + legend_height

    # --- layout params for legend boxes ---
    BOX_WIDTH = 48.0    # width per motif box (enough for 3 chars)
    PADDING_X = 8.0     # padding at left and right of legend row

    n = len(highlights)
    if n == 0:
        return svg_str

    needed_width = BOX_WIDTH * n + 2 * PADDING_X

    # Decide final SVG width for layout of legend
    if needed_width <= width:
        svg_width_final = width
        # no width change, just center boxes
    else:
        svg_width_final = needed_width
        # widen the SVG, preserve quote style
        svg_str = re.sub(
            r"width=(['\"])([\d.]+)(?:px)?\1",
            f"width={width_quote}{svg_width_final}px{width_quote}",
            svg_str,
            count=1,
        )

    # Update height attribute, preserving quote style
    height_quote = height_match.group(1)
    svg_str = re.sub(
        r"height=(['\"])([\d.]+)(?:px)?\1",
        f"height={height_quote}{new_height}px{height_quote}",
        svg_str,
        count=1,
    )

    # Update viewBox='0 0 W H' (single or double quotes)
    vb_match = re.search(r"viewBox=(['\"])0 0 ([\d.]+) ([\d.]+)\1", svg_str)
    if vb_match:
        vb_quote = vb_match.group(1)
        vb_w = float(vb_match.group(2))
        vb_h = float(vb_match.group(3))
        new_vb_w = max(vb_w, needed_width)
        new_vb_h = vb_h + legend_height
        # NOTE: we keep vb_w as-is so the molecule isn’t rescaled horizontally
        svg_str = re.sub(
            r"viewBox=(['\"])0 0 ([\d.]+) ([\d.]+)\1",
            f"viewBox={vb_quote}0 0 {new_vb_w} {new_vb_h}{vb_quote}",
            svg_str,
            count=1,
        )

    # Layout: fixed-width boxes, centered as a block
    legend_y = old_height  # start right below the original drawing
    legend_elems: list[str] = []

    # center the set of boxes within svg_width_final
    start_x = (svg_width_final - needed_width) / 2.0 + PADDING_X

    for i, h in enumerate(highlights):
        box_x = start_x + i * BOX_WIDTH
        box_y = legend_y

        fill_hex = rgba_to_hex_opacity(h.color)

        rect = (
            f'<rect x="{box_x:.2f}" y="{box_y:.2f}" '
            f'width="{BOX_WIDTH:.2f}" height="{legend_height:.2f}" '
            f'fill="{fill_hex}" />'
        )

        text_x = box_x + BOX_WIDTH / 2.0
        text_y = box_y + legend_height / 2.0

        text = (
            f'<text x="{text_x:.2f}" y="{text_y:.2f}" '
            f'text-anchor="middle" dominant-baseline="middle" '
            f'font-size="14" fill="black">{h.display_name}</text>'
        )

        legend_elems.append(rect)
        legend_elems.append(text)

    legend_group = '<g id="motif-legend">' + "".join(legend_elems) + "</g>"

    # Inject legend just before the closing </svg>
    svg_str = svg_str.replace("</svg>", legend_group + "</svg>")

    return svg_str


def draw_highlights(
    tagged_parent_smiles: str,
    highlights: list[Highlight],
    background_color: str | None = None,
) -> None:
    """
    Draw highlights on a molecule given its tagged SMILES representation.

    :param tagged_parent_smiles: SMILES string of the tagged parent molecule
    :param highlights: list of Highlight objects specifying tags and alpha values
    :param background_color: optional background color in hex format
    :return: SVG string of the drawn molecule with highlights
    """
    tagged_parent = smiles_to_mol(tagged_parent_smiles)
    drawing: MolDraw2DSVG = MolDraw2DSVG(-1, -1)

    atoms_to_highlight: list[int] = []
    bonds_to_highlight: list[int] = []
    atom_highlight_colors: dict[int, tuple[float, float, float]] = {}
    bond_highlight_colors: dict[int, tuple[float, float, float]] = {}

    for highlight in highlights:
        color = highlight.color
        n_tags = highlight.tags

        for atom in tagged_parent.GetAtoms():
            a_tag = atom.GetIsotope()
            if a_tag in n_tags:
                a_idx = atom.GetIdx()
                atoms_to_highlight.append(a_idx)
                atom_highlight_colors[a_idx] = color

        for bond in tagged_parent.GetBonds():
            b_begin_idx = bond.GetBeginAtom()
            b_end_idx = bond.GetEndAtom()
            b_begin_tag = b_begin_idx.GetIsotope()
            b_end_tag = b_end_idx.GetIsotope()
            if b_begin_tag in n_tags and b_end_tag in n_tags:
                b_idx = bond.GetIdx()
                bonds_to_highlight.append(b_idx)
                bond_highlight_colors[b_idx] = color

    options: MolDrawOptions = drawing.drawOptions()
    if background_color is not None:
        options.setBackgroundColour(hex_to_rgb_tuple(background_color))
    options.useBWAtomPalette()

    # Remove isotopic labels for drawing
    cp_tagged_parent = deepcopy(tagged_parent)
    for atom in cp_tagged_parent.GetAtoms():
        atom.SetIsotope(0)

    # drawing.DrawMolecule(
    DrawMoleculeACS1996(
        drawing,
        cp_tagged_parent,
        highlightAtoms=atoms_to_highlight,
        highlightBonds=bonds_to_highlight,
        highlightAtomColors=atom_highlight_colors,
        highlightBondColors=bond_highlight_colors,
    )

    drawing.FinishDrawing()
    mol_svg_str = drawing.GetDrawingText().replace("svg:", "")

    # Inject motif legend
    svg_str = add_motif_legend_to_svg(
        svg_str=mol_svg_str,
        highlights=highlights,
    )

    return svg_str


@blp_draw_compound_item.post("/api/drawCompoundItem")
def draw_compound_item():
    """
    Endpoint to handle drawing of compound items.

    :return: JSON response with query results or error message
    """
    payload = request.get_json(force=True) or {}

    # Check required fields
    tagged_parent_smiles = payload.get("taggedParentSmiles", None)
    primary_sequence = payload.get("primarySequence", None)

    if tagged_parent_smiles is None or primary_sequence is None:
        return jsonify({"svg": ""}), 500
    
    # Parse out highlights
    highlights: list[Highlight] = []
    palette = [c.normalize() for c in Palette]
    for motif_idx, motif in enumerate(primary_sequence.get("sequence", [])):
        # Format display name
        display_name = motif.get("name", "")
        default_display_name = f"M{motif_idx+1:02d}"
        if display_name:
            display_name = "".join(re.findall(r"[A-Za-z0-9]", display_name))[:3].upper()
            if display_name == "":
                display_name = default_display_name
        else:
            display_name = default_display_name

        color = palette[motif_idx % len(palette)]
        tags = motif.get("tags", [])
        highlights.append(Highlight(
            display_name=display_name,
            tags=set(tags),
            color=color)
        )

    # Draw highlights
    svg_str = draw_highlights(
        tagged_parent_smiles=tagged_parent_smiles,
        highlights=highlights,
        background_color=payload.get("backgroundColor", None),
    )
    
    return jsonify({"svg": svg_str}), 200