<script lang="ts">
  import type { Platz } from '../lib/game';
  import SpielerChip from './SpielerChip.svelte';

  let { plaetze }: { plaetze: Platz[] } = $props();
</script>

<ol class="tabelle">
  {#each plaetze as p (p.index)}
    <li style:--farbe={p.spieler.farbe}>
      <span class="rang">{p.rang}.</span>
      <SpielerChip spieler={p.spieler} />
      <span class="punkte">{p.spieler.punkte}</span>
    </li>
  {/each}
</ol>

<style>
  .tabelle {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  li {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 14px;
    border-radius: 12px;
    background: var(--bg-2);
    box-shadow: var(--shadow);
    border-left: 6px solid var(--farbe);
  }
  .rang {
    font-weight: 800;
    width: 2ch;
  }
  .punkte {
    margin-left: auto;
    font-weight: 800;
    font-variant-numeric: tabular-nums;
    font-size: 1.15rem;
  }
</style>
