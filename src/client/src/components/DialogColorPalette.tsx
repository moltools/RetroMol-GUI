import React from "react";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import TextField from "@mui/material/TextField";
import DeleteIcon from "@mui/icons-material/Delete";
import { DialogWindow } from "../components/DialogWindow";
import { defaultMotifColorMap } from "../features/session/utils";

type DialogColorPaletteProps = {
  open: boolean;
  onClose: () => void;
  colorMap: Record<string, string>;
  onSave: (newColorMap: Record<string, string>) => void;
}

export const DialogColorPalette: React.FC<DialogColorPaletteProps> = ({
  open,
  onClose,
  colorMap,
  onSave,
}) => {
  type PaletteEntry = { id: string; key: string; color: string };

  const createEntryId = React.useCallback(() => {
    if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
      return (crypto as any).randomUUID() as string;
    }
    return `tmp-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }, []);

  const mapToEntries = React.useCallback(
    (map: Record<string, string>): PaletteEntry[] =>
      Object.entries(map).map(([key, color]) => ({
        id: key, // stable id when syncing from saved map
        key,
        color,
      })),
    []
  );

  const [localEntries, setLocalEntries] = React.useState<PaletteEntry[]>(mapToEntries(colorMap));
  const [dirty, setDirty] = React.useState(false);

  // Sync local state with remote session updates when not actively editing
  React.useEffect(() => {
    // If dialog is closed, always sync to the latest saved palette
    if (!open) {
      setLocalEntries(mapToEntries(colorMap));
      setDirty(false);
      return;
    }

    // When open but not dirty, accept incoming updates (e.g., from polling)
    if (!dirty) {
      setLocalEntries(mapToEntries(colorMap));
    }
  }, [colorMap, open, dirty, mapToEntries]);

  // Whenever the dialog opens, start from the latest saved palette
  React.useEffect(() => {
    if (open) {
      setLocalEntries(mapToEntries(colorMap));
      setDirty(false);
    }
  }, [open, mapToEntries]);

  // Handle change of key; duplicate keys are not allowed
  const handleKeyChange = (entryId: string, newKey: string) => {
    const entry = localEntries.find((e) => e.id === entryId);
    if (!entry) return;
    if (newKey === entry.key) return;
    if (localEntries.some((e) => e.key === newKey)) {
      // Duplicate key; ignore change
      return;
    }

    const updated = localEntries.map((e) =>
      e.id === entryId ? { ...e, key: newKey } : e
    );
    setLocalEntries(updated);
    setDirty(true);
  }

  const handleColorChange = (entryId: string, newColor: string) => {
    let changed = false;
    const updated = localEntries.map((entry) => {
      if (entry.id !== entryId) return entry;
      if (entry.color === newColor) return entry;
      changed = true;
      return { ...entry, color: newColor };
    });
    if (!changed) return;
    setLocalEntries(updated);
    setDirty(true);
  }

  // Add entry to top of the list with default values
  const handleAddEntry = () => {
    let newKey = "NewMotif";
    let counter = 1;
    const existingKeys = new Set(localEntries.map((e) => e.key));
    while (existingKeys.has(newKey)) {
      newKey = `NewMotif${counter}`;
      counter += 1;
    }
    const newEntries = [{ id: createEntryId(), key: newKey, color: "#FFFFFF" }, ...localEntries];
    setLocalEntries(newEntries);
    setDirty(true);
  }

  const handleRemoveEntry = (entryId: string) => {
    const filtered = localEntries.filter((entry) => entry.id !== entryId);
    setLocalEntries(filtered);
    setDirty(true);
  }

  const handleCancel = () => {
    setLocalEntries(mapToEntries(colorMap)); // discard unsaved edits
    setDirty(false);
    onClose();
  }

  const handleSave = () => {
    const nextMap = localEntries.reduce<Record<string, string>>((acc, entry) => {
      acc[entry.key] = entry.color;
      return acc;
    }, {});

    onSave(nextMap);
    setDirty(false);
    onClose();
  }

  const title = (
    <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
      Color palette
      {dirty && (
        <Chip
          label="Unsaved changes"
          size="small"
          color="warning"
          variant="outlined"
          sx={{ height: 20, fontSize: "0.7rem" }}
        />
      )}
    </Box>
  );

  return (
    <DialogWindow
      open={open}
      title={title}
      onClose={handleCancel}
      dividers
      actions={[
        { label: "Cancel", variant: "text", color: "inherit", onClick: handleCancel },
        { label: "Save", variant: "contained", color: "primary", onClick: handleSave },
      ]}
    >
      <Stack direction="row" gap={1} sx={{ mb: 2 }}>
        <Button
          variant="outlined"
          color="primary"
          onClick={handleAddEntry}
        >
          Add entry
        </Button>
        <Button
          variant="outlined"
          color="primary"
          onClick={() => {
            setLocalEntries(mapToEntries(colorMap));
            setDirty(false);
          }}
        >
          Reset to saved
        </Button>
        <Button
          variant="outlined"
          color="primary"
          onClick={() => {
            setLocalEntries(mapToEntries(defaultMotifColorMap()));
            setDirty(true);
          }}
        >
          Reset to default
        </Button>
        <Button
          variant="outlined"
          color="primary"
          onClick={() => {
            setLocalEntries([]);
            setDirty(true);
          }}
        >
          Clear all
        </Button>
      </Stack>
      <Stack direction="column" sx={{ maxHeight: 400, overflowY: "auto", mb: 2 }}>
        {localEntries.map(({ id, key, color }) => (
          <Stack
            key={id}
            direction="row"
            sx={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              gap: 1,
              mb: 1,
            }}
          >
            <TextField
              value={key}
              onChange={(e) => handleKeyChange(id, e.target.value)}
            />
            <TextField
              type="text"
              value={color}
              onChange={(e) => handleColorChange(id, e.target.value)}
              inputProps={{ maxLength: 7, placeholder: "#RRGGBB" }}
            />
            <Box
              sx={{
                width: 24,
                height: 24,
                bgcolor: color,
                border: "1px solid #ccc",
                borderRadius: "4px",
                mr: 2,
              }}
          />
            <DeleteIcon
              sx={{ cursor: "pointer" }}
              onClick={() => handleRemoveEntry(id)}
            />
          </Stack>
        ))}
      </Stack>
    </DialogWindow>
  )
}
