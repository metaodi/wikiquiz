<script lang="ts">
  import type { Teilnehmer } from '../lib/raum';
  import SpielerChip from './SpielerChip.svelte';

  /** Raumcode und Liste der beigetretenen Geräte (Lobby von Host und Gästen) */
  let { code, teilnehmer, ich }: { code: string; teilnehmer: Teilnehmer[]; ich: string } = $props();
</script>

<section class="karte" aria-labelledby="raum-titel">
  <h2 id="raum-titel">Raum</h2>
  <p class="code" aria-label="Raumcode">{code}</p>
  <p class="muted hinweis">Weitere Geräte wählen „Mit mehreren Geräten spielen“ und geben diesen Code ein.</p>
  <ol class="liste" aria-label="Spieler im Raum">
    {#each teilnehmer as t (t.geraet)}
      <li>
        <SpielerChip spieler={t} />
        {#if t.geraet === ich}<span class="muted">(du)</span>{/if}
        {#if t === teilnehmer[0]}<span class="muted">· leitet das Spiel</span>{/if}
      </li>
    {/each}
  </ol>
</section>

<style>
  .karte {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  h2 {
    font-size: 1.1rem;
  }
  p {
    margin: 0;
  }
  .code {
    font-size: 2.4rem;
    font-weight: 800;
    letter-spacing: 0.25em;
    text-align: center;
  }
  .hinweis {
    font-size: 0.95rem;
  }
  .liste {
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
    gap: 6px;
    flex-wrap: wrap;
    min-height: 40px;
  }
</style>
