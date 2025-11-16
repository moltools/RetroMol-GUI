import { z } from "zod";

export const EmbeddingPointSchema = z.object({
  id: z.string(), // corresponds to SessionItem id
  x: z.number(),
  y: z.number(),
})

export const GetEmbeddingSpaceRespSchema = z.object({
  points: z.array(EmbeddingPointSchema),
})

export type EmbeddingPoint = z.output<typeof EmbeddingPointSchema>;
