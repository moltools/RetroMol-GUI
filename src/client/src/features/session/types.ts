import { z } from "zod";

export const BaseItemSchema = z.object({
  id: z.string(),
  name: z.string(), // display name
  status: z.enum(["queued", "processing", "done", "error"]).default("queued"),
  errorMessage: z.string().nullable().optional(),
  updatedAt: z.number().nonnegative().default(() => Date.now()),
})

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
})

export const GeneClusterSchema = BaseItemSchema.extend({
  kind: z.literal("gene_cluster"),
  fileContent: z.string(),
  fingerprints: z.array(GeneClusterFingerprintSchema).default([]),
})

export const SessionItemSchema = z.discriminatedUnion("kind", [
  CompoundItemSchema,
  GeneClusterSchema,
])

export type CompoundItem = z.output<typeof CompoundItemSchema>;
export type GeneClusterItem = z.output<typeof GeneClusterSchema>;
export type SessionItem = z.output<typeof SessionItemSchema>;

export const SessionSchema = z.object({
  sessionId: z.string(),
  created: z.number().nonnegative(),
  items: z.array(SessionItemSchema).default([]),
})

export type Session = z.output<typeof SessionSchema>;

// Simple response wrappers
export const CreateSessionRespSchema = z.object({ sessionId: z.string() });
export const GetSessionRespSchema = z.object({ session: SessionSchema });

export function initSession(): Session {
  const newSession = {
    sessionId: crypto.randomUUID(),
    created: Date.now(),
    items: [],
  } satisfies Session;

  return newSession;
}