import { postJson } from "../http";
import { SessionItem } from "../session/types";
import { EmbeddingPoint, GetEmbeddingSpaceRespSchema, GetEnrichmentResultRespSchema } from "./types";
import { EnrichmentResult, QuerySettings } from "./types";

export async function getEmbeddingSpace(sessionId: string, sessionItems: SessionItem[]): Promise<EmbeddingPoint[]> {
  const data = await postJson(
    "/api/getEmbeddingSpace",
    {
      sessionId: sessionId,
      items: sessionItems,
    },
    GetEmbeddingSpaceRespSchema
  )
  return data.points;
}

export async function runEnrichment({ fingerprint512, querySettings }: {
  fingerprint512: any;
  querySettings: QuerySettings;
}): Promise<EnrichmentResult> {
  const data = await postJson(
    "/api/enrich",
    {
      fingerprint512,
      querySettings,
    },
    GetEnrichmentResultRespSchema
  )
  return data.result;
}
