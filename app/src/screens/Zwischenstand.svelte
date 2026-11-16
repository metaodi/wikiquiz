<script lang="ts">
  import Tabelle from '../components/Tabelle.svelte';
  import { rangliste } from '../lib/game';
  import type { Spielstand } from '../lib/types';

  /** Ohne `onWeiter` (mehrere Geräte, nicht der Host) erscheint stattdessen `warteText`. */
  let { spiel, onWeiter, warteText }: { spiel: Spielstand; onWeiter?: () => void; warteText?: string } = $props();
  const plaetze = $derived(rangliste(spiel.spieler));
</script>

<div class="screen">
  <p class="muted">Runde {spiel.runde - 1} von {spiel.runden} beendet</p>
  <h1>Zwischenstand</h1>
  <Tabelle {plaetze} />
  <div class="unten">
    {#if onWeiter}
      <button class="btn" onclick={onWeiter}>Runde {spiel.runde} starten</button>
    {:else}
      <p class="muted warten" role="status">{warteText}</p>
    {/if}
  </div>
</div>

<style>
  p {
    margin: 0;
  }
  .warten {
    text-align: center;
  }
</style>
