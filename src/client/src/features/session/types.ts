import { z } from "zod";

export const SessionSchema = z.object({
  sessionId: z.string(),
  created: z.number(), // epoch ms 
})

export type Session = z.infer<typeof SessionSchema>;

// Simple response wrappers
export const CreateSessionRespSchema = z.object({ sessionId: z.string() });
export const GetSessionRespSchema = z.object({ session: SessionSchema });

export function initSession(): Session {
  const newSession = {
    sessionId: crypto.randomUUID(),
    created: Date.now(),
  } satisfies Session;

  return newSession;
}