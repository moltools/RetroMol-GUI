import { postJson } from "../http";
import { MsaSettings, SessionItem, SessionSettings } from "../session/types";
import {
  EmbeddingPoint,
  GetEmbeddingSpaceRespSchema,
  GetEnrichmentResultRespSchema,
  GetMsaResultRespSchema,
  MsaResult
} from "./types";
import { EnrichmentResult } from "./types";
import { QuerySettings } from "../session/types";
import { PrimarySequence } from "../session/types";

export async function getEmbeddingSpace(
  sessionId: string,
  sessionItems: SessionItem[],
  method: SessionSettings["embeddingVisualizationType"] = "pca"
): Promise<EmbeddingPoint[]> {
  const data = await postJson(
    "/api/getEmbeddingSpace",
    {
      sessionId: sessionId,
      items: sessionItems,
      method,
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

export async function runMsa({ primarySequences, centerId, msaSettings }: {
  primarySequences: PrimarySequence[];
  centerId?: string;
  msaSettings?: MsaSettings;
}): Promise<MsaResult> {
  const data = await postJson(
    "/api/runMsa",
    {
      primarySequences,
      centerId,
      msaSettings,
    },
    GetMsaResultRespSchema
  )
  return data.result;
}
