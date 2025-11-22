import React from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import MuiLink from "@mui/material/Link";
import Stack from "@mui/material/Stack";
import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";
import Typography from "@mui/material/Typography";
import NotificationsRoundedIcon from "@mui/icons-material/NotificationsRounded";
import { useTheme } from "@mui/material/styles";
import { Link as RouterLink } from "react-router-dom";
import { Session } from "../features/session/types";
import { ViewEmbeddingSpace } from "./ViewEmbeddingSpace";
import { ViewMsa } from "./ViewMsa";

type WorkspaceExploreProps = {
  session: Session;
  setSession: (updated: (prev: Session) => Session) => void;
}

type ExploreView = "msa" | "embedding";

export const WorkspaceExplore: React.FC<WorkspaceExploreProps> = ({ session, setSession }) => {
  const theme = useTheme();
  const [view, setView] = React.useState<ExploreView>("msa");
  // Helper to switch views
  const handleViewChange = (_event: React.SyntheticEvent, newValue: ExploreView) => {
    setView(newValue);
  }

  return (
    <Box 
      sx={{ 
          width: "100%",
          mx: "auto", 
          display: "flex", 
          flexDirection: "column", 
          gap: "16px",
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
            Items from the&nbsp;
            <MuiLink
              component={RouterLink}
              to="/dashboard/upload"
              underline="hover"
              color={(theme.vars || theme).palette.primary.main}
              sx={{ fontWeight: "500" }}
            >
              Upload tab
            </MuiLink>&nbsp;
            marked as <b>Ready</b> can used here for analysis. Biosynthetic fingerprints parsed from your imports can be
            visualized in a reduced dimensional space and individual clusters can be enriched for annotations. You can
            enrich your data further by querying any item against the BioNexus database in the&nbsp;
            <MuiLink
              component={RouterLink}
              to="/dashboard/query"
              underline="hover"
              color={(theme.vars || theme).palette.primary.main}
              sx={{ fontWeight: "500" }}
            >
              Query tab
            </MuiLink>&nbsp;and importing additional hits into your workspace. Keep an eye on&nbsp;
            <NotificationsRoundedIcon fontSize={"small"} sx={{ verticalAlign: "middle" }} /> for updates on your
            imports.
          </Typography>
        </CardContent>
      </Card>
      
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
          <Stack>
            <Typography component="h1" variant="subtitle1">
              Explore imports
            </Typography>
            <Typography variant="body1">
              Visualize multiple sequence alignments and embedding spaces of biosynthetic fingerprints for items in your
              workspace. You can switch between the different views using the tabs below.
            </Typography>
          </Stack>

          <Tabs
            value={view}
            onChange={handleViewChange}
            textColor="primary"
            indicatorColor="primary"
            sx={{ mt: 2, mb: 1 }}
          >
            <Tab
              label="Multiple sequence alignment"
              value="msa"
              sx={{ textTransform: "none", fontWeight: view === "msa" ? 600 : 400 }}
            />
            <Tab
              label="Embedding space"
              value="embedding"
              sx={{ textTransform: "none", fontWeight: view === "embedding" ? 600 : 400 }}
            />
          </Tabs>

          {view === "embedding" && (
            <ViewEmbeddingSpace session={session} setSession={setSession} />
          )}
          {view === "msa" && (
            <ViewMsa session={session} setSession={setSession} />
          )}
        </CardContent>
      </Card>
    </Box>
  )
}
