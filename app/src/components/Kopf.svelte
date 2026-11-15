<script lang="ts">
  import type { Spielstand } from '../lib/types';
  import SpielerChip from './SpielerChip.svelte';

  let { spiel, onBeenden }: { spiel: Spielstand; onBeenden: () => void } = $props();
  const aktiv = $derived(spiel.spieler[spiel.aktiverSpieler]);
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
