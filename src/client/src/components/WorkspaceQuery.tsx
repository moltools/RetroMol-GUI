import React from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Grid from "@mui/material/Grid";
import MuiLink from "@mui/material/Link";
import Typography from "@mui/material/Typography";
import NotificationsRoundedIcon from "@mui/icons-material/NotificationsRounded";
import { useTheme } from "@mui/material/styles";
import { Link as RouterLink } from "react-router-dom";
import { useNotifications } from "../components/NotificationProvider";
import { Session } from "../features/session/types";
import { runQuery } from "../features/query/api";
import type { QueryResult } from "../features/query/types";

interface WorkspaceQueryProps {
  session: Session;
  setSession: (updated: (prev: Session) => Session) => void;
}

export const WorkspaceQuery: React.FC<WorkspaceQueryProps> = ({ session, setSession }) => {
  const theme = useTheme();
  const { pushNotification } = useNotifications();

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
            Pick one of your imported items from the&nbsp;
            <MuiLink
              component={RouterLink}
              to="/dashboard/upload"
              underline="hover"
              color={(theme.vars || theme).palette.primary.main}
              sx={{ fontWeight: "500" }}
            >
              Upload tab
            </MuiLink>
            &nbsp;and query it against the BioNexus database for compounds and biosynthetic gene clusters. You can
            insert query hits into your workspace for further analysis in the&nbsp;
            <MuiLink
              component={RouterLink}
              to="/dashboard/explore"
              underline="hover"
              color={(theme.vars || theme).palette.primary.main}
              sx={{ fontWeight: "500" }}
            >
              Explore tab
            </MuiLink>. Keep an eye on <NotificationsRoundedIcon fontSize={"small"} sx={{ verticalAlign: "middle" }} />
            for updates on your queries.
          </Typography>
        </CardContent>
      </Card>
      <Grid container spacing={2} columns={12} alignItems="stretch" sx={{ mb: (theme) => theme.spacing(2) }}>
        <Grid size={{ xs: 12, md: 6 }} sx={{ display: "flex" }}>
          <Card variant="outlined" sx={{ display: "flex", "flexDirection": "column", flex: 1 }}>
            <CardContent>
              {/* */}
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
