<script lang="ts">
  import { FARB_NAMEN, MAX_SPIELER, RUNDEN_OPTIONEN, RUNDEN_STANDARD, SPIELER_FARBEN } from '../lib/config';
  import type { LetzteSpieler } from '../lib/storage';

  let {
    letzte,
    anzahlFragen,
    onStart,
    onInfo,
  }: {
    letzte: LetzteSpieler | null;
    anzahlFragen: number;
    onStart: (spieler: { name: string; farbe: string }[], runden: number) => void;
    onInfo: () => void;
  } = $props();

  // svelte-ignore state_referenced_locally
  const start = letzte;
  let spieler = $state(
    start?.namen.length
      ? start.namen.map((name, i) => ({ name, farbe: start.farben[i] ?? SPIELER_FARBEN[i] }))
      : [{ name: '', farbe: SPIELER_FARBEN[0] }],
  );
  // svelte-ignore state_referenced_locally
  let runden = $state(start?.runden ?? RUNDEN_STANDARD);

  const namen = $derived(spieler.map((p, i) => p.name.trim() || `Spieler ${i + 1}`));
  const doppelt = $derived(new Set(namen.map((n) => n.toLowerCase())).size !== namen.length);

  function hinzufuegen() {
    const frei = SPIELER_FARBEN.find((f) => !spieler.some((p) => p.farbe === f)) ?? SPIELER_FARBEN[0];
    spieler.push({ name: '', farbe: frei });
  }

  function entfernen(i: number) {
    spieler.splice(i, 1);
  }

  function starten(e: SubmitEvent) {
    e.preventDefault();
    if (doppelt) return;
    onStart(
      spieler.map((p, i) => ({ name: namen[i], farbe: p.farbe })),
      runden,
    );
  }
</script>

<form class="screen" onsubmit={starten}>
  <header class="titel">
    <h1>WikiQuiz</h1>
    <p class="muted">Wissen aus Wikipedia – für 1 bis 4 Spieler auf einem Gerät.</p>
  </header>

  <section class="karte" aria-labelledby="spieler-titel">
    <h2 id="spieler-titel">Spieler</h2>
    <ol class="liste">
      {#each spieler as p, i (i)}
        <li class="zeile">
          <input
            class="name"
            type="text"
            bind:value={p.name}
            placeholder={`Spieler ${i + 1}`}
            maxlength="20"
            autocomplete="off"
            aria-label={`Name Spieler ${i + 1}`}
            style:border-color={p.farbe}
          />
          {#if spieler.length > 1}
            <button type="button" class="entfernen" onclick={() => entfernen(i)} aria-label={`Spieler ${i + 1} entfernen`}>✕</button>
          {/if}
          <div class="farben" role="radiogroup" aria-label={`Farbe Spieler ${i + 1}`}>
            {#each SPIELER_FARBEN as f (f)}
              <button
                type="button"
                class="farbe"
                class:gewaehlt={p.farbe === f}
                style:background={f}
                role="radio"
                aria-checked={p.farbe === f}
                aria-label={FARB_NAMEN[f] ?? f}
                onclick={() => (p.farbe = f)}
              ></button>
            {/each}
          </div>
        </li>
      {/each}
    </ol>
    {#if spieler.length < MAX_SPIELER}
      <button type="button" class="btn sekundaer klein" onclick={hinzufuegen}>+ Spieler hinzufügen</button>
    {/if}
    {#if doppelt}
      <p class="fehler" role="alert">Bitte unterschiedliche Namen verwenden.</p>
    {/if}
  </section>

  <section class="karte" aria-labelledby="runden-titel">
    <h2 id="runden-titel">Runden</h2>
    <p class="muted klein-text">In jeder Runde beantwortet jeder Spieler eine Frage.</p>
    <div class="segment" role="radiogroup" aria-labelledby="runden-titel">
      {#each RUNDEN_OPTIONEN as r (r)}
        <button type="button" role="radio" aria-checked={runden === r} class:aktiv={runden === r} onclick={() => (runden = r)}>
          {r}
        </button>
      {/each}
    </div>
  </section>

  <div class="unten">
    <button class="btn" type="submit" disabled={doppelt || anzahlFragen === 0}>Spiel starten</button>
    <button type="button" class="textlink" onclick={onInfo}>Info, Quellen & Lizenzen</button>
  </div>
</form>

<style>
  .titel h1 {
    font-size: 2.2rem;
    letter-spacing: -0.02em;
  }
  .titel p {
    margin: 4px 0 0;
  }
  .karte {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  h2 {
    font-size: 1.1rem;
  }
  .liste {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .zeile {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 8px;
  }
  .name {
    min-height: 52px;
    border: 3px solid;
    border-radius: 12px;
    padding: 8px 12px;
    background: var(--bg);
    min-width: 0;
  }
  .entfernen {
    width: 52px;
    border: 0;
    background: none;
    color: var(--text-2);
    font-size: 1.2rem;
  }
  .farben {
    grid-column: 1 / -1;
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }
  .farbe {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    border: 3px solid transparent;
    box-shadow: inset 0 0 0 2px rgba(255, 255, 255, 0.6);
  }
  .farbe.gewaehlt {
    border-color: var(--text);
  }
  .segment {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
  }
  .segment button {
    min-height: 52px;
    border-radius: 12px;
    border: 2px solid var(--line);
    background: var(--bg);
    font-weight: 700;
    font-size: 1.1rem;
  }
  .segment button.aktiv {
    background: var(--accent);
    color: var(--accent-text);
    border-color: var(--accent);
  }
  .klein-text {
    margin: -6px 0 0;
    font-size: 0.95rem;
  }
  .fehler {
    color: var(--bad);
    margin: 0;
  }
</style>
