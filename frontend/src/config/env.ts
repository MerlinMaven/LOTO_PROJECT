/**
 * Centralised, typed access to environment configuration.
 *
 * Everything that reads import.meta.env goes through here so the rest of the
 * app never touches raw env vars and tests can stub a single module.
 */

export const env = {
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? "/api",
  reviewer: {
    id: import.meta.env.VITE_DEFAULT_REVIEWER_ID ?? "hse_reviewer@smartloto.io",
    role: import.meta.env.VITE_DEFAULT_REVIEWER_ROLE ?? "hse_reviewer",
  },
} as const;
