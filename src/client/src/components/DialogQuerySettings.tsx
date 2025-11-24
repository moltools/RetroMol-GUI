import React from "react";
import Box from "@mui/material/Box";
import FormControl from "@mui/material/FormControl";
import FormControlLabel from "@mui/material/FormControlLabel";
import Radio from "@mui/material/Radio";
import RadioGroup from "@mui/material/RadioGroup";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { DialogWindow } from "../components/DialogWindow";
import { QuerySearchSpace, QuerySettings } from "../features/session/types";

type DialogQuerySettingsProps = {
  open: boolean;
  onClose: () => void;
  settings: QuerySettings;
  onSave: (newSettings: QuerySettings) => void;
}

export const DialogQuerySettings: React.FC<DialogQuerySettingsProps> = ({
  open,
  onClose,
  settings,
  onSave,
}) => {
  const [localSettings, setLocalSettings] = React.useState<QuerySettings>(settings);
  const [dirty, setDirty] = React.useState(false);

  React.useEffect(() => {
    setLocalSettings(settings);
  }, [settings])

  const handleSave = () => {
    onSave(localSettings);
    onClose();
  }

  const handleSearchSpaceChange = (value: QuerySearchSpace) => {
    setLocalSettings((prev) => ({
      ...prev,
      searchSpace: value,
    }));
    setDirty(true);
  }

  return (
    <DialogWindow
      open={open}
      onClose={onClose}
      title="Query settings"
      dirty={dirty}
      dividers
      actions={[
        { label: "Cancel", variant: "text", color: "inherit", onClick: onClose },
        { label: "Save", variant: "contained", color: "primary", onClick: handleSave },
      ]}
    >
      <Box display="flex" flexDirection="column" gap={2}>
        <Stack direction="column" spacing={1}>
          <Typography component="h1" variant="subtitle1">
            Search space
          </Typography>
          <Typography variant="body1">
            Choose whether to search against both compounds and biosynthetic gene clusters (BGCs), or limit the search to only one of these categories.
            Search space impacts both the results returned and the enrichment calculations. Some annotations are only available for one type of item and
            will appear as significant only when that item type is included in the search space (e.g., chemical classes for compounds).
          </Typography>
          <FormControl component="fieldset" disabled>
            <RadioGroup
              value={localSettings.searchSpace ?? "both"}
              onChange={(e) => handleSearchSpaceChange(e.target.value as QuerySearchSpace)}
            >
              <FormControlLabel value="both" control={<Radio />} label="Full (compounds & BGCs)" />
              <FormControlLabel value="only_compounds" control={<Radio />} label="Compounds only" />
              <FormControlLabel value="only_gene_clusters" control={<Radio />} label="BGCs only" />
            </RadioGroup>
          </FormControl>
        </Stack>
      </Box>
    </DialogWindow>
  )
}
