import React from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import MuiLink from "@mui/material/Link";
import Typography from "@mui/material/Typography";
import NotificationsRoundedIcon from '@mui/icons-material/NotificationsRounded';
import { useTheme } from "@mui/material/styles";
import { Link as RouterLink } from "react-router-dom";
import { Session } from "../features/session/types";

type WorkspaceExploreProps = {
  session: Session;
  // Updated to functional form to avoid stale closures
  setSession: (updated: (prev: Session) => Session) => void;
}

export const WorkspaceExplore: React.FC<WorkspaceExploreProps> = ({ session, setSession }) => {
  const theme = useTheme();

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
            Items from the&nbsp;
            <MuiLink
              component={RouterLink}
              to="/dashboard/explore"
              underline="hover"
              color={(theme.vars || theme).palette.primary.main}
              sx={{ fontWeight: "500" }}
            >
              Upload tab
            </MuiLink>&nbsp;
            marked as <b>Ready</b> can used here for analysis. Biosynthetic fingerprints parsed from your imports can be visualized in a reduced dimensional space and individual clusters can be enriched for annotations. Keep an eye on <NotificationsRoundedIcon fontSize={'small'} sx={{ verticalAlign: 'middle' }} /> for updates on your queries.
          </Typography>
        </CardContent>
      </Card>
      <Card variant="outlined">
        <CardContent>
          <Typography component="h2" variant="subtitle1">
            Not yet implemented
          </Typography>
        </CardContent>
      </Card>
    </Box>
  )
}
