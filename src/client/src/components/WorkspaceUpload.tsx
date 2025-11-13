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
import { DialogWindow } from "../components/DialogWindow";

export const WorkspaceUpload: React.FC = () => {
  const theme = useTheme();
  const { pushNotification } = useNotifications();

  const [openCompounds, setOpenCompounds] = React.useState(false);
  const [openGeneClusters, setOpenGeneClusters] = React.useState(false);

  // Actions and handlers for compounds
  const [compoundMode, setCompoundMode] = React.useState<"single" | "batch">("single");
  const [compoundText, setCompoundText] = React.useState<string>("");
  const [compoundFile, setCompoundFile] = React.useState<File | null>(null);
  const canImportCompounds =
    (compoundMode === "single" && compoundText.trim().length > 0) ||
    (compoundMode === "batch" && !!compoundFile);

  const resetCompounds = () => {
    setCompoundMode("single");
    setCompoundText("");
    setCompoundFile(null);
  }

  const importCompounds = () => {
    if (compoundMode === "single") {
      pushNotification("Importing single compound not yet implemented", "warning");
    } else if (compoundFile) {
      pushNotification("Importing compounds from file not yet implemented", "warning");
    }
    resetCompounds();
    setOpenCompounds(false);
  }

  // Actions and handlers for gene clusters
  const [gbkFiles, setGbkFiles] = React.useState<File[]>([]);
  const canImportGBK = gbkFiles.length > 0;
  const resetGBK = () => setGbkFiles([]);
  const importGBK = () => {
    pushNotification("Importing gene clusters from GBK files not yet implemented", "warning");
    resetGBK();
    setOpenGeneClusters(false);
  }

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
            .
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

      <DialogWindow
        open={openCompounds}
        onClose={() => setOpenCompounds(false)}
        title="Import compounds"
        dividers
        maxWidth="sm"
        actions={[
          { label: "Cancel", variant: "text", color: "inherit", onClick: () => setOpenCompounds(false) },
          { label: "Clear", variant: "outlined", color: "secondary", onClick: resetCompounds },
          { label: "Import", variant: "contained", color: "primary", onClick: importCompounds, disabled: !canImportCompounds, autoFocus: true },
        ]}
      >

      <Stack spacing={2}>
        <Stack direction="row" spacing={1}>
          <Button variant={compoundMode === "single" ? "contained" : "outlined"} onClick={() => setCompoundMode("single")}>
            Single
          </Button>
          <Button variant={compoundMode === "batch" ? "contained" : "outlined"} onClick={() => setCompoundMode("batch")}>
            Batch
          </Button>
        </Stack>

        {compoundMode === "single" ? (
          <textarea
            style={{ width: "100%", minHeight: 80 }}
            placeholder="Paste SMILES / InChI / name"
            value={compoundText}
            onChange={(e) => setCompoundText(e.target.value)}
          />
        ) : (
          <Stack direction={{ xs: "column", sm: "row" }} spacing={2} alignItems="center">
            <Button variant="outlined" component="label">
              Choose file
              <input
                type="file"
                hidden
                accept=".csv,.tsv,text/csv,text/tab-separated-values,text/plain"
                onChange={(e) => setCompoundFile(e.target.files?.[0] || null)}
              />
            </Button>
          </Stack>
        )}
        </Stack>  
      </DialogWindow>

      <DialogWindow
        open={openGeneClusters}
        onClose={() => setOpenGeneClusters(false)}
        title="Import gene clusters"
        dividers
        maxWidth="sm"
        actions={[
          { label: "Cancel", variant: "text", color: "inherit", onClick: () => setOpenGeneClusters(false) },
          { label: "Clear", variant: "outlined", color: "secondary", onClick: resetGBK },
          { label: "Import", variant: "contained", color: "primary", onClick: importGBK, disabled: !canImportGBK, autoFocus: true },
        ]}
      >
        <Stack spacing={2}>
          <Typography variant="body2" color="text.secondary">
            Select one or more GenBank files (.gbk, .gb, .genbank)
          </Typography>
          <Button variant="outlined" component="label">
            Choose files
            <input
              type="file"
              hidden
              multiple
              accept=".gb,.gbk,.genbank,application/genbank"
              onChange={(e) => setGbkFiles(Array.from(e.target.files || []))}
            />
          </Button>
          {gbkFiles.length > 0 && (
            <Typography variant="body2">
              {gbkFiles.length} file(s) selected
            </Typography>
          )}
        </Stack>
      </DialogWindow>
    </Box>
  )
}
