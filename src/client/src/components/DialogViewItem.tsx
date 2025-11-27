import React from "react";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import FormControl from "@mui/material/FormControl";
import Select from "@mui/material/Select";
import MenuItem from "@mui/material/MenuItem";
import { useNotifications } from "./NotificationProvider";
import { DialogWindow } from "../components/DialogWindow";
import { SessionItem } from "../features/session/types";
import { SvgViewer } from "../components/SvgViewer";
import { drawCompoundItem, drawGeneClusterItem } from "../features/drawing/api";

type DialogViewItemProps = {
  open: boolean;
  item?: SessionItem | null;
  onClose: () => void;
}

export const DialogViewItem: React.FC<DialogViewItemProps> = ({
  open,
  item,
  onClose,
}) => {
  const { pushNotification } = useNotifications();

  const [initializedItemId, setInitializedItemId] = React.useState<string | null>(null);
  const [selectPrimarySequenceId, setSelectPrimarySequenceId] = React.useState<string>("");
  const [svg, setSvg] = React.useState<string | null>(null);

  const generateSvg = React.useCallback(async (primarySequenceId: string) => {
    if (!item) {
      setSvg(null);
      return;
    }

    // Get Item primarySequence for primarySequenceId
    const primarySequence = item.primarySequences?.find(seq => seq.id === primarySequenceId);
    if (!primarySequence) {
      pushNotification("Selected primary sequence not found in item.", "error");
      setSvg(null);
      return;
    }

    try {
      if (item.kind === "compound") {
        const taggedParentSmiles = item.taggedSmiles;

        // Check if taggedParentSmiles is available
        if (!taggedParentSmiles) {
          pushNotification("No tagged SMILES available for this compound item.", "error");
          setSvg(null);
          return;
        }
         
        // Call drawing API
        const drawingSvg = await drawCompoundItem(
          taggedParentSmiles,
          primarySequence
        );
        setSvg(drawingSvg);
      } else if (item.kind === "gene_cluster") {
        // Call drawing API
        const drawingSvg = await drawGeneClusterItem();
        setSvg(drawingSvg);
      } else {
        pushNotification("SVG drawing not supported for this item type.", "error");
        setSvg(null);
        return;
      }
    } catch (error) {
      pushNotification("Error generating SVG drawing.", "error");
      setSvg(null);
    }
  }, [item]);

  const initializePrimarySequence = React.useCallback(() => {
    if (item && item.primarySequences && item.primarySequences.length > 0) {
      const firstSeqId = item.primarySequences[0].id;
      setSelectPrimarySequenceId(firstSeqId);
      generateSvg(firstSeqId);
    } else {
      setSelectPrimarySequenceId("");
      setSvg(null);
    }
  }, [item, generateSvg]);

  // Initialize primary sequence selection when item changes
  // Also avoid re-initializing if the same item is passed again
  React.useEffect(() => {
    if (!item) {
      setInitializedItemId(null);
      setSelectPrimarySequenceId("");
      setSvg(null);
      return;
    }

    // No redraw if same item
    if (initializedItemId === item.id) {
      return;
    }

    // New item is passed
    setInitializedItemId(item.id);
    initializePrimarySequence();
  }, [item, initializedItemId, initializePrimarySequence]);

  const handlePrimarySequenceChange = (sequenceId: string) => {
    setSelectPrimarySequenceId(sequenceId);
    generateSvg(sequenceId);
  }

  return (
    <DialogWindow
      open={open}
      onClose={onClose}
      title="View item"
      dividers
      maxWidth="xl"
      actions={[
        { label: "Cancel", variant: "text", color: "inherit", onClick: onClose },
      ]}
    >
      { !item ? (
        <Typography variant="body1">
          No item selected.
        </Typography>
      ) : svg === null || svg.length === 0 ? (
        <Typography variant="body1">
          No SVG drawing available for this item.
        </Typography>
      ) : item.kind === "compound" ? (
        <Stack direction="column" gap={1} alignItems="flex-start">
          <Typography variant="body1">
            To get started, select a primary sequence to map onto the input compound structure.
            A downloadable SVG will be generated showing the mapping below the selector upon successful mapping.
          </Typography>
          <FormControl fullWidth size="small">
            <Select
              label="Primary sequence"
              value={selectPrimarySequenceId}
              onChange={(e) => handlePrimarySequenceChange(e.target.value)}
              disabled={!item.primarySequences || item.primarySequences.length === 0}
            >
              {item.primarySequences && item.primarySequences.map((seq) => (
                <MenuItem key={seq.id} value={seq.id}>
                  {seq.name || seq.id}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          {svg && (
            <SvgViewer
              svg={svg}
              onZoomChange={() => {}}
              onElementClick={() => {}}
              height={600}
            />
          )}
        </Stack>
      ) : item.kind === "gene_cluster" ? (
        <Stack direction="column" spacing={2} alignItems="center">
          {svg && (
            <SvgViewer
              svg={svg}
              onZoomChange={() => {}}
              onElementClick={() => {}}
              height={600}
            />
          )}
        </Stack>
      ) : (
        <Typography variant="body1">
          No preview available for this item type.
        </Typography>
      )}

    </DialogWindow>
  )
}
