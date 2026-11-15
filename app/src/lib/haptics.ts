/** Kurzes haptisches Feedback über die Vibration API, wo verfügbar. */
function vibrieren(muster: number | number[]): void {
  try {
    if (typeof navigator !== 'undefined' && 'vibrate' in navigator) navigator.vibrate(muster);
  } catch {
    /* nicht unterstützt */
  }
}

export const haptik = {
  tippen: () => vibrieren(10),
  richtig: () => vibrieren(40),
  falsch: () => vibrieren([60, 50, 60]),
  timeout: () => vibrieren([120]),
};
