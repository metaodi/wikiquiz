<script lang="ts">
  import { onMount } from 'svelte';
  import { haptik } from '../lib/haptics';
  import type { Frage, Spieler, Zug } from '../lib/types';

  let {
    frage,
    zug,
    spieler,
    letzterZug,
    onWeiter,
  }: { frage: Frage; zug: Zug; spieler: Spieler; letzterZug: boolean; onWeiter: () => void } = $props();

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

<a class="wiki" href={frage.quelle_url} target="_blank" rel="noopener noreferrer">
  Mehr auf Wikipedia{frage.quelle_titel ? `: ${frage.quelle_titel}` : ''} ↗
</a>

<div class="unten">
  <button class="btn" onclick={onWeiter}>{letzterZug ? 'Zur Rangliste' : 'Weiter'}</button>
</div>

<style>
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
