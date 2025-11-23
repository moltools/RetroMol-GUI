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
      actions={[
        { label: "Cancel", variant: "text", color: "inherit", onClick: onClose },
      ]}
    >
      { item && (
        <>
          <div>Viewing item: {item.id}</div>
          {item.retrofingerprints && item.retrofingerprints.length > 0 && (
            <>
              <div>Number of retrofingerprints: {item.retrofingerprints.length}</div>
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
                          <div>Tags: {motif.tags.join(", ") || "None"}</div>
                          <div>Morgan Fingerprint hex (2048 r2): {motif.morganfingerprint2048r2 ?? "N/A"}</div>
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
