/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** URL, die TURN-Zugangsdaten liefert (z. B. Metered), siehe src/lib/turn.ts */
  readonly VITE_TURN_CREDENTIALS_URL?: string;
}
