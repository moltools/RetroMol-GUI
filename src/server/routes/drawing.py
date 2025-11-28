"""Module for handling drawing-related routes."""

import re
from copy import deepcopy
from enum import Enum
from dataclasses import dataclass

from flask import Blueprint, request, jsonify
from rdkit.Chem.Draw.rdMolDraw2D import DrawMoleculeACS1996, MolDraw2DSVG, MolDrawOptions
from retromol.chem import smiles_to_mol
from raichu.run_raichu import draw_cluster
from raichu.antismash import get_nrps_pks_modules
from pikachu.general import read_smiles
from pikachu.drawing.drawing import Drawer, Options


blp_draw_compound_item = Blueprint("draw_compound_item", __name__)
blp_draw_gene_cluster_item = Blueprint("draw_gene_cluster_item", __name__)


class Palette(Enum):
    Orange = (230, 159, 0)
    SkyBlue = (86, 180, 233)
    Green = (3, 158, 115)
    Yellow = (240, 228, 66)
    Blue = (0, 114, 178)
    Red = (213, 95, 0)
    Pink = (204, 121, 167)

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


def rgba_to_hex(rgba: tuple[float, float, float]) -> str:
    """
    Convert RGBA tuple to hex color string.
    
    :param rgba: RGBA color tuple
    :return: tuple of hex color string
    """
    r, g, b = rgba
    r_i = int(r * 255)
    g_i = int(g * 255)
    b_i = int(b * 255)
    return f"#{r_i:02x}{g_i:02x}{b_i:02x}"


def extract_svg_body(svg_str: str) -> tuple[float, float, str]:
    """
    Extract width, height and inner content from an SVG string.

    :param svg_str: SVG string
    :return: tuple of (width, height, inner SVG content)
    :raises ValueError: if SVG tag or dimensions cannot be parsed
    """
    # Find opening <svg ...> tag
    m = re.search(r"<svg[^>]*>", svg_str)
    if not m:
        raise ValueError("No <svg> tag found in RDKit/PIKAChU SVG")

    svg_open_tag = m.group(0)
    inner = svg_str[m.end():]
    # Remove closing tag
    inner = inner.replace("</svg>", "")

    width_match = re.search(r'width=(["\'])([\d.]+)(?:px)?\1', svg_open_tag)
    height_match = re.search(r'height=(["\'])([\d.]+)(?:px)?\1', svg_open_tag)

    if not width_match or not height_match:
        raise ValueError("Could not parse width/height from SVG header")

    width = float(width_match.group(2))
    height = float(height_match.group(2))

    return width, height, inner


def build_compound_scheme_svg(
    mol_width: float,
    mol_height: float,
    mol_inner_svg: str,
    highlights: list[Highlight],
    arrow_labels: list[str] | None = None,
) -> str:
    """
    Build a full SVG with: [structure] --arrow--> [structure] --arrow--> [primary sequence]

    :param mol_width: width of single molecule drawing
    :param mol_height: height of single molecule drawing
    :param mol_inner_svg: inner SVG content of molecule (no outer <svg> tags)
    :param highlights: motif info for the primary sequence panel
    :param arrow_labels: optional labels above the arrows, e.g. ["step 1", "step 2"]
    """
    arrow_labels = arrow_labels or ["", ""]

    # Layout constants
    PADDING = 20.0
    H_GAP = 25.0  # gap between elements
    ARROW_LEN = 120.0
    AVG_CHAR_WIDTH = 7.0
    MIN_BOX_WIDTH = 40.0
    H_TEXT_PADDING = 14.0
    SEQ_BOX_HEIGHT = 24.0
    SEQ_BOX_GAP = 4.0

    n_motifs = len(highlights)
    if n_motifs > 0:
        seq_panel_height = (
            2 * PADDING +
            n_motifs * SEQ_BOX_HEIGHT +
            (n_motifs - 1) * SEQ_BOX_GAP
        )
    else:
        seq_panel_height = 2 * PADDING + SEQ_BOX_HEIGHT

    content_height = max(mol_height, seq_panel_height)
    total_height = content_height + 2 * PADDING

    # X positions
    mol1_x = PADDING
    mol1_y = (total_height - mol_height) / 2.0

    arrow1_x1 = mol1_x + mol_width + H_GAP
    arrow1_x2 = arrow1_x1 + ARROW_LEN

    mol2_x = arrow1_x2 + H_GAP
    mol2_y = mol1_y

    arrow2_x1 = mol2_x + mol_width + H_GAP
    arrow2_x2 = arrow2_x1 + ARROW_LEN

    seq_x = arrow2_x2 + H_GAP
    seq_y = (total_height - seq_panel_height) / 2.0

    widest_box = max(
        max(MIN_BOX_WIDTH, len(h.display_name) * AVG_CHAR_WIDTH + H_TEXT_PADDING)
        for h in highlights
    ) if highlights else MIN_BOX_WIDTH

    seq_panel_width = widest_box + 2 * PADDING

    total_width = seq_x + seq_panel_width + PADDING

    arrow_y = total_height / 2.0
    arrow_label_offset = 12.0  # distance above arrow for text

    # Assemble SVG
    svg_parts: list[str] = []

    svg_parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{total_width:.2f}" height="{total_height:.2f}" '
        f'viewBox="0 0 {total_width:.2f} {total_height:.2f}">'
    )

    # Arrowhead marker
    svg_parts.append(
        """
        <defs>
          <marker id="arrowhead" markerWidth="10" markerHeight="7"
                  refX="10" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" />
          </marker>
        </defs>
        """
    )

    # First molecule
    svg_parts.append(
        f'<g transform="translate({mol1_x:.2f},{mol1_y:.2f})">'
        f'{mol_inner_svg}'
        '</g>'
    )

    # Second molecule
    svg_parts.append(
        f'<g transform="translate({mol2_x:.2f},{mol2_y:.2f})">'
        f'{mol_inner_svg}'
        '</g>'
    )

    # Arrow 1
    svg_parts.append(
        f'<line x1="{arrow1_x1:.2f}" y1="{arrow_y:.2f}" '
        f'x2="{arrow1_x2:.2f}" y2="{arrow_y:.2f}" '
        f'stroke="black" stroke-width="1.5" marker-end="url(#arrowhead)" />'
    )
    if arrow_labels[0]:
        mid_x1 = (arrow1_x1 + arrow1_x2) / 2.0
        svg_parts.append(
            f'<text x="{mid_x1:.2f}" y="{arrow_y - arrow_label_offset:.2f}" '
            f'text-anchor="middle" font-size="12">{arrow_labels[0]}</text>'
        )

    # Arrow 2
    svg_parts.append(
        f'<line x1="{arrow2_x1:.2f}" y1="{arrow_y:.2f}" '
        f'x2="{arrow2_x2:.2f}" y2="{arrow_y:.2f}" '
        f'stroke="black" stroke-width="1.5" marker-end="url(#arrowhead)" />'
    )
    if arrow_labels[1]:
        mid_x2 = (arrow2_x1 + arrow2_x2) / 2.0
        svg_parts.append(
            f'<text x="{mid_x2:.2f}" y="{arrow_y - arrow_label_offset:.2f}" '
            f'text-anchor="middle" font-size="12">{arrow_labels[1]}</text>'
        )

    # Primary sequence panel on the right (vertical legend)
    # Draw background panel (optional, can remove if you don’t want it)
    title_text = "primary sequence"
    title_font_size = 14.0

    title_x = seq_x + seq_panel_width / 2.0
    title_y = seq_y - 6.0

    svg_parts.append(
        f'<text x="{title_x:.2f}" y="{title_y:.2f}" '
        f'text-anchor="middle" font-size="{title_font_size}" '
        f'font-weight="bold">{title_text}</text>'
    )

    svg_parts.append(
        f'<rect x="{seq_x:.2f}" y="{seq_y:.2f}" '
        f'width="{seq_panel_width:.2f}" height="{seq_panel_height:.2f}" '
        f'rx="4" ry="4" fill="white" stroke="#dddddd" />'
    )

    current_y = seq_y + PADDING
    for h in highlights:
        fill_hex = rgba_to_hex(h.color)
        # Box
        text_len = len(h.display_name)
        box_width = max(MIN_BOX_WIDTH, text_len * AVG_CHAR_WIDTH + H_TEXT_PADDING)
        svg_parts.append(
            f'<rect x="{seq_x + PADDING:.2f}" y="{current_y:.2f}" '
            f'width="{box_width:.2f}" height="{SEQ_BOX_HEIGHT:.2f}" '
            f'rx="3" ry="3" fill="{fill_hex}" stroke="black" />'
        )
        # Text in middle
        text_x = seq_x + PADDING + box_width / 2.0
        text_y = current_y + SEQ_BOX_HEIGHT / 2.0
        svg_parts.append(
            f'<text x="{text_x:.2f}" y="{text_y:.2f}" '
            f'text-anchor="middle" dominant-baseline="middle" '
            f'font-size="12">{h.display_name}</text>'
        )

        current_y += SEQ_BOX_HEIGHT + SEQ_BOX_GAP

    svg_parts.append("</svg>")

    return "".join(svg_parts)


def draw_structure_with_pikachu(drawer: Drawer) -> str:
    """
    Draw a molecular structure using Pikachu and return the SVG string.

    :param drawer: Drawer object with the molecular structure
    :return: SVG string of the drawn structure
    """
    drawer.flip_y_axis()
    drawer.move_to_positive_coords()
    drawer.convert_to_int()

    min_x = 100000000
    max_x = -100000000
    min_y = 100000000
    max_y = -100000000

    for atom in drawer.structure.graph:
        if atom.draw.positioned:
            if atom.draw.position.x < min_x:
                min_x = atom.draw.position.x
            if atom.draw.position.y < min_y:
                min_y = atom.draw.position.y
            if atom.draw.position.x > max_x:
                max_x = atom.draw.position.x
            if atom.draw.position.y > max_y:
                max_y = atom.draw.position.y

    width = max_x - min_x + 2 * drawer.options.padding
    height = max_y - min_y + 2 * drawer.options.padding

    svg_string = f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">"""
    svg_string += drawer.svg_style
    svg_string += drawer.draw_svg(annotation=None, numbered_atoms=None)
    svg_string += "</svg>"

    return svg_string


def draw_highlights(
    tagged_parent_smiles: str,
    highlights: list[Highlight],
    background_color: str | None = None,
    engine: str = "rdkit",
) -> None:
    """
    Draw highlights on a molecule given its tagged SMILES representation.

    :param tagged_parent_smiles: SMILES string of the tagged parent molecule
    :param highlights: list of Highlight objects specifying tags and alpha values
    :param background_color: optional background color in hex format
    :param engine: drawing engine to use, either "rdkit" or "pikachu"
    :return: SVG string of the drawn molecule with highlights
    :raises ValueError: if an unknown drawing engine is specified
    """
    if engine == "rdkit":
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
    
    elif engine == "pikachu":
        # We have to translate isotope-stored tags from the SMILES to atom.nr in PIKAChU
        # PIKAChU also labels hydrogen atoms, which we have to ignore for the highlights

        # Create mapping: isotope tag to idx (read order in SMILES)
        tag_to_idx = {}
        tagged_parent = smiles_to_mol(tagged_parent_smiles)
        for atom in tagged_parent.GetAtoms():
            idx = atom.GetIdx()
            tag = atom.GetIsotope()
            if tag > 0:
                tag_to_idx[tag] = idx

        # First map every tag to its corresponding Highlight's color
        color_map = {}
        for highlight in highlights:
            for tag in highlight.tags:
                if tag in tag_to_idx:
                    atom_idx = tag_to_idx[tag]
                    color_map[atom_idx + 1] = rgba_to_hex(highlight.color)
        
        # Now create a lookup of every non-hydogen atom
        # PIKAChU reads the SMILES string from left-to-right so we can just count
        structure = read_smiles(tagged_parent_smiles)
        non_h_count = 0
        for atom in structure.get_atoms():
            if atom.type == "H":
                continue
            
            non_h_count += 1
            atom.draw.colour = color_map.get(non_h_count, "black")

        options = Options()
        drawer = Drawer(structure, options=options, coords_only=True, kekulise=True)
        mol_svg_str = draw_structure_with_pikachu(drawer)
    
    else:
        raise ValueError(f"Unknown drawing engine: {engine}")
    
    mol_w, mol_h, mol_inner = extract_svg_body(mol_svg_str)
    arrow_labels = ["preprocess", "sequence"]
    svg_str = build_compound_scheme_svg(
        mol_width=mol_w,
        mol_height=mol_h,
        mol_inner_svg=mol_inner,
        highlights=highlights,
        arrow_labels=arrow_labels,
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
        display_name = motif.get("name", None)
        if not display_name:
            display_name = f"motif {motif_idx + 1}"

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
        engine="pikachu",
    )
    
    return jsonify({"svg": svg_str}), 200


@blp_draw_gene_cluster_item.post("/api/drawGeneClusterItem")
def draw_gene_cluster_item():
    """
    Endpoint to handle drawing of gene cluster items.

    :return: JSON response with query results or error message
    """
    payload = request.get_json(force=True) or {}

    fileContent = payload.get("fileContent", None)
    if fileContent is None:
        return jsonify({"svg": "", "error": "Missing fileContent"}), 500

    try:
        modules = get_nrps_pks_modules(fileContent, file_mode="file_content")
        cluster_repr = modules.make_raichu_cluster()
        svg_str = draw_cluster(cluster_repr, out_file=None, colour_by_module=False)
    except Exception as e:
        return jsonify({"svg": "", "error": str(e)}), 500

    return jsonify({"svg": svg_str}), 200
