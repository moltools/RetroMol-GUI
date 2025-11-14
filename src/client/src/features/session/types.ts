import { z } from "zod";

export const BaseItemSchema = z.object({
  id: z.string(),
  status: z.enum(["queued", "processing", "done", "error"]).default("queued"),
  errorMessage: z.string().nullable().optional(),
  updatedAt: z.number().nonnegative().default(() => Date.now()),
})

export const CompoundItemSchema = BaseItemSchema.extend({
  kind: z.literal("compound"),
  name: z.string(),
  smiles: z.string(),
})

export const GeneClusterSchema = BaseItemSchema.extend({
  kind: z.literal("gene_cluster"),
  fileName: z.string(),
  fileContent: z.string(),
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