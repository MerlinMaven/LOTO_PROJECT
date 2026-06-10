/**
 * Reviewer identity store.
 *
 * Until real auth (JWT) lands, the reviewer identity is sent as X-User-Id /
 * X-User-Role headers (read by the backend's get_current_user stub). The
 * 4-eyes rule is enforced server-side using this identity, so it must be a
 * real reviewer, distinct from the draft's author.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { env } from "@/config/env";

interface AuthState {
  reviewerId: string;
  reviewerRole: string;
  setReviewer: (id: string, role?: string) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      reviewerId: env.reviewer.id,
      reviewerRole: env.reviewer.role,
      setReviewer: (id, role) =>
        set((s) => ({ reviewerId: id, reviewerRole: role ?? s.reviewerRole })),
    }),
    { name: "smartloto.reviewer" },
  ),
);
