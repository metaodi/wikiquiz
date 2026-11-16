<script lang="ts">
  import { onMount } from 'svelte';
  import { haptik } from '../lib/haptics';
  import { quellenLinkText } from '../lib/quelle';
  import SpielerChip from '../components/SpielerChip.svelte';
  import type { Antwort, Frage, Spieler, Zug } from '../lib/types';

  let {
    frage,
    zug,
    spieler,
    letzterZug,
    onWeiter,
    warteText,
    ergebnisse,
  }: {
    frage: Frage;
    zug: Zug;
    spieler: Spieler;
    letzterZug: boolean;
    /** Ohne `onWeiter` (mehrere Geräte, jemand anders ist dran) erscheint stattdessen `warteText`. */
    onWeiter?: () => void;
    warteText?: string;
    /** „Alle gleichzeitig“: Ergebnis aller Spieler */
    ergebnisse?: { spieler: Spieler; antwort: Antwort }[];
  } = $props();

  const timeout = $derived(zug.gewaehlt === null);

  onMount(() => {
    if (zug.richtig) haptik.richtig();
    else if (timeout) haptik.timeout();
    else haptik.falsch();
  });
</script>

<div class="ergebnis" class:richtig={zug.richtig} role="status">
  <span class="symbol" aria-hidden="true">{zug.richtig ? '✓' : timeout ? '⏱' : '✗'}</span>
  <div>
    <h1>{zug.richtig ? 'Richtig!' : timeout ? 'Zeit abgelaufen' : 'Leider falsch'}</h1>
    <p class="punkte">
      {#if zug.richtig}
        +{zug.punkte} Punkte <span class="muted">({zug.zeit?.toFixed(1)} s)</span>
      {:else}
        0 Punkte
      {/if}
      · Total {spieler.punkte}
    </p>
  </div>
</div>

<p class="frage">{frage.frage}</p>

<ul class="antworten">
  {#each zug.reihenfolge as i (i)}
    {@const korrekt = i === frage.korrekt_index}
    {@const gewaehlt = i === zug.gewaehlt}
    <li class:korrekt class:falsch={gewaehlt && !korrekt}>
      <span class="text">{frage.antworten[i]}</span>
      {#if korrekt}<span class="marke">richtige Antwort</span>{:else if gewaehlt}<span class="marke">deine Antwort</span>{/if}
    </li>
  {/each}
</ul>

{#if ergebnisse}
  <div class="alle" role="list" aria-label="Ergebnisse">
    {#each ergebnisse as e, i (i)}
      <div class="zeile" role="listitem">
        <SpielerChip spieler={e.spieler} />
        <span class="wahl" class:ok={e.antwort.richtig}>
          {e.antwort.gewaehlt === null ? 'keine Antwort' : frage.antworten[e.antwort.gewaehlt]}
        </span>
        <span class="plus">
          {e.antwort.richtig ? `+${e.antwort.punkte}` : '0'}
          {#if e.antwort.gewaehlt !== null}<span class="muted">· {e.antwort.zeit.toFixed(1)} s</span>{/if}
        </span>
      </div>
    {/each}
  </div>
{/if}

<a class="wiki" href={frage.quelle_url} target="_blank" rel="noopener noreferrer">
  {quellenLinkText(frage)} ↗
</a>

<div class="unten">
  {#if onWeiter}
    <button class="btn" onclick={onWeiter}>{letzterZug ? 'Zur Rangliste' : 'Weiter'}</button>
  {:else}
    <p class="muted warten" role="status">{warteText}</p>
  {/if}
</div>

<style>
  .alle {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px 14px;
    border-radius: var(--radius);
    background: var(--bg-2);
    box-shadow: var(--shadow);
  }
  .zeile {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 2px 10px;
    align-items: center;
  }
  .wahl {
    grid-column: 1;
    font-size: 0.95rem;
    color: var(--bad);
    overflow-wrap: anywhere;
  }
  .wahl.ok {
    color: var(--ok);
  }
  .plus {
    grid-column: 2;
    grid-row: 1 / span 2;
    font-weight: 800;
    text-align: right;
    white-space: nowrap;
  }
  .warten {
    margin: 0;
    text-align: center;
  }
  .ergebnis {
    display: flex;
    gap: 14px;
    align-items: center;
    padding: 16px;
    border-radius: var(--radius);
    background: var(--bad-bg);
    border-left: 6px solid var(--bad);
    animation: auftauchen 0.3s ease-out;
  }
  .ergebnis.richtig {
    background: var(--ok-bg);
    border-left-color: var(--ok);
  }
  .symbol {
    font-size: 2.2rem;
    font-weight: 800;
    color: var(--bad);
    width: 44px;
    text-align: center;
  }
  .richtig .symbol {
    color: var(--ok);
  }
  h1 {
    font-size: 1.5rem;
  }
  .punkte {
    margin: 2px 0 0;
    font-weight: 600;
  }
  .frage {
    margin: 0;
    font-weight: 600;
    overflow-wrap: anywhere;
  }
  .antworten {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  li {
    padding: 10px 14px;
    border-radius: 12px;
    border: 2px solid var(--line);
    background: var(--bg-2);
    display: flex;
    flex-direction: column;
    opacity: 0.7;
  }
  li.korrekt {
    border-color: var(--ok);
    background: var(--ok-bg);
    opacity: 1;
    font-weight: 700;
  }
  li.falsch {
    border-color: var(--bad);
    background: var(--bad-bg);
    opacity: 1;
  }
  .text {
    overflow-wrap: anywhere;
  }
  .marke {
    font-size: 0.8rem;
    font-weight: 600;
    color: var(--text-2);
  }
  .wiki {
    min-height: 48px;
    display: flex;
    align-items: center;
    font-weight: 600;
  }
  @keyframes auftauchen {
    from {
      transform: scale(0.95);
      opacity: 0;
    }
  }
</style>
