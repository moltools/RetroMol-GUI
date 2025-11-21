import React from "react";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import Button from "@mui/material/Button";
import ZoomOutIcon from "@mui/icons-material/ZoomOut";
import ZoomInIcon from "@mui/icons-material/ZoomIn";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";
import { useNotifications } from "./NotificationProvider";
import { Session } from "../features/session/types";
import { PrimarySequence } from "../features/session/types";
import { runMsa } from "../features/views/api";

// Helper: turn a name into a display name by keeping only alphanumerics, capitalizing, and taking up to 3 characters
const toDisplayName = (name: string | null): string | null => {
  if (!name) return null;
  const alphanumeric = name.replace(/[^a-z0-9]/gi, "");
  return alphanumeric.slice(0, 3).toUpperCase();
};

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

  const [msa, setMsa] = React.useState<PrimarySequence[] | null>(null);
  
  // Which sequence is the center start for alignment
  const [centerId, setCenterId] = React.useState<string | null>(null);

  // Which sequences are hidden (excluded from MSA view + alignment)
  const [hiddenIds, setHiddenIds] = React.useState<Set<string>>(
    () => new Set()
  )

  const [aligning, setAligning] = React.useState<boolean>(false);

  // Aggregate all primary sequences from session and pad to same length
  React.useEffect(() => {
    // Don't proceed if msa is already set
    if (msa !== null) return;

    const sequences: PrimarySequence[] = [];
    session.items.forEach(item => {
      item.primarySequences.forEach(ps => {
        if (ps.sequence.length > 0) {
          sequences.push({
            id: `${item.id}::${ps.id}`,
            name: `${item.name} (${ps.name})`,
            sequence: ps.sequence
          });
        }
      });
    })

    // Pad sequences to the same length with null motifs
    const maxLength = Math.max(...sequences.map(seq => seq.sequence.length), 0);
    const paddedSequences = sequences.map(seq => {
      const paddedSeq = { ...seq };
      const paddingNeeded = maxLength - seq.sequence.length;
      if (paddingNeeded > 0) {
        const paddingMotifs = Array.from({ length: paddingNeeded }, (_, i) => ({
          id: `pad-${seq.id}-${i}`,
          name: null,
          displayName: null,
          smiles: null,
        }));
        paddedSeq.sequence = [...seq.sequence, ...paddingMotifs];
      }
      return paddedSeq;
    });

    setMsa(paddedSequences);
  }, [session]);

  if (!msa) {
    return (
      <Typography variant="body2">
        No primary sequences available in session items to display MSA.
      </Typography>
    );
  }

  const visibleRows = msa.filter(row => !hiddenIds.has(row.id as string));

  const msaLength = msa[0]?.sequence.length || 0;
  const motifWidth = 50 * zoom;
  const labelWidth = 250;
  const totalWidth = labelWidth + msaLength * motifWidth;
  const colTemplate = `${labelWidth}px repeat(${msaLength}, ${motifWidth}px)`;

  const handleHideRow = (id: string) => {
    setHiddenIds(prev => {
      const next = new Set(prev);
      next.add(id);
      return next;
    });
    if (centerId == id) {
      setCenterId(null);
    } 
  }

  const handleResetHidden = () => {
    setHiddenIds(new Set());
  }

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

    setAligning(true);
    try {
      const result = await runMsa({
        primarySequences: currentVisible,
        centerId: centerId,
      });
      setMsa(result.alignedSequences);
      pushNotification("Alignment completed successfully.", "success");
    } catch (error) {
      pushNotification(`An error occurred during alignment: ${error}`, "error"); 
    } finally {
      setAligning(false);
      setHiddenIds(new Set()); // reset hidden rows after alignment; hidden rows are now excluded from alignment
    }
  }

  return (
    <Box sx={{ maxWidth: "100vw", overflowX: "hidden" }}>
      <Stack direction="column" spacing={2}>
        <Typography variant="body1">
          Click a row label to choose the center sequence.
          Hidden rows are excluded from alignment.
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
              {hiddenIds.size > 0 ? `Reset Hidden (${hiddenIds.size})` : "Reset Hidden"}
            </Button>
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
              <Box
                sx={{
                  display: "grid",
                  gridTemplateColumns: colTemplate,
                  width: `${totalWidth}px`,
                  gap: 1,
                }}
              >
                {visibleRows.map((row, rowIndex) => {
                  const isCenter = centerId === row.id;

                  return (
                    <React.Fragment key={row.id ?? rowIndex}>
                      {/* Row label */}
                        <Box
                          onClick={() => setCenterId(row.id as string)}
                          sx={{
                            m: 0,
                            p: 0,
                            height: 20,
                            fontWeight: 600,
                            textAlign: "left",
                            zIndex: 100,
                            cursor: "pointer",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            px: 1,
                            borderRadius: 1,
                            backgroundColor: isCenter
                              ? "warning.light"
                              : "background.paper",
                            border: isCenter
                              ? "1px solid"
                              : "1px solid transparent",
                            borderColor: isCenter
                              ? "warning.main"
                              : "transparent",
                          }}
                        >
                          <Tooltip
                            title={row.name || row.id}
                            placement="bottom"
                            arrow
                          >
                            <Typography
                              variant="body2"
                              sx={{
                                fontWeight: 600,
                                maxWidth: labelWidth - 40,
                                lineHeight: "20px",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                                zIndex: 101,
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
                                  fontSize: "0.7rem",
                                }}
                              />
                            )}
                            <VisibilityOffIcon 
                              fontSize="small"
                              onClick={e => {
                                e.stopPropagation();
                                handleHideRow(row.id as string);
                              }}
                            />
                          </Box>
                        </Box>

                      {/* Sequence motifs */}
                      {row.sequence.map((motif, colIndex) =>
                        !motif.id.startsWith("pad-") ? (
                          <Box
                            key={motif.id}
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
                                label={
                                  toDisplayName(
                                    motif.displayName ||
                                      motif.name ||
                                      null
                                  ) || "UNK"
                                }
                                size="small"
                                sx={{
                                  mt: "-4px",
                                  width: motifWidth,
                                  height: 20,
                                  textAlign: "center",
                                  backgroundColor: "background.paper",
                                  border: "1px solid",
                                  borderColor: "primary.main",
                                  zIndex: 100,
                                  fontSize: "0.75rem",
                                  transition:
                                    "background-color 0s ease-in-out",
                                }}
                              />
                            </Tooltip>
                          </Box>
                        ) : (
                          <Box
                            key={motif.id}
                            sx={{
                              m: 0,
                              width: motifWidth,
                              height: 20,
                              backgroundColor: "transparent",
                              display: "flex",
                              justifyContent: "center",
                              alignItems: "center",
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
                        )
                      )}

                      {/* Row line */}
                      <Box
                        sx={{
                          gridColumn: "2 / -1", // spans all columns except the first
                          borderBottom: "1px solid",
                          borderColor: "divider",
                          height: 0,
                          mt: "-19px",
                          ml: "-210px",
                          zIndex: 50,
                        }}
                      />
                    </React.Fragment>
                  );
                })}
              </Box>
            </Box>
          </Stack>
        ) : (
          <Typography variant="body2" sx={{ mt: 2 }}>
            All sequences are hidden. Reset hidden to show them again.
          </Typography>
        )}
      </Stack>
    </Box>
  );
}
