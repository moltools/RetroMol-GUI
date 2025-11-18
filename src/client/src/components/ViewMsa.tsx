import React from "react";
import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { Session } from "../features/session/types";

interface ViewMsaProps {
  session: Session;
  setSession: (updated: (prev: Session) => Session) => void;
}

export const ViewMsa: React.FC<ViewMsaProps> = ({
  session,
  setSession,
}) => {
  return (
    <Box>
      <Typography variant="body2">
        MSA view is currently unavailable.
      </Typography>
    </Box>
  )
}
