import React from "react";
import Box from "@mui/material/Box";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import { DialogWindow } from "../components/DialogWindow";
import { QuerySettings } from "../features/views/types";

type DialogQuerySettingsProps = {
  open: boolean;
  onClose: () => void;
  settings: QuerySettings,
  handleSettingsChange: (newSettings: QuerySettings) => void;
}

export const DialogQuerySettings: React.FC<DialogQuerySettingsProps> = ({
  open,
  onClose,
  settings,
  handleSettingsChange,
}) => {
  // Handle settings changes
  const handleScoreThresholdChange = (key: keyof QuerySettings) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = Number(e.target.value);
    if (Number.isFinite(value)) {
      handleSettingsChange({
        ...settings,
        [key]: value,
      });
    }
  }

  return (
    <DialogWindow
      open={open}
      onClose={onClose}
      title="Query settings"
      dividers
      maxWidth="sm"
      actions={[
        { label: "Close", variant: "text", color: "inherit", onClick: onClose },
      ]}
    >
      <Box display="flex" flexDirection="column" gap={2} py={1}>
        <Typography variant="body1">
          Set the similarity threshold for nearest neighbor retrieval. 
          Items passing the similarity threshold will be considered the in-group for the enrichment analysis as well.
          All items not passing the threshold will be considered the background.
        </Typography>
        <TextField
          type="number"
          value={settings.scoreThreshold}
          onChange={handleScoreThresholdChange("scoreThreshold")}
          inputProps={{
            step: 0.01,
            min: 0,
            max: 1,
          }}
          helperText="Value between 0 and 1"
          fullWidth
          // Change input label background
          sx={{
            "& .MuiInputLabel-root": {
              backgroundColor: "background.paper",
            }
          }}
        />
      </Box>
    </DialogWindow>
  )
}
