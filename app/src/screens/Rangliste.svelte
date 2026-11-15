<script lang="ts">
  import Tabelle from '../components/Tabelle.svelte';
  import { rangliste } from '../lib/game';
  import type { Spielstand } from '../lib/types';

  let { spiel, onNochmals, onNeu }: { spiel: Spielstand; onNochmals: () => void; onNeu: () => void } = $props();
  const plaetze = $derived(rangliste(spiel.spieler));
  const sieger = $derived(plaetze.filter((p) => p.rang === 1));
  const solo = $derived(spiel.spieler.length === 1);
</script>

<div class="screen">
  <div class="sieg" aria-live="polite">
    <div class="pokal" aria-hidden="true">🏆</div>
    {#if solo}
      <h1>Geschafft!</h1>
      <p class="gross">{sieger[0].spieler.punkte} Punkte</p>
    {:else if sieger.length > 1}
      <h1>Gleichstand!</h1>
      <p class="gross">{sieger.map((p) => p.spieler.name).join(' & ')}</p>
      <p class="muted">teilen sich den Sieg mit {sieger[0].spieler.punkte} Punkten</p>
    {:else}
      <h1>{sieger[0].spieler.name} gewinnt!</h1>
      <p class="muted">mit {sieger[0].spieler.punkte} Punkten</p>
    {/if}
  </div>

  {#if !solo}
    <Tabelle {plaetze} />
  {/if}

  <div class="unten">
    <button class="btn" onclick={onNochmals}>Nochmals spielen</button>
    <button class="btn sekundaer" onclick={onNeu}>Neues Spiel</button>
  </div>
</div>

<style>
  .sieg {
    text-align: center;
    padding-top: 4vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
  }
  .pokal {
    font-size: 4.5rem;
    animation: hupf 0.8s cubic-bezier(0.3, 1.6, 0.5, 1);
  }
  h1 {
    font-size: 1.8rem;
    overflow-wrap: anywhere;
  }
  p {
    margin: 0;
  }
  .gross {
    font-size: 1.4rem;
    font-weight: 800;
  }
  @keyframes hupf {
    from {
      transform: scale(0.3) rotate(-15deg);
      opacity: 0;
    }
  }
</style>
