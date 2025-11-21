import React from "react";
import { DialogWindow } from "../components/DialogWindow";
import { SessionItem } from "../features/session/types";

type DialogViewItemProps = {
  open: boolean;
  item?: SessionItem | null;
  onClose: () => void;
}

export const DialogViewItem: React.FC<DialogViewItemProps> = ({
  open,
  item,
  onClose,
}) => {
  return (
    <DialogWindow
      open={open}
      onClose={onClose}
      title="View item"
      dividers
      maxWidth="sm"
      actions={[
        { label: "Cancel", variant: "text", color: "inherit", onClick: onClose },
      ]}
    >
      { item && (
        <>
          <div>Viewing item: {item.id}</div>
          {item.fingerprints && item.fingerprints.length > 0 && (
            <>
              <div>Number of fingerprints: {item.fingerprints.length}</div>
              {item.primarySequences && item.primarySequences.length > 0 && (
                <>
                  <div>Number of primary sequences: {item.primarySequences.length}</div>
                  {item.primarySequences.map((ps) => (
                    <div key={ps.id} style={{ marginTop: "1em", paddingLeft: "1em", borderLeft: "2px solid #ccc" }}>
                      <div>Primary Sequence ID: {ps.id}</div>
                      <div>Number of Motifs: {ps.sequence.length}</div>
                      {ps.sequence.map((motif) => (
                        <div key={motif.id} style={{ marginTop: "0.5em", paddingLeft: "1em", borderLeft: "2px solid #eee" }}>
                          <div>Motif ID: {motif.id}</div>
                          <div>Name: {motif.name ?? "N/A"}</div>
                          <div>Display Name: {motif.displayName ?? "N/A"}</div>
                          <div>SMILES: {motif.smiles ?? "N/A"}</div>
                        </div>
                      ))}
                    </div>
                  ))}
                </>
              )}  
            </>
          )}
        </>
      )}
    </DialogWindow>
  )
}
