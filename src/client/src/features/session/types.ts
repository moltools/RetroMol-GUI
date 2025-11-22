import { defaultMotifColorMap } from "./utils";
import { z } from "zod";

export const BaseItemSchema = z.object({
  id: z.string(),
  name: z.string(), // display name
  status: z.enum(["queued", "processing", "done", "error"]).default("queued"),
  errorMessage: z.string().nullable().optional(),
  updatedAt: z.number().nonnegative().default(() => Date.now()),
})

export const PrimarySequenceMotifSchema = z.object({
  id: z.string(),
  name: z.string().nullable().optional(),
  displayName: z.string().nullable().optional(),
  smiles: z.string().nullable().optional(),
})

export type PrimarySequenceMotif = z.output<typeof PrimarySequenceMotifSchema>;

export const PrimarySequenceSchema = z.object({
  id: z.string(),
  name: z.string().nullable().optional(),
  sequence: z.array(PrimarySequenceMotifSchema).min(1),
})

export type PrimarySequence = z.output<typeof PrimarySequenceSchema>;

export const BaseFingerprintSchema = z.object({
  id: z.string(),
  fingerprint512: z.string().length(128),
  score: z.number().min(0).max(1),
})

export const CompoundFingerprintSchema = BaseFingerprintSchema.extend({});
export const GeneClusterFingerprintSchema = BaseFingerprintSchema.extend({});

export const CompoundItemSchema = BaseItemSchema.extend({
  kind: z.literal("compound"),
  smiles: z.string(),
  fingerprints: z.array(CompoundFingerprintSchema).default([]),
  primarySequences: z.array(PrimarySequenceSchema).default([]),
})

export const GeneClusterSchema = BaseItemSchema.extend({
  kind: z.literal("gene_cluster"),
  fileContent: z.string(),
  fingerprints: z.array(GeneClusterFingerprintSchema).default([]),
  primarySequences: z.array(PrimarySequenceSchema).default([]),
})

export const SessionItemSchema = z.discriminatedUnion("kind", [
  CompoundItemSchema,
  GeneClusterSchema,
])

export type CompoundItem = z.output<typeof CompoundItemSchema>;
export type GeneClusterItem = z.output<typeof GeneClusterSchema>;
export type SessionItem = z.output<typeof SessionItemSchema>;

export const SessionSettingsSchema = z.object({
  // Color palette for motifs in MSA view
  motifColorPalette: z.record(z.string()).default(() => defaultMotifColorMap()),
  // Embedding space visualization type is either "pca" or "umap"
  embeddingVisualizationType: z.enum(["pca", "umap"]).default("pca"),
  // Similarity threshold for querying in [0, 1] range
  similarityThreshold: z.number().min(0).max(1).default(0.7),
});

export type SessionSettings = z.output<typeof SessionSettingsSchema>;

export const SessionSchema = z.object({
  sessionId: z.string().default(() => crypto.randomUUID()),
  created: z.number().nonnegative().default(() => Date.now()),
  items: z.array(SessionItemSchema).default([]),
  settings: SessionSettingsSchema.default(() => ({})),
})

export type Session = z.output<typeof SessionSchema>;

// Simple response wrappers
export const CreateSessionRespSchema = z.object({ sessionId: z.string() });
export const GetSessionRespSchema = z.object({ session: SessionSchema });

export function initSession(): Session {
  const newSession = SessionSchema.parse({});
  return newSession;
}