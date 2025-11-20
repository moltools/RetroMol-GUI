import { z } from "zod";

export const EmbeddingPointSchema = z.object({
  parent_id: z.string(), // corresponds to SessionItem id
  child_id: z.string(), // corresponds to fingerprint item id
  kind: z.enum(["compound", "gene_cluster"]), // corresponds to SessionItem kind
  x: z.number(),
  y: z.number(),
})

export const GetEmbeddingSpaceRespSchema = z.object({ points: z.array(EmbeddingPointSchema) })

export type EmbeddingPoint = z.output<typeof EmbeddingPointSchema>;

const QuerySettingsSchema = z.object({
  scoreThreshold: z.number().min(0).max(1),
})

export type QuerySettings = z.infer<typeof QuerySettingsSchema>;

const EnrichmentItemSchema = z.object({
  id: z.string(),
  schema: z.string(),
  key: z.string(),
  value: z.string(),
  p_value: z.number(),
  adjusted_p_value: z.number(),
})

export type EnrichmentItem = z.infer<typeof EnrichmentItemSchema>;
  
export const EnrichmentResultSchema = z.object({
  items: z.array(EnrichmentItemSchema),
  querySettings: QuerySettingsSchema,
})

export type EnrichmentResult = z.infer<typeof EnrichmentResultSchema>;

// Simple response wrapper
export const CreateEnrichmentResultRespSchema = z.object({ result: EnrichmentResultSchema });
export const GetEnrichmentResultRespSchema = z.object({ result: EnrichmentResultSchema })
