import { postJson } from "../http";
import { SessionItem } from "../session/types";
import { EmbeddingPoint, GetEmbeddingSpaceRespSchema } from "./types";

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
