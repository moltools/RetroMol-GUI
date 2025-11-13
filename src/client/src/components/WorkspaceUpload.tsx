import React from "react";
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import MuiLink from "@mui/material/Link";
import { useTheme } from "@mui/material/styles";
import { useNotifications } from "../components/NotificationProvider";
import { Link as RouterLink } from "react-router-dom";
import { DialogImportCompound } from "./DialogImportCompound";
import { DialogImportGeneCluster } from "./DialogImportGeneCluster";
import { WorkspaceItemCard } from "./WorkspaceItemCard";
import { Session, SessionItem } from "../features/session/types";

const MAX_ITEMS = 100;

type WorkspaceUploadProps = {
  session: Session;
  setSession: (session: Session) => void;
}

export const WorkspaceUpload: React.FC<WorkspaceUploadProps> = ({ session, setSession }) => {
  const theme = useTheme();
  const { pushNotification } = useNotifications();

  const [openCompounds, setOpenCompounds] = React.useState(false);
  const [openGeneClusters, setOpenGeneClusters] = React.useState(false);

  const [selectedIds, setSelectedIds] = React.useState<Set<string>>(new Set());
  const currentItemCount = session.items?.length ?? 0;

  // Helper to add items while respecting MAX_ITEMS limit
  const appendItems = (newItems: SessionItem[]) => {
    const existing = session.items || [];
    const total = existing.length + newItems.length;
    if (total > MAX_ITEMS) {
      pushNotification(`Cannot add items. Importing these items would exceed the maximum limit of ${MAX_ITEMS}. Current count: ${existing.length}`, "error");
      return;
    }

    setSession({ ...session, items: [...existing, ...newItems] });
  }

  // Selection helpers
  const toggleSelectItem = (id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    })
  }

  const handleDeleteItem = (id: string) => {
    const remaining = session.items.filter(item => item.id !== id);
    setSession({ ...session, items: remaining });
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }

  const handleSelectAll = () => {
    if (!session.items.length) return;
    setSelectedIds(new Set(session.items.map(item => item.id)));
  }

  const handleClearSelection = () => {
    setSelectedIds(new Set());
  }

  const handleDeleteSelected = () => {
    if (selectedIds.size === 0) return;
    const toDelete = new Set(selectedIds);
    const remaining = session.items.filter(item => !toDelete.has(item.id));
    setSession({ ...session, items: remaining });
    setSelectedIds(new Set());
  }

  // Actions and handlers for compounds
  const handleImportSingleCompound = ({ name, smiles }: { name: string; smiles: string }) => {
    const item: SessionItem = {
      id: crypto.randomUUID(),
      kind: "compound",
      name,
      smiles,
    };
    appendItems([item]);
  }

  const handleImportBatchCompounds = (file: File) => {
    pushNotification("Importing batch compounds not yet implemented", "warning");
  }

  // Actions and handlers for gene clusters
  const handleImportGeneClusters = (files: File[]) => {
    if (!files.length) return;

    const newItems: SessionItem[] = files.map((file) => ({
      id: crypto.randomUUID(),
      kind: "gene_cluster",
      fileName: file.name,
    }));

    appendItems(newItems);
  }

  // Selection states
  const anySelected = selectedIds.size > 0;
  const allSelected = session.items.length > 0 && selectedIds.size === session.items.length;

  return (
    <Box 
      sx={{ 
          width: "100%", 
          mx: "auto", 
          display: "flex", 
          flexDirection: "column", 
          gap: "16px" 
      }}
    >
      <Card
        variant="outlined"
        sx={{
          display: "flex",
          flexDirection: "column",
          gap: "8px",
          flexGrow: 1,
        }}
      >
        <CardContent>
          <Typography component="h1" variant="subtitle1">
            Getting started
          </Typography>
          <Typography variant="body1">
            To get started, you can import compounds and gene clusters into your workspace. Use the buttons below to upload your data files. After importing, you can visualize and analyze your data within the&nbsp;
            <MuiLink
              component={RouterLink}
              to="/dashboard/explore"
              underline="hover"
              color={(theme.vars || theme).palette.primary.main}
              sx={{ fontWeight: "500" }}
            >
              Explore tab
            </MuiLink>
            . A maximum of <b>100 items</b> can be imported into the workspace.
          </Typography>

          <Stack direction="row" spacing={2} sx={{ mt: 2 }}>
            <Button variant="contained" onClick={() => setOpenCompounds(true)}>
              Import compounds
            </Button>
            <Button variant="contained" onClick={() => setOpenGeneClusters(true)}>
              Import gene clusters
            </Button>
          </Stack>
        </CardContent>
      </Card>

      <DialogImportCompound
        open={openCompounds}
        onClose={() => setOpenCompounds(false)}
        onImportSingle={handleImportSingleCompound}
        onImportBatch={handleImportBatchCompounds}
      />

      <DialogImportGeneCluster
        open={openGeneClusters}
        onClose={() => setOpenGeneClusters(false)}
        onImport={handleImportGeneClusters}
      />

      {session.items.length > 0 && (
        <Card variant="outlined">
          <CardContent>
            <Stack
              direction="row"
              alignItems="center"
              justifyContent="space-between"
              sx={{ mb: 1.5 }}
            >
              <Typography component="h1" variant="subtitle1">
                Workspace items ({session.items.length}/{MAX_ITEMS})
              </Typography>
              <Stack direction="row" spacing={1}>
                <Button
                  size="small"
                  variant="text"
                  onClick={handleSelectAll}
                  disabled={session.items.length === 0 || allSelected}
                >
                  Select all
                </Button>
                <Button
                  size="small"
                  variant="text"
                  onClick={handleClearSelection}
                  disabled={!anySelected}
                >
                  Clear selection
                </Button>
                <Button
                  size="small"
                  variant="text"
                  color="error"
                  onClick={handleDeleteSelected}
                  disabled={!anySelected}
                >
                  Delete selected
                </Button>
              </Stack>
            </Stack>

            <Stack spacing={1}>
              {session.items.map((item) => (
                <WorkspaceItemCard
                  key={item.id}
                  item={item}
                  selected={selectedIds.has(item.id)}
                  onToggleSelect={toggleSelectItem}
                  onDelete={handleDeleteItem}
                />
              ))}
            </Stack>
          </CardContent>
        </Card>
      )}

    </Box>
  )
}
