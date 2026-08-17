/// <reference types="vite/client" />

interface ImportMetaEnv {
  /**
   * Base URL of the API, e.g. https://api.example.org/api/v1
   *
   * Every VITE_* variable is inlined into the browser bundle and is therefore
   * PUBLIC. Secrets must never be placed here.
   */
  readonly VITE_API_BASE_URL: string;
  /** Public origin used to build shareable group URLs. */
  readonly VITE_PUBLIC_BASE_URL: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
