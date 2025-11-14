import { postJson } from "../http";
import type { CompoundItem } from "../session/types";
import { z } from "zod";

const SubmitJobRespSchema = z.object({
  ok: z.boolean(),
  elapsed_ms: z.number().int().nonnegative(),
  status: z.string().optional(),
}).partial() // we don't actually use the response body here

export async function submitCompoundJob(
  sessionId: string,
  item: CompoundItem
): Promise<void> {
  await postJson(
    "/api/submit_compound",
    {
      sessionId,
      itemId: item.id,
      name: item.name,
      smiles: item.smiles,
    },
    SubmitJobRespSchema
  )
}
