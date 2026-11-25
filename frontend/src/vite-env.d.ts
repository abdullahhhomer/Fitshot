/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** The FitShot server when the app is hosted elsewhere, e.g. https://abc.trycloudflare.com */
  readonly VITE_API_BASE?: string;
}
