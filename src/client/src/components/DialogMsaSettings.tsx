import React from "react";
import Box from "@mui/material/Box";
import FormControl from "@mui/material/FormControl";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import Select, { SelectChangeEvent } from "@mui/material/Select";
import MenuItem from "@mui/material/MenuItem";
import { DialogWindow } from "../components/DialogWindow";
import { MsaSettings, AlignmentType } from "../features/session/types";

type DialogMsaSettingsProps = {
  open: boolean;
  onClose: () => void;
  settings: MsaSettings;
  onSave: (newSettings: MsaSettings) => void;
}

export const DialogMsaSettings: React.FC<DialogMsaSettingsProps> = ({
  open,
  onClose,
  settings,
  onSave,
}) => {
  const [localSettings, setLocalSettings] = React.useState<MsaSettings>(settings);
  const [dirty, setDirty] = React.useState(false);

  // Sync local state with remote session updates when not actively editing
  React.useEffect(() => {
    // If dialog is closed, always sync to the latest saved settings
    if (!open) {
      setLocalSettings(settings);
      setDirty(false);
      return;
    }

    // When open but not dirty, accept incoming updates (e.g., from polling)
    if (!dirty) {
      setLocalSettings(settings);
    }
  }, [settings, open, dirty])

  // Whenever the dialog opens, start from the latest saved settings
  React.useEffect(() => {
    if (open) {
      setLocalSettings(settings);
      setDirty(false);
    }
  }, [open, settings])

  // Handle alignment type change
  const handleAlignmentTypeChange = (event: SelectChangeEvent<AlignmentType>) => {
    const newType = event.target.value as AlignmentType;
    setLocalSettings((prev) => ({
      ...prev,
      alignmentType: newType,
    }));
    setDirty(true);
  }

  const handleCancel = () => {
    setLocalSettings(settings);
    setDirty(false);
    onClose();
  }

  const handleSave = () => {
    onSave(localSettings);
    setDirty(false);
    onClose();
  }

  return (
    <DialogWindow
      open={open}
      onClose={handleCancel}
      title="Query settings"
      dirty={dirty}
      dividers
      actions={[
        { label: "Cancel", variant: "text", color: "inherit", onClick: handleCancel },
        { label: "Save", variant: "contained", color: "primary", onClick: handleSave, disabled: !dirty },
      ]}
    >
      <Box display="flex" flexDirection="column" gap={1}>
        <Stack direction="column" spacing={1}>
          <Typography component="h1" variant="subtitle1">
            Alignment type
          </Typography>
          <Typography variant="body1">
            Choose between global (Needleman-Wunsch) and local (Smith-Waterman) alignment algorithms.
          </Typography>
          <FormControl fullWidth>
            <Select
              labelId="alignment-type-label"
              id="alignment-type"
              value={localSettings.alignmentType}
              label="Alignment type"
              onChange={handleAlignmentTypeChange}
              disabled
            >
              <MenuItem value="global">Global</MenuItem>
              <MenuItem value="local">Local</MenuItem>
            </Select>
          </FormControl>
        </Stack>
      </Box>
    </DialogWindow>
  )
}
