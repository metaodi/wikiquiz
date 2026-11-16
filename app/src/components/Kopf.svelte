<script lang="ts">
  import type { Spieler, Spielstand } from '../lib/types';
  import SpielerChip from './SpielerChip.svelte';

  /** `spieler`: wer oben angezeigt wird – standardmässig der aktive Spieler, bei „Alle gleichzeitig“ man selbst */
  let { spiel, onBeenden, spieler }: { spiel: Spielstand; onBeenden: () => void; spieler?: Spieler } = $props();
  const aktiv = $derived(spieler ?? spiel.spieler[spiel.aktiverSpieler]);
</script>

<header class="kopf">
  <SpielerChip spieler={aktiv} />
  <span class="runde muted">Runde {spiel.runde}/{spiel.runden} · {aktiv.punkte} P.</span>
  <button class="textlink" onclick={onBeenden} aria-label="Spiel beenden">✕</button>
</header>

<style>
  .kopf {
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 48px;
  }
  .runde {
    margin-left: auto;
    font-size: 0.95rem;
    white-space: nowrap;
  }
  .textlink {
    text-decoration: none;
    font-size: 1.2rem;
  }
</style>
