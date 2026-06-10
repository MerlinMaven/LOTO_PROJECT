/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_PROXY_TARGET?: string;
  readonly VITE_DEFAULT_REVIEWER_ID?: string;
  readonly VITE_DEFAULT_REVIEWER_ROLE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
