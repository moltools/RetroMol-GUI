import { z } from "zod";

export const EmbeddingPointSchema = z.object({
  parent_id: z.string(), // corresponds to SessionItem id
  child_id: z.string(), // corresponds to fingerprint item id
  kind: z.enum(["compound", "gene_cluster"]), // corresponds to SessionItem kind
  x: z.number(),
  y: z.number(),
})

export const GetEmbeddingSpaceRespSchema = z.object({
  points: z.array(EmbeddingPointSchema),
})

export type EmbeddingPoint = z.output<typeof EmbeddingPointSchema>;
