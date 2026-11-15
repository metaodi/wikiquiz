<script lang="ts">
  import Tabelle from '../components/Tabelle.svelte';
  import { rangliste } from '../lib/game';
  import type { Spielstand } from '../lib/types';

  let { spiel, onWeiter }: { spiel: Spielstand; onWeiter: () => void } = $props();
  const plaetze = $derived(rangliste(spiel.spieler));
</script>

<div class="screen">
  <p class="muted">Runde {spiel.runde - 1} von {spiel.runden} beendet</p>
  <h1>Zwischenstand</h1>
  <Tabelle {plaetze} />
  <div class="unten">
    <button class="btn" onclick={onWeiter}>Runde {spiel.runde} starten</button>
  </div>
</div>

<style>
  p {
    margin: 0;
  }
</style>
