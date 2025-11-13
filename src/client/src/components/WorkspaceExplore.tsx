import React from "react";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Typography from "@mui/material/Typography";
import { Session } from "../features/session/types";

type WorkspaceExploreProps = {
  session: Session;
  setSession: (session: Session) => void;
}

export const WorkspaceExplore: React.FC<WorkspaceExploreProps> = ({ session, setSession }) => {
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
            The Explore tab is still under development. Please check back later for updates!
          </Typography>
        </CardContent>
      </Card>
    </Box>
  )
}
