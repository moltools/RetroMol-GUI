import React from "react";
import Box from "@mui/material/Box";
import Dialog from "@mui/material/Dialog";
import DialogTitle from "@mui/material/DialogTitle";
import DialogContent from "@mui/material/DialogContent";
import DialogActions from "@mui/material/DialogActions";
import IconButton from "@mui/material/IconButton";
import Button, { ButtonProps } from "@mui/material/Button";
import CloseIcon from "@mui/icons-material/Close";
import type { DialogProps } from "@mui/material/Dialog";
import type { DialogContentProps } from "@mui/material/DialogContent";

type ActionConfig = {
  key?: string;
  label: React.ReactNode;
  onClick?: () => void | Promise<void>;
  color?: ButtonProps["color"];
  variant?: ButtonProps["variant"];
  disabled?: boolean;
  startIcon?: React.ReactNode;
  autoFocus?: boolean;
}

type Action = React.ReactNode | ActionConfig;

export interface DialogWindowProps {
  open: boolean;
  title?: React.ReactNode;
  onClose: (event: object, reason?: "backdropClick" | "escapeKeyDown") => void;
  children?: React.ReactNode;

  /** Bottom-right actions; pass configs or fully custom nodes */
  actions?: Action[];

  /** Extras like styling */
  maxWidth?: DialogProps["maxWidth"];
  fullWidth?: DialogProps["fullWidth"];
  dividers?: DialogContentProps["dividers"];
  disableCloseButton?: boolean;
  ContentProps?: Partial<DialogContentProps>;
  PaperProps?: DialogProps["PaperProps"];
}

export const DialogWindow: React.FC<DialogWindowProps> = ({
  open,
  title,
  onClose,
  children,
  actions,
  fullWidth = true,
  dividers = false,
  disableCloseButton = false,
  ContentProps,
  PaperProps,
}) => {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth={"sm"}
      fullWidth={fullWidth}
      PaperProps={PaperProps}
    >
      {(title || !disableCloseButton) && (
        <DialogTitle sx={{ pr: disableCloseButton ? 3 : 6 }}>
          {title}
          {!disableCloseButton && (
            <Box
              onClick={(e) => onClose(e as any, "escapeKeyDown")}
              sx={{
                position: "absolute",
                right: 8,
                top: 8,
                cursor: "pointer",
                lineHeight: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                outline: "none",
                "&:hover": { outline: "none" },
                "&:focus": { outline: "none" },
                "&:focus-visible": { outline: "none" },
              }}
            >
              <CloseIcon fontSize="small" />
            </Box>
          )}
        </DialogTitle>
      )}
      
      <DialogContent dividers={dividers} {...ContentProps}>
        {children}
      </DialogContent>

      {Array.isArray(actions) && actions.length > 0 && (
        <DialogActions sx={{ px: 3, py: 2 }}>
          {actions.filter(Boolean).map((a, i) => {
            // Guarantee that 'a' is either a React element or an ActionConfig
            if (React.isValidElement(a)) {
              return <React.Fragment key={(a as any).key ?? i}>{a}</React.Fragment>;
            }
            const action = a as ActionConfig;
            return (
              <Button
                key={action.key ?? i}
                onClick={action.onClick}
                color={action.color ?? "primary"}
                variant={action.variant ?? "contained"}
                disabled={action.disabled}
                startIcon={action.startIcon}
                autoFocus={action.autoFocus}
              >
                {action.label}
              </Button>
            )
          })}
        </DialogActions>
      )}

    </Dialog>
  )
}
