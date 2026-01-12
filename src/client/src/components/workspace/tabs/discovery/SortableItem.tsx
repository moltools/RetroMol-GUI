import React from "react";
import Box from "@mui/material/Box";
import { CSS } from "@dnd-kit/utilities";
import { useSortable } from "@dnd-kit/sortable";

interface SortableItemProps {
  id: string;
  children: React.ReactNode;
  disabled?: boolean;  // if true, cannot dragt THIS item
};

export const SortableItem: React.FC<SortableItemProps> = ({ id, children, disabled }) => {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({
    id,
    disabled,
    animateLayoutChanges: () => false,
  })

  return (
    <Box
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      {...(disabled ? {} : listeners)}
      sx={{
        transform: transform ? CSS.Transform.toString(transform) : undefined,
        transition,
        display: "inline-block",
        cursor: disabled ? "default" : "grab",
        "&:focus": { outline: "none" },
        zIndex: 100,
      }}
    >
      {children}
    </Box>
  );
};