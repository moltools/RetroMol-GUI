import React from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Typography from "@mui/material/Typography";
import MuiLink from "@mui/material/Link";
import NotificationsRoundedIcon from "@mui/icons-material/NotificationsRounded";
import { useTheme } from "@mui/material/styles";
import { useNotifications } from "../../NotificationProvider";
import { Link as RouterLink } from "react-router-dom";
import { Session } from "../../../../features/session/types";

type WorkspaceDiscoveryProps = {
  session: Session;
  setSession: React.Dispatch<React.SetStateAction<Session | null>>;
};

export const WorkspaceDiscovery: React.FC<WorkspaceDiscoveryProps> = ({ session, setSession }) => {
  const theme = useTheme();
  const { pushNotification } = useNotifications();

  // Wrap parent setter (Session | null) into the deps shape (Session-only functional updater)
  const setSessionSafe = React.useCallback(
    (updater: (prev: Session) => Session) => {
      setSession((prev) => (prev ? updater(prev) : prev));
    },
    [setSession]
  );

  // Helper to build deps for import service
  const deps = React.useMemo(
    () => ({
      setSession: setSessionSafe,
      pushNotification,
      sessionId: session.sessionId,
    }),
    [setSessionSafe, pushNotification, session.sessionId]
  );

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
            Here you can use uploaded items from the&nbsp;
            <MuiLink
              component={RouterLink}
              to="/dashboard/upload"
              underline="hover"
              color={(theme.vars || theme).palette.primary.main}
              sx={{ fontWeight: "500" }}
            >
              Upload tab
            </MuiLink>
            &nbsp;for cross-modal retrieval against the BioNexus database.
          </Typography>

        </CardContent>
      </Card>
    </Box>
  );
};
