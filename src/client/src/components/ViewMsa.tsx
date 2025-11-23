import React from "react";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import Button from "@mui/material/Button";
import ZoomOutIcon from "@mui/icons-material/ZoomOut";
import ZoomInIcon from "@mui/icons-material/ZoomIn";
import RefreshIcon from "@mui/icons-material/Refresh";
import PaletteIcon from "@mui/icons-material/Palette";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";
import SettingsIcon from "@mui/icons-material/Settings";
import { useNotifications } from "./NotificationProvider";
import { Session, MsaSettings, MsaState, MsaSequence, PrimarySequence } from "../features/session/types";
import { runMsa } from "../features/views/api";
import { DialogColorPalette } from "./DialogColorPalette";
import { DialogMsaSettings } from "./DialogMsaSettings";

// Imports for dragging and dropping rows and motifs
import { DndContext, DragEndEvent } from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
  horizontalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import DragIndicatorIcon from "@mui/icons-material/DragIndicator";

// Helper: turn a name into a display name by keeping only alphanumerics, capitalizing, and taking up to 3 characters
const toDisplayName = (name: string | null): string | null => {
  if (!name) return null;
  const alphanumeric = name.replace(/[^a-z0-9]/gi, "");
  return alphanumeric.slice(0, 3).toUpperCase();
};

interface SortableRowProps {
  row: MsaSequence;
  labelWidth: number;
  motifWidth: number;
  zoom: number;
  centerId: string | null;
  session: Session;
  onSetCenter: (id: string) => void;
  onHideRow: (id: string) => void;
  children: React.ReactNode; // the motifs
}

const SortableRow: React.FC<SortableRowProps> = ({
  row,
  labelWidth,
  centerId,
  motifWidth,
  zoom,
  session,
  onSetCenter,
  onHideRow,
  children,
}) => {
  const rowSortableId = `row:${row.id}`;
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: rowSortableId });

  const isCenter = centerId === row.id;

  return (
    <>
      <Box
        ref={setNodeRef}
        onClick={() => onSetCenter(row.id as string)}
        sx={{
          transform: transform ? CSS.Transform.toString(transform) : undefined,
          transition,
          m: 0,
          p: 0,
          height: 20,
          fontWeight: 600,
          zIndex: 100,
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          px: 1,
          borderRadius: 1,
          backgroundColor: isCenter ? "warning.light" : "background.paper",
          border: isCenter ? "1px solid" : "1px solid transparent",
          borderColor: isCenter ? "warning.main" : "transparent",
        }}
      >
        <Box
          {...listeners}
          {...attributes}
          sx={{
            display: "flex",
            alignItems: "center",
            cursor: "grab",
          }}
          onClick={e => e.stopPropagation()} // don't trigger center selection on drag
        >
          <DragIndicatorIcon fontSize="small" />
        </Box>
        <Stack direction="row" alignItems="center" justifyContent="space-between" sx={{ width: "100%", pl: 1 }}>
          <Tooltip
            title={row.name || row.id}
            placement="top"
            arrow
          >
            <Typography
              variant="body2"
              sx={{
                fontWeight: 600,
                maxWidth: isCenter ? labelWidth - 135 : labelWidth - 80,
                lineHeight: "20px",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
                zIndex: 101,
                userSelect: "none",
              }}
            >
              {row.name || row.id}
            </Typography>
          </Tooltip>
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 0.5,
            }}
          >
            {isCenter && (
              <Chip
                label="CENTER"
                size="small"
                color="warning"
                sx={{
                  height: 18,
                  borderRadius: 0,
                  fontSize: "0.7rem",
                }}
              />
            )}
            <VisibilityOffIcon 
              fontSize="small"
              onClick={e => {
                e.stopPropagation();
                onHideRow(row.id as string);
              }}
            />
          </Box>
        </Stack>
      </Box>
      
      {/* Motifs */}
      {children}

      {/* Row line */}
      <Box
        sx={{
          gridColumn: "1 / -1", // span every column
          borderBottom: "1px solid",
          borderColor: "divider",
          height: 0,
          mt: "-19px",
          zIndex: 50,
        }}
      />
    </>
  )
}

interface SortableMotifCellProps {
  id: string;
  children: React.ReactNode;
}

const SortableMotifCell: React.FC<SortableMotifCellProps> = ({ id, children }) => {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({
    id,
    animateLayoutChanges: () => false,
  })

  return (
    <Box
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      sx={{
        transform: transform ? CSS.Transform.toString(transform) : undefined,
        transition,
        display: "inline-block",
        cursor: "grab",
        "&:focus": { outline: "none" },
        zIndex: 100,
      }}
    >
      {children}
    </Box>
  )
}

interface ViewMsaProps {
  session: Session;
  setSession: (updated: (prev: Session) => Session) => void;
}

export const ViewMsa: React.FC<ViewMsaProps> = ({
  session,
  setSession,
}) => {
  const { pushNotification } = useNotifications();

  const [zoom, setZoom] = React.useState(1);
  const handleZoomIn = () => setZoom(z => Math.min(z + 0.1, 3));
  const handleZoomOut = () => setZoom(z => Math.max(z - 0.1, 0.5));
  const [colorPaletteDialogOpen, setColorPaletteDialogOpen] = React.useState(false);
  const [msaSettingsDialogOpen, setMsaSettingsDialogOpen] = React.useState(false);

  const handleColorPaletteSave = (newMap: Record<string, string>) => {
    setSession(prev => ({
      ...prev,
      settings: {
        ...prev.settings,
        motifColorPalette: newMap,
      },
    }));
    pushNotification("Palette saved", "success");
  };

  const handleMsaSettingsSave = (newSettings: MsaSettings) => {
    setSession(prev => ({
      ...prev,
      settings: {
        ...prev.settings,
        msaSettings: newSettings,
      },
    }));
    pushNotification("MSA settings saved", "success");
  }

  const emptyMsaState = React.useCallback((): MsaState => ({
    aligned: false,
    centerId: null,
    sequences: [],
  }), []);

  const padSequence = React.useCallback(
    (sequence: PrimarySequence["sequence"], targetLength: number, baseId: string) => {
      // Always clone, so callers never share references
      const seq = sequence.map((m, idx ) => ({
        ...m,
        // keep existing cellKey if present, otherwise initialize
        cellKey: (m as any).cellKey ?? `${baseId}-motif-${m.id ?? "idx"}-${idx}`,
      }));

      if (targetLength <= 0) return [];
      if (seq.length > targetLength) {
        return seq.slice(0, targetLength);
      }
      if (seq.length >= targetLength) return seq;

      const paddingNeeded = targetLength - seq.length;
      const paddingMotifs = Array.from({ length: paddingNeeded }, (_, i) => ({
        id: `pad-${baseId}-${i}`,
        name: null,
        displayName: null,
        tags: [],
        smiles: null,
        morganfingerprint2048r2: null,
        // Give pads a unique cellKey as well
        cellKey: `pad-${baseId}-${i}`,
      }));

      return [...seq, ...paddingMotifs];
    },
    []
  );

  const normalizeMsaState = React.useCallback(() => {
    setSession(prev => {
      const prevState = prev.msaState ?? emptyMsaState();
      const order = new Map(prevState.sequences.map((seq, idx) => [seq.id, idx]));

      const collected: MsaSequence[] = [];
      prev.items.forEach(item => {
        item.primarySequences.forEach(ps => {
          if (ps.sequence.length === 0) return;
          const seqId = `${item.id}::${ps.id}`;
          const existing = prevState.sequences.find(s => s.id === seqId);
          const baseSeq = existing?.sequence ?? ps.sequence;
          collected.push({
            id: seqId,
            itemId: item.id,
            primarySequenceId: ps.id,
            name: item.name,
            // sequence: existing?.sequence ?? ps.sequence,
            sequence: baseSeq.map((m, idx) => ({
              ...m,
              // keep existing cellKey if present, otherwise initialize
              cellKey: (m as any).cellKey ?? `${seqId}-motif-${m.id ?? "idx"}-${idx}`,
            })),
            hidden: existing?.hidden ?? false,
          });
        });
      });

      // Preserve prior order; new sequences append
      collected.sort((a, b) => {
        const idxA = order.has(a.id) ? order.get(a.id)! : Number.MAX_SAFE_INTEGER;
        const idxB = order.has(b.id) ? order.get(b.id)! : Number.MAX_SAFE_INTEGER;
        return idxA - idxB;
      });

      if (collected.length === 0) {
        const nextState = emptyMsaState();
        if (JSON.stringify(prevState) === JSON.stringify(nextState)) {
          return prev;
        }
        return { ...prev, msaState: nextState };
      }

      const maxLength = Math.max(...collected.map(seq => seq.sequence.length), 0);
      const padded = collected.map(seq => ({
        ...seq,
        sequence: padSequence(seq.sequence, maxLength, seq.id),
      }));

      const nextCenter = prevState.centerId && padded.some(s => s.id === prevState.centerId)
        ? prevState.centerId
        : null;

      const nextState: MsaState = {
        ...prevState,
        sequences: padded,
        centerId: nextCenter,
      };

      // Lightweight equality check
      const sameLength =
        prevState.sequences.length === nextState.sequences.length &&
        prevState.centerId === nextState.centerId &&
        prevState.aligned === nextState.aligned;
      if (sameLength) {
        let identical = true;
        for (let i = 0; i < nextState.sequences.length; i++) {
          const prevSeq = prevState.sequences[i];
          const nextSeq = nextState.sequences[i];
          if (!prevSeq || prevSeq.id !== nextSeq.id || prevSeq.hidden !== nextSeq.hidden || prevSeq.name !== nextSeq.name) {
            identical = false;
            break;
          }
          if (prevSeq.sequence.length !== nextSeq.sequence.length) {
            identical = false;
            break;
          }
          if (JSON.stringify(prevSeq.sequence) !== JSON.stringify(nextSeq.sequence)) {
            identical = false;
            break;
          }
        }
        if (identical) return prev;
      }

      return { ...prev, msaState: nextState };
    });
  }, [emptyMsaState, padSequence, setSession]);

  React.useEffect(() => {
    normalizeMsaState();
  }, [normalizeMsaState, session.items]);

  const msaState = session.msaState ?? emptyMsaState();
  const msa = msaState.sequences;
  const hiddenIds = new Set(msa.filter(seq => seq.hidden).map(seq => seq.id));
  const centerId = msaState.centerId;
  const [aligning, setAligning] = React.useState<boolean>(false);

  const updateMsaState = React.useCallback(
    (updater: (state: MsaState) => MsaState) => {
      setSession(prev => {
        const nextState = updater(prev.msaState ?? emptyMsaState());
        return { ...prev, msaState: nextState };
      });
    },
    [emptyMsaState, setSession]
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over) return;

    const activeId = String(active.id);
    const overId = String(over.id);
    if (activeId === overId) return;

    // Row-level drag: ids like "row:<rowIds>"
    if (activeId.startsWith("row:") && overId.startsWith("row:")) {
      const fromRowId = activeId.slice("row:".length);
      const toRowId = overId.slice("row:".length);

      updateMsaState(state => {
        const sequences = [...state.sequences];
        const fromIndex = sequences.findIndex(s => s.id === fromRowId);
        const toIndex = sequences.findIndex(s => s.id === toRowId);
        if (fromIndex === -1 || toIndex === -1) return state;

        const [moved] = sequences.splice(fromIndex, 1);
        sequences.splice(toIndex, 0,  moved);

        return {
          ...state,
          aligned: false, // manual reorder breaks alignment
          sequences,
        }
      });

      return;
    }

    // Motif level drag depends on motif cellKey ids
    // Find which row cells belong to via search
    updateMsaState(state => {
      let rowIndex = -1;
      let fromCol = -1;
      let toCol = -1;

      state.sequences.forEach((row, rIdx) => {
        const seq = row.sequence as any[];
        const aIdx = seq.findIndex(m => m.cellKey === activeId);
        const oIdx = seq.findIndex(m => m.cellKey === overId);
        if (aIdx !== -1 && oIdx !== -1) {
          rowIndex = rIdx;
          fromCol = aIdx;
          toCol = oIdx;
        }
      })

      if (rowIndex === -1 || fromCol === -1 || toCol === -1) return state;

      const row = state.sequences[rowIndex];
      const seq = [...row.sequence];

      const [movedMotif] = seq.splice(fromCol, 1);
      seq.splice(toCol, 0, movedMotif);

      const newSequences = state.sequences.map((s, idx) => 
        idx === rowIndex ? { ...s, sequence: seq } : s
      );

      return {
        ...state,
        aligned: false, // manual reorder breaks alignment
        sequences: newSequences,
      };
    })
    
  }

  const handleHideRow = (id: string) => {
    updateMsaState(state => ({
      ...state,
      centerId: state.centerId === id ? null : state.centerId,
      sequences: state.sequences.map(seq =>
        seq.id === id ? { ...seq, hidden: true } : seq
      ),
    }));
  };

  const handleResetHidden = () => {
    updateMsaState(state => ({
      ...state,
      sequences: state.sequences.map(seq => ({ ...seq, hidden: false })),
    }));
  };

  const handleSetCenter = (id: string) => {
    updateMsaState(state => ({
      ...state,
      centerId: id,
    }));
  };

  if (msa.length === 0) {
    return (
      <Typography variant="body2">
        No primary sequences available in session items to display MSA.
      </Typography>
    );
  }

  const visibleRows = msa.filter(row => !hiddenIds.has(row.id as string));
  const msaLength = visibleRows.length > 0
    ? Math.max(...visibleRows.map(row => row.sequence.length))
    : 0;
  const motifWidth = 50 * zoom;
  const labelWidth = 250;
  const colTemplate = `${labelWidth}px repeat(${msaLength}, ${motifWidth}px) 1fr`;

  const stripPads = (seq: PrimarySequence["sequence"]) =>
    seq.filter(motif => !(motif.id ?? "").startsWith("pad-"));

  const handleAlign = async () => {
    if (!centerId) {
      pushNotification("Please select a center sequence for alignment.", "warning");
      return;
    }

    const currentVisible = msa.filter(row => !hiddenIds.has(row.id as string));

    if (!currentVisible.some(r => r.id === centerId)) {
      pushNotification("Center sequence is hidden. Please unhide it before aligning.", "warning");
      return;
    }

    if (currentVisible.length < 2) {
      pushNotification("At least two sequences must be visible to perform alignment.", "warning");
      return;
    }

    // Build a canonical, *ungapped* base sequence per id,
    // using msaState if present, falling back to session.items.
    const baseById = new Map<
      string,
      { baseSeq: PrimarySequence["sequence"]; name: string | null; itemId?: string; primarySequenceId?: string }
    >();

    session.items.forEach(item => {
      item.primarySequences.forEach(ps => {
        const seqId = `${item.id}::${ps.id}`;
        const existing = msaState.sequences.find(s => s.id === seqId);

        // Prefer the current msaState sequence (stripped of our pads),
        // otherwise fall back to the original primary sequence.
        const rawSeq = existing ? stripPads(existing.sequence) : stripPads(ps.sequence);

        baseById.set(seqId, {
          // Deep clone: runMsa cannot mutate our state
          baseSeq: rawSeq.map(m => ({ ...m })),
          name: item.name,
          itemId: item.id,
          primarySequenceId: ps.id,
        });
      });
    });

    setAligning(true);
    try {
      const result = await runMsa({
        primarySequences: currentVisible.map(seq => {
          const base = baseById.get(seq.id);
          if (!base) {
            // Shouldn't happen, but be defensive
            return {
              id: seq.id,
              name: seq.name,
              sequence: stripPads(seq.sequence).map(m => ({ ...m })),
            };
          }
          return {
            id: seq.id,
            name: base.name ?? seq.name,
            sequence: base.baseSeq.map(m => ({ ...m })), // clone again for safety
          };
        }),
        centerId,
        msaSettings: session.settings.msaSettings,
      });

      const alignedSequences = result.alignedSequences;
      const alignedLength = Math.max(...alignedSequences.map(seq => seq.sequence.length), 0);

      updateMsaState(state => {
        const alignedIds = new Set(alignedSequences.map(seq => seq.id));
        const nextSequences: MsaSequence[] = [];

        alignedSequences.forEach(seq => {
          const base = baseById.get(seq.id);
          const existing = state.sequences.find(s => s.id === seq.id);

          nextSequences.push({
            ...(existing ?? {}),
            id: seq.id,
            itemId: base?.itemId ?? (existing as MsaSequence | undefined)?.itemId ?? seq.id,
            primarySequenceId: base?.primarySequenceId ?? (existing as MsaSequence | undefined)?.primarySequenceId ?? seq.id,
            name: base?.name ?? seq.name,
            // padSequence now clones internally, so this is a fresh array
            sequence: padSequence(seq.sequence, alignedLength, seq.id),
            hidden: false,
          });
        });

        // Keep previously hidden sequences (not part of this alignment)
        state.sequences
          .filter(seq => seq.hidden && !alignedIds.has(seq.id))
          .forEach(seq => {
            const base = baseById.get(seq.id);
            const rawSeq = base ? base.baseSeq : stripPads(seq.sequence);
            nextSequences.push({
              ...seq,
              sequence: padSequence(rawSeq, alignedLength, seq.id),
              hidden: true,
            });
          });

        return {
          ...state,
          aligned: true,
          centerId,
          sequences: nextSequences,
        };
      });

      pushNotification("Alignment completed successfully.", "success");
    } catch (error) {
      pushNotification(`An error occurred during alignment: ${error}`, "error");
    } finally {
      setAligning(false);
    }
  }

  return (
    <Box sx={{ maxWidth: "100vw", overflowX: "hidden" }}>
      <Stack direction="column" spacing={2}>
        <Typography variant="body1">
          Click a row label to choose the center sequence to align all other sequences against. Press the <strong>Align</strong> button to perform the alignment.
          Hidden rows are excluded from alignment, but can be reset using the <strong>Reset hidden</strong> button.
          The state of the alignment is saved in the session and can be revisited later.
          Any manual changes made to the alignment are local and do not affect the readouts for querying.
        </Typography>
        <Stack direction="row" spacing={1} sx={{ justifyContent: "space-between" }}>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Button
              variant="contained"
              size="small"
              disabled={
                aligning || visibleRows.length < 2 || !centerId
              }
              onClick={handleAlign}
            >
              {aligning ? "Aligning..." : "Align"}
            </Button>
            <Button
              size="small"
              variant="contained"
              color="secondary"
              onClick={handleResetHidden}
              disabled={hiddenIds.size === 0}
            >
              {hiddenIds.size > 0 ? `Reset hidden (${hiddenIds.size})` : "Reset hidden"}
            </Button>
            <Tooltip title="Adjust MSA settings" arrow>
              <SettingsIcon
                fontSize="small"
                onClick={() => setMsaSettingsDialogOpen(true)}
                sx={{
                  cursor: "pointer",
                  color: "text.primary",
                  transform: msaSettingsDialogOpen ? "rotate(180deg)" : "rotate(0deg)",
                  transition: "transform 0.4s ease",
                }}
              />
            </Tooltip>
            {msaState.aligned ? (
              <Chip
                label="Aligned"
                size="small"
                color="success"
                sx={{
                  height: 20,
                  fontSize: "0.75rem",
                }}
              />
            ) : (
              <Chip
                label="Unaligned"
                size="small"
                color="error"
                sx={{
                  height: 20,
                  fontSize: "0.75rem",
                }}
              />
            )}
          </Box>
          {/* Toolbar */}
          <Box
            sx={{
              display: "flex",
              flexDirection: "row",
              justifyContent: "space-between",
              alignItems: "center",
              px: 2,
              pt: 2,
            }}
          >
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <Tooltip title="Zoom MSA out">
                <ZoomOutIcon
                  onClick={handleZoomOut}
                  sx={{ cursor: "pointer" }}
                />
              </Tooltip>
              <Tooltip title="Zoom MSA in">
                <ZoomInIcon
                  onClick={handleZoomIn}
                  sx={{ cursor: "pointer" }}
                />
              </Tooltip>
              <Tooltip title="Reset zoom">
                <RefreshIcon
                  onClick={() => setZoom(1)}
                  sx={{ cursor: "pointer" }}
                />
              </Tooltip>
              <Tooltip title="Change color palette">
                <PaletteIcon
                  onClick={() => setColorPaletteDialogOpen(true)}
                  sx={{ cursor: "pointer" }}
                />
              </Tooltip>
            </Box>
          </Box>
        </Stack>
        {visibleRows.length > 0 ? (
          <Stack direction="column" spacing={1}>
            {/* MSA display */}
            <Box
              sx={{
                width: "100%",
                overflowX: "auto",
                overflowY: "hidden",
                pb: 2,
              }}
            >
              <DndContext onDragEnd={handleDragEnd}>
              {/* Row-level sortable context (vertical) */}
                <SortableContext
                  items={visibleRows.map(row => `row:${row.id}`)}
                  strategy={verticalListSortingStrategy}
                >
                  <Box
                    sx={{
                      display: "grid",
                      gridTemplateColumns: colTemplate,
                      width: "100%",
                      gap: 1,
                    }}
                  >
                    {visibleRows.map((row, rowIndex) => (
                      <React.Fragment key={row.id ?? rowIndex}>
                        <SortableRow
                          row={row}
                          labelWidth={labelWidth}
                          motifWidth={motifWidth}
                          zoom={zoom}
                          centerId={centerId ?? null}
                          session={session}
                          onSetCenter={handleSetCenter}
                          onHideRow={handleHideRow}
                        >
                          <SortableContext
                            items={row.sequence.map(m => (m as any).cellKey)}
                            strategy={horizontalListSortingStrategy}
                          >
                            {row.sequence.map((motif, colIndex) => {
                              const cellKey = (motif as any).cellKey as string;
                              const isPad = (motif.id ?? "").startsWith("pad-");

                              return (
                                <SortableMotifCell
                                  id={cellKey}
                                  key={cellKey}
                                >
                                  {!isPad ? (
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
                                        title={motif.name || "Unknown motif"}
                                        placement="top"
                                        arrow
                                      >
                                        <Chip
                                          label={toDisplayName(motif.displayName || motif.name || null) || "UNK"}
                                          size="small"
                                          sx={{
                                            mt: "-4px",
                                            width: motifWidth,
                                            height: 20,
                                            textAlign: "center",
                                            backgroundColor:
                                              session.settings.motifColorPalette[motif.name || ""] ||
                                              "background.paper",
                                            border: "1px solid",
                                            borderColor: "primary.main",
                                            zIndex: 100,
                                            fontSize: `${Math.max(0.5, Math.min(1.0, zoom)) * 0.75}rem`,
                                            transition: "background-color 0s ease-in-out",
                                          }}
                                        />
                                      </Tooltip>
                                    </Box>
                                  ) : (
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
                                          width: 3,
                                          height: 3,
                                          borderRadius: "50%",
                                          backgroundColor: "text.primary",
                                          zIndex: 100,
                                        }}
                                      />
                                    </Box>
                                  )}
                                </SortableMotifCell>
                              )
                            })}
                          </SortableContext>
                        </SortableRow>
                      </React.Fragment>
                    ))}
                  </Box>
                </SortableContext>
              </DndContext>
            </Box>
          </Stack>
        ) : (
          <Typography variant="body2" sx={{ mt: 2 }}>
            All sequences are hidden. Reset hidden to show them again.
          </Typography>
        )}
      </Stack>

      {/* Color palette dialog */}
      <DialogColorPalette
        open={colorPaletteDialogOpen}
        onClose={() => setColorPaletteDialogOpen(false)}
        colorMap={session.settings.motifColorPalette}
        onSave={handleColorPaletteSave}
      />

      {/* MSA settings dialog */}
      <DialogMsaSettings
        open={msaSettingsDialogOpen}
        onClose={() => setMsaSettingsDialogOpen(false)}
        settings={session.settings.msaSettings}
        onSave={handleMsaSettingsSave}
      />
    </Box>
  );
}
