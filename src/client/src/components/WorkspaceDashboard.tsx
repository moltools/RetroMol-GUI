import React from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import MuiLink from "@mui/material/Link";
import Typography from "@mui/material/Typography";
import { useTheme } from "@mui/material/styles";
import { Link as RouterLink } from "react-router-dom";
import { useNotifications } from "../components/NotificationProvider";
import type { QueryResult } from "../features/query/types";
import { runQuery } from "../features/query/api";

export const WorkspaceDashboard: React.FC = () => {
    const theme = useTheme();
    const { pushNotification } = useNotifications();

    const [result, setResult] = React.useState<QueryResult | null>(null);

    React.useEffect(() => {
      let alive = true;
      (async () => {
        try {
          const r = await runQuery({
            name: "compound_by_mass",
            params: { min_mass: 100, max_mass: 300 },
            paging: { limit: 50, offset: 0 },
            order: { column: "exact_mass", dir: "asc" },
          });
          if (alive) setResult(r);
        } catch (e: any) {
          pushNotification(e?.message ?? "Query failed", "error");
        };
      })();
    }, [pushNotification]);

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
              Welcome to the RetroMol dashboard! Here you can find an overview of available data in the database.
              Use the navigation menu on the left to upload your data in the&nbsp;
              <MuiLink
                component={RouterLink}
                to="/dashboard/upload"
                underline="hover"
                color={(theme.vars || theme).palette.primary.main}
                sx={{ fontWeight: "500" }}
              >
                Upload tab
              </MuiLink>
              .
              Biosynthetic fingerprints are automatically parsed from your data during upload.
              You can use the biosynthetic fingerprints parsed from you data for exploratory data analysis in the&nbsp;
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
              Exploratory data analysis allows you to retrieve similar biosynthetic fingerprints and their associated metadata from the database using your uploaded data.
            </Typography>
          </CardContent>
        </Card>
      </Box>
    )
}
