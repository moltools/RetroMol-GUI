import React from "react";
import Typography from "@mui/material/Typography";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import ZoomOutIcon from "@mui/icons-material/ZoomOut";
import ZoomInIcon from "@mui/icons-material/ZoomIn";
import RefreshIcon from "@mui/icons-material/Refresh";
import DownloadIcon from "@mui/icons-material/Download";
import { SortableRow } from "./SortableRow";
import { SortableItem } from "./SortableItem";

// Imports for dragging and dropping rows and motifs
import { DndContext, DragEndEvent } from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  verticalListSortingStrategy,
  horizontalListSortingStrategy,
} from "@dnd-kit/sortable";

export type SequenceItem = {
  id: string;
  isGap: boolean;
  name: string | null;
  smiles: string | null;
};

export type Reference = {
  name: string;
  database_name: string;
  database_identifier: string;
};

export type MsaItem = {
  id: string;
  name?: string;
  alignment_score: number | null;
  cosine_score: number | null;
  sequence: SequenceItem[];
  references: Reference[];
};

export type QueryResult = {
  msa: MsaItem[];
};

type QueryResultViewProps = {
  result: QueryResult;
};

export const PROTECTED_NAME_TO_CODE: Record<string, string> = {
  ALANINE: "ALA",
  CYSTEINE: "CYS",
  ASPARTICACID: "ASP",
  GLUTAMICACID: "GLU",
  PHENYLALANINE: "PHE",
  GLYCINE: "GLY",
  HISTIDINE: "HIS",
  ISOLEUCINE: "ILE",
  LYSINE: "LYS",
  LEUCINE: "LEU",
  METHIONINE: "MET",
  ASPARAGINE: "ASN",
  PROLINE: "PRO",
  GLUTAMINE: "GLN",
  ARGININE: "ARG",
  SERINE: "SER",
  THREONINE: "THR",
  VALINE: "VAL",
  TRYPTOPHAN: "TRP",
  TYROSINE: "TYR",
};


export const renderChiralSuperscripts = (label: string) => {
  // Split into normal text + ^R/^S tokens
  const parts = label.split(/(\^[RS])/g).filter(Boolean);

  return (
    <>
      {parts.map((p, i) => {
        if (p === "^R" || p === "^S") {
          return (
            <sup key={i} style={{ fontSize: "0.7em", lineHeight: 0 }}>
              {p.slice(1)}
            </sup>
          );
        }
        return <React.Fragment key={i}>{p}</React.Fragment>;
      })}
    </>
  );
};

const isPolyketideMotif = (s: string | null | undefined) => {
  if (!s) return false;
  return /^[A-D](\^[RS])*(\d+)?(\^[RS])*$/i.test(s.trim());
};

export const makeToDisplayName = (protectedNameToCode: Record<string, string>) => {
  const norm = (s: string) => s.replace(/[^a-z0-9]/gi, "").toUpperCase();

  // normalize protected names + reserve protected codes
  const prot = new Map<string, string>(
    Object.entries(protectedNameToCode).map(([k, v]) => [norm(k), norm(v)])
  );
  const reserved = new Set<string>(Array.from(prot.values())); // e.g. ALA, GLY
  const used = new Set<string>(reserved);                      // block others from taking them
  const cache = new Map<string, string>();                     // per-name stability

  const candidates = (s: string) => {
    const out: string[] = [];
    if (s.length >= 3) {
      out.push(s.slice(0, 3)); // ABC
      for (let i = 3; i < s.length; i++) out.push(s[0] + s[1] + s[i]); // AB?
      for (let i = 2; i < s.length; i++) out.push(s[0] + s[i - 1] + s[i]); // A??
    }
    if (s.length >= 2) out.push(s.slice(0, 2)); // AB
    if (s.length >= 1) out.push(s[0]);          // A
    // de-dupe in order
    const seen = new Set<string>();
    return out.filter(c => c.length <= 3 && !seen.has(c) && (seen.add(c), true));
  };

  return (name: string | null): string | null => {
    if (!name) return null;
    const s = norm(name);
    if (!s) return null;

    const hit = cache.get(s);
    if (hit) return hit;

    // ONLY protected full names get protected 3-letter codes
    const canonical = prot.get(s);
    if (canonical) {
      cache.set(s, canonical);
      return canonical;
    }

    // don’t let non-protected names steal reserved AA codes
    for (const c of candidates(s)) {
      if (!used.has(c)) {
        used.add(c);
        cache.set(s, c);
        return c;
      }
    }
    return null;
  };
};

function parseColor(color: string, alpha: number): string {
  // HEX case: "#RGB" or "#RRGGBB"
  if (color.startsWith("#")) {
    let hex = color.replace(/^#/, "");
    // expand shorthand (#abc → aabbcc)
    if (hex.length === 3) {
      hex = hex.split("").map(c => c + c).join("");
    }
    // parse r, g, b
    const r = parseInt(hex.slice(0, 2), 16);
    const g = parseInt(hex.slice(2, 4), 16);
    const b = parseInt(hex.slice(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  };

  // HSL case: "hsl(h, s%, l%)"
  const hsl = color.match(
    /hsl\(\s*([\d.]+)(?:deg)?\s*,\s*([\d.]+)%\s*,\s*([\d.]+)%\s*\)/
  );
  if (hsl) {
    const h = hsl[1];
    const s = hsl[2];
    const l = hsl[3];
    return `hsla(${h}, ${s}%, ${l}%, ${alpha})`;
  };

  throw new Error(`Unsupported color format: ${color}`);
};

export const canonicalMotifKey = (s: string): string => {
  return s.trim().replace(/\s+/g, "").replace(/\^[RS]/g, "");
};

export const defaultMotifColorMap = (): Record<string, string> => {
  const newColorMap: Record<string, string> = {};

  const baseColors: Record<"A"|"B"|"C"|"D", string> = {
    A: "#e74c3c", // red
    B: "#27ae60", // green
    C: "#2980b9", // blue
    D: "#f39c12", // orange
  };

  for (const key of Object.keys(baseColors) as Array<keyof typeof baseColors>) {
    const color = baseColors[key];
    // plain (opaque) base
    newColorMap[key] = color;

    // numbered variants 1->15 -> alpha = 1/15...15/15
    for (let i = 1; i <= 15; i++) {
      const alpha = 1 - (i / 15);
      const alphaRounded = Math.round(alpha * 1000) / 1000;
      newColorMap[`${key}${i}`] = parseColor(color, alphaRounded);
    };
  };

  return newColorMap;
};

const getMotifColor = (name: string): string | null => {
  const colorMap = defaultMotifColorMap();
  const key = canonicalMotifKey(name);
  return colorMap[key] || null;
};

const renderChipLabel = (
  rawName: string | null,
  toDisplayName: (name: string | null) => string | null
): React.ReactNode => {
  const raw = rawName || "";
  const displayLabel = isPolyketideMotif(raw)
    ? raw
    : (toDisplayName(raw) || "X");
  return renderChiralSuperscripts(displayLabel);
};

const renderTooltipLabel = (
  rawName: string | null,
  toDisplayName: (name: string | null) => string | null
): React.ReactNode => {
  const raw = rawName || "";

  // Polyketide: show the short display code in tooltip
  if (isPolyketideMotif(raw)) {
    return toDisplayName(raw) || raw; // fallback to raw if code not available
  }

  // Non-polyketide: show full original name in tooltip
  return renderChiralSuperscripts(raw || "Unknown motif");
};


export const QueryResultView: React.FC<QueryResultViewProps> = ({ result }) => {
  // Keep order locally
  const [msa, setMsa] = React.useState<MsaItem[]>(result.msa);

  // Zoom
  const [zoom, setZoom] = React.useState<number>(1.0);
  const handleZoomIn = () => setZoom(z => Math.min(z + 0.1, 3.0));
  const handleZoomOut = () => setZoom(z => Math.max(z - 0.1, 0.5));
  const handleZoomReset = () => setZoom(1.0);

  const msaLength = result.msa.length > 0 ? Math.max(...result.msa.map((r) => r.sequence.length)) : 0;
  const motifWidth = 50 * zoom;
  const labelWidth = 250;
  const colTemplate = `${labelWidth}px repeat(${msaLength}, ${motifWidth}px) 1fr`;

  const toDisplayName = React.useMemo(() => makeToDisplayName(PROTECTED_NAME_TO_CODE), []);

  // If a new result comes in, refresh local state
  React.useEffect(() => {
    setMsa(result.msa);
  }, [result]);

  // Handle drag end
  const handleDragEnd = React.useCallback((event: DragEndEvent) => {
    const { active, over } = event;
    if (!over) return;

    const activeId = active.id as string;
    const overId = over.id as string;
    if (activeId === overId) return;

    setMsa((prev) => {
      // Row-level drag: both IDs must be row IDs
      const rowIds = new Set(prev.map((r) => r.id));
      const isRowDrag = rowIds.has(activeId) && rowIds.has(overId);

      if (isRowDrag) {
        const fromIndex = prev.findIndex((r) => r.id === activeId);
        const toIndex = prev.findIndex((r) => r.id === overId);
        if (fromIndex === -1 || toIndex === -1) return prev;
        return arrayMove(prev, fromIndex, toIndex);
      };

      // Item-level drag: both IDs must be in the SAME row
      let rowIndex = -1;
      let fromCol = -1
      let toCol = -1;

      for (let r = 0; r < prev.length; r++) {
        const seq = prev[r].sequence;
        const aIdx = seq.findIndex((s) => s.id === activeId);
        const oIdx = seq.findIndex((s) => s.id === overId);

        // Only reorder if both items are within the SAME row
        if (aIdx !== -1 && oIdx !== -1) {
          rowIndex = r;
          fromCol = aIdx;
          toCol = oIdx;
          break;
        };
      };

      if (rowIndex === -1) return prev;

      const row = prev[rowIndex];
      const newSeq = arrayMove([...row.sequence], fromCol, toCol);

      return prev.map((r, idx) => idx === rowIndex ? { ...r, sequence: newSeq } : r);
    });
  }, []);

  return (
    <div>
      <Typography component="h1" variant="subtitle1">
        Query results
      </Typography>
    
      {/* Toolbar */}
      <Box
        sx={{
          display: "flex",
          flexDirection: "row",
          justifyContent: "right",
          alignItems: "center",
          px: 2,
          py: 1,
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <Tooltip title="Zoom MSA out" arrow><ZoomOutIcon onClick={handleZoomOut} sx={{ cursor: "pointer" }} /></Tooltip>
          <Tooltip title="Zoom MSA in" arrow><ZoomInIcon onClick={handleZoomIn} sx={{ cursor: "pointer" }} /></Tooltip>
          <Tooltip title="Reset zoom" arrow><RefreshIcon onClick={handleZoomReset} sx={{ cursor: "pointer" }} /></Tooltip>
          <Tooltip title="Download as SVG" arrow><DownloadIcon onClick={() => {}} sx={{ cursor: "not-allowed" }} /></Tooltip>
        </Box>
      </Box>

      <Stack direction="column" spacing={1}>
        <Box
          sx={{
            width: "100%",
            overflowX: "auto",
            overflowY: "hidden",
            pb: 2,
          }}
        >
          <DndContext onDragEnd={handleDragEnd}>
            <SortableContext
              items={result.msa.map((item) => item.id)}
              strategy={verticalListSortingStrategy}
            >
              <Box
                sx={{
                  display: "grid",
                  gridTemplateColumns: colTemplate,
                  width: "100%",
                  gap: 1,
                  py: 1,
                }}
              >
                {msa.map((row) => (
                  <React.Fragment key={row.id}>
                    <SortableRow row={row} labelWidth={labelWidth}>
                      <SortableContext
                        items={row.sequence.map((item) => item.id)}
                        strategy={horizontalListSortingStrategy}
                      >
                        {row.sequence.map(item => (
                          <SortableItem id={item.id} key={item.id} disabled={item.isGap}>
                            {item.isGap ? (
                              <Box
                                sx={{
                                  m: 0,
                                  width: motifWidth,
                                  height: 20,
                                  backgroundColor: "transparent",
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                }}
                              >
                                <Box
                                  sx={{
                                    width: Math.max(2, 3 * zoom),
                                    height: Math.max(2, 3 * zoom),
                                    borderRadius: "50%",
                                    backgroundColor: "text.secondary",
                                  }}
                                />
                              </Box>
                            ) : (
                              <Box
                                component="span"
                                sx={{
                                  backgroundColor: "background.paper",
                                  borderRadius: 1,
                                  display: "inline-block",
                                  zIndex: 99,
                                }}
                              >
                                <Tooltip
                                  title={renderTooltipLabel(item.name, toDisplayName)}
                                  arrow
                                >
                                  <Chip
                                    label={renderChipLabel(item.name, toDisplayName)}
                                    size="small"
                                    sx={{
                                      mt: "-4px",
                                      width: motifWidth,
                                      height: 20,
                                      textAlign: "center",
                                      backgroundColor: getMotifColor(item.name || "") || "background.paper",
                                      border: "1px solid",
                                      borderColor: getMotifColor(item.name || "") || "primary.main",
                                      zIndex: 100,
                                      fontSize: `${Math.max(0.5, Math.min(1.0, zoom)) * 0.75}rem`,
                                      transition: "background-color 0s ease-in-out",
                                    }}
                                  />
                                </Tooltip>
                              </Box>
                            )}
                          </SortableItem>
                        ))}
                      </SortableContext>
                    </SortableRow>
                  </React.Fragment>
                ))}
              </Box>
            </SortableContext>
          </DndContext>
        </Box>
      </Stack>
    </div>
  );
};
