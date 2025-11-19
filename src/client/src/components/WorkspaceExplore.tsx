import React from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Grid from "@mui/material/Grid";
import MuiLink from "@mui/material/Link";
import Typography from "@mui/material/Typography";
import Tabs from "@mui/material/Tabs";
import Tab from "@mui/material/Tab";
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

type ExploreView = "embedding" | "msa";

export const WorkspaceExplore: React.FC<WorkspaceExploreProps> = ({ session, setSession }) => {
  const theme = useTheme();
  const [view, setView] = React.useState<ExploreView>("embedding");
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
      <Grid container spacing={2} columns={12} alignItems="stretch" sx={{ mb: (theme) => theme.spacing(2) }}>
        <Grid size={{ xs: 12, md: 6 }} sx={{ display: "flex" }}>
          <Card
            variant="outlined"
            sx={{
              display: "flex",
              flexDirection: "column",
              flexGrow: 1,
            }}
          >
            <CardContent sx={{ pt: 1.5 }}>
              <Tabs
                value={view}
                onChange={handleViewChange}
                aria-label="Explore views"
                sx={{
                  borderBottom: 1,
                  borderColor: "divider",
                  mb: 2,
                  minHeight: 0,
                  "& .MuiTab-root": {
                    minHeight: 0,
                    textTransform: "none",
                    fontSize: 14,
                  },
                }}
              >
                <Tab
                  label="Embedding space"
                  value="embedding"
                  id="explore-tab-embedding"
                  aria-controls="explore-tabpanel-embedding"
                />
                <Tab
                  label="MSA"
                  value="msa"
                  id="explore-tab-msa"
                  aria-controls="explore-tabpanel-msa"
                />
              </Tabs>

              <Box>
                <Box
                  role="tabpanel"
                  id="explore-tabpanel-embedding"
                  aria-labelledby="explore-tab-embedding"
                  sx={{ display: view === "embedding" ? "block" : "none" }}
                >
                  <ViewEmbeddingSpace session={session} setSession={setSession} />
                </Box>
              </Box>
              <Box>
                <Box
                  role="tabpanel"
                  id="explore-tabpanel-msa"
                  aria-labelledby="explore-tab-msa"
                  sx={{ display: view === "msa" ? "block" : "none" }}
                >
                  <ViewMsa session={session} setSession={setSession} />
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, md: 6 }} sx={{ display: "flex" }}>
          <Card variant="outlined" sx={{ display: "flex", "flexDirection": "column", flex: 1 }}>
            <CardContent>
              {/* */}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  )
}
