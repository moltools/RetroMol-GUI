import { postJson } from "../http";
import { Session } from "../session/types";
import { EmbeddingPoint, GetEmbeddingSpaceRespSchema } from "./types";

export async function getEmbeddingSpace(session: Session): Promise<EmbeddingPoint[]> {
  const data = await postJson(
    "/api/getEmbeddingSpace",
    {
      sessionId: session.sessionId,
      items: session.items,
    },
    GetEmbeddingSpaceRespSchema
  )
  return data.points;
}
