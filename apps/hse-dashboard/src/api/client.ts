/**
 * Axios instance shared by all API modules.
 *
 * Responsibilities:
 * - Base URL from env.
 * - Inject the reviewer identity headers (X-User-Id / X-User-Role) that the
 *   backend's get_current_user stub reads. Swap for an Authorization bearer
 *   token here when real auth lands — nothing else changes.
 * - Normalise FastAPI error bodies into a typed ApiError.
 */

import axios, { AxiosError } from "axios";
import { env } from "@/config/env";
import { ApiError, type ApiErrorBody } from "@/types/api";
import { useAuthStore } from "@/store/authStore";

export const http = axios.create({
  baseURL: env.apiBaseUrl,
  headers: { "Content-Type": "application/json" },
});

http.interceptors.request.use((config) => {
  const { reviewerId, reviewerRole } = useAuthStore.getState();
  config.headers.set("X-User-Id", reviewerId);
  config.headers.set("X-User-Role", reviewerRole);
  return config;
});

http.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorBody>) => {
    const status = error.response?.status ?? 0;
    const body = error.response?.data;

    if (body && typeof body === "object" && "error" in body) {
      const e = body.error;
      return Promise.reject(new ApiError(e.code, e.message, status, e.details));
    }

    // FastAPI request-validation errors (422) have a different shape.
    if (status === 422) {
      let message = "Erreur de validation des données transmises.";
      if (body && typeof body === "object" && "detail" in body && Array.isArray((body as Record<string, unknown>).detail)) {
        const details = (body as { detail: Array<{ msg?: string; loc?: string[] }> }).detail;
        const formatted = details
          .map((d) => {
            const field = d.loc ? d.loc.filter((part) => part !== "body").join(".") : "";
            return field ? `${field} (${d.msg})` : d.msg;
          })
          .filter(Boolean)
          .join(", ");
        if (formatted) message = `Validation rejetée : ${formatted}`;
      }
      return Promise.reject(
        new ApiError("VALIDATION_ERROR", message, status, {
          raw: body,
        }),
      );
    }

    return Promise.reject(
      new ApiError(
        "NETWORK_ERROR",
        error.message || "Unable to reach the SmartLOTO backend.",
        status,
      ),
    );
  },
);
