<script lang="ts">
  import { KATEGORIEN } from '../lib/categories';
  import { FARB_NAMEN, MAX_SPIELER, RUNDEN_OPTIONEN, RUNDEN_STANDARD, SPIELER_FARBEN } from '../lib/config';
  import { ALLE_KATEGORIEN, einstellungenPruefen } from '../lib/game';
  import type { LetzteSpieler } from '../lib/storage';
  import type { Einstellungen, KategorieId, KategorieModus } from '../lib/types';

  let {
    letzte,
    gesamt,
    onStart,
    onInfo,
  }: {
    letzte: LetzteSpieler | null;
    /** Fragen pro Kategorie im Pool */
    gesamt: Record<KategorieId, number>;
    onStart: (spieler: { name: string; farbe: string }[], runden: number, einstellungen: Einstellungen) => void;
    onInfo: () => void;
  } = $props();

  const MODI: { id: KategorieModus; titel: string; text: string }[] = [
    { id: 'selbst', titel: 'Selbst wählen', text: 'Jeder wählt die Kategorie für seine eigene Frage.' },
    { id: 'vorgaenger', titel: 'Vorheriger Spieler wählt', text: 'Wer gerade dran war, wählt die Kategorie für den Nächsten.' },
    { id: 'zufall', titel: 'Immer Zufall', text: 'Die Kategorie wird jedes Mal ausgelost.' },
  ];

  // svelte-ignore state_referenced_locally
  const start = letzte;
  let spieler = $state(
    start?.namen.length
      ? start.namen.map((name, i) => ({ name, farbe: start.farben[i] ?? SPIELER_FARBEN[i] }))
      : [{ name: '', farbe: SPIELER_FARBEN[0] }],
  );
  // svelte-ignore state_referenced_locally
  let runden = $state(start?.runden ?? RUNDEN_STANDARD);
  // svelte-ignore state_referenced_locally
  const startEinst = einstellungenPruefen(start ?? undefined, MAX_SPIELER);
  let modus = $state<KategorieModus>(startEinst.modus);
  let kategorien = $state<KategorieId[]>(startEinst.kategorien);

  // „Vorheriger Spieler“ braucht mindestens 2 Spieler
  const modusEffektiv = $derived<KategorieModus>(modus === 'vorgaenger' && spieler.length < 2 ? 'selbst' : modus);
  const alle = $derived(kategorien.length === ALLE_KATEGORIEN.length);
  const fragenGewaehlt = $derived(kategorien.reduce((n, k) => n + (gesamt[k] ?? 0), 0));

  function umschalten(id: KategorieId) {
    kategorien = kategorien.includes(id)
      ? kategorien.filter((k) => k !== id)
      : ALLE_KATEGORIEN.filter((k) => k === id || kategorien.includes(k));
  }

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
    if (doppelt || fragenGewaehlt === 0) return;
    onStart(
      spieler.map((p, i) => ({ name: namen[i], farbe: p.farbe })),
      runden,
      { modus: modusEffektiv, kategorien: [...kategorien] },
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

  <section class="karte" aria-labelledby="modus-titel">
    <h2 id="modus-titel">Kategorie-Wahl</h2>
    <div class="modi" role="radiogroup" aria-labelledby="modus-titel">
      {#each MODI as m (m.id)}
        {@const gesperrt = m.id === 'vorgaenger' && spieler.length < 2}
        <button
          type="button"
          role="radio"
          class="modus"
          aria-checked={modusEffektiv === m.id}
          class:aktiv={modusEffektiv === m.id}
          disabled={gesperrt}
          onclick={() => (modus = m.id)}
        >
          <span class="modus-titel">{m.titel}</span>
          <span class="modus-text">{gesperrt ? 'Ab 2 Spielern möglich.' : m.text}</span>
        </button>
      {/each}
    </div>
  </section>

  <section class="karte" aria-labelledby="kategorien-titel">
    <div class="kopfzeile">
      <h2 id="kategorien-titel">Kategorien</h2>
      <button
        type="button"
        class="textlink alle"
        onclick={() => (kategorien = alle ? [] : [...ALLE_KATEGORIEN])}
      >
        {alle ? 'Keine' : 'Alle'}
      </button>
    </div>
    <p class="muted klein-text">Mit allen spielen oder nur mit einer Auswahl.</p>
    <div class="kategorien" role="group" aria-labelledby="kategorien-titel">
      {#each KATEGORIEN as k (k.id)}
        {@const an = kategorien.includes(k.id)}
        <button
          type="button"
          class="kat"
          class:an
          style:--kf={k.farbe}
          style:--kt={k.text}
          aria-pressed={an}
          onclick={() => umschalten(k.id)}
        >
          <span class="kat-icon" aria-hidden="true">{k.icon}</span>
          <span class="haken" aria-hidden="true">{an ? '✓' : ''}</span>
          <span class="kat-name">{k.name}</span>
          <span class="kat-anzahl">{gesamt[k.id] ? `${gesamt[k.id]} Fragen` : 'bald verfügbar'}</span>
        </button>
      {/each}
    </div>
    {#if kategorien.length === 0}
      <p class="fehler" role="alert">Bitte mindestens eine Kategorie wählen.</p>
    {:else if fragenGewaehlt === 0}
      <p class="fehler" role="alert">Für die gewählten Kategorien gibt es noch keine Fragen.</p>
    {/if}
  </section>

  <div class="unten">
    <button class="btn" type="submit" disabled={doppelt || fragenGewaehlt === 0}>Spiel starten</button>
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
  .modi {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .modus {
    min-height: 52px;
    border-radius: 12px;
    border: 2px solid var(--line);
    background: var(--bg);
    padding: 10px 14px;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    text-align: left;
  }
  .modus.aktiv {
    border-color: var(--accent);
    box-shadow: inset 0 0 0 1px var(--accent);
  }
  .modus.aktiv .modus-titel::before {
    content: '✓ ';
    color: var(--accent);
  }
  .modus:disabled {
    opacity: 0.5;
  }
  .modus-titel {
    font-weight: 700;
  }
  .modus-text {
    font-size: 0.9rem;
    color: var(--text-2);
  }
  .kopfzeile {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .alle {
    min-height: 48px;
    min-width: 48px;
  }
  .kategorien {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }
  .kat {
    min-height: 88px;
    border-radius: 12px;
    border: 2px solid var(--line);
    background: var(--bg);
    color: var(--text);
    padding: 8px 10px;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    text-align: left;
    line-height: 1.2;
    opacity: 0.6;
    position: relative;
  }
  .haken {
    position: absolute;
    top: 8px;
    right: 10px;
    font-weight: 800;
  }
  .kat.an {
    background: var(--kf);
    color: var(--kt);
    border-color: var(--kf);
    opacity: 1;
  }
  .kat-icon {
    font-size: 1.3rem;
  }
  .kat-name {
    font-weight: 700;
    font-size: 0.95rem;
    overflow-wrap: anywhere;
    hyphens: auto;
  }
  .kat-anzahl {
    font-size: 0.8rem;
    margin-top: auto;
  }
</style>
