<script lang="ts">
  import { KATEGORIEN, KATEGORIE_MAP } from '../lib/categories';
  import type { Wahl } from '../lib/game';
  import type { KategorieId, Spieler } from '../lib/types';

  let {
    offen,
    gesamt,
    meldung,
    kategorien,
    waehler,
    fuer,
    onWahl,
    onBeenden,
  }: {
    /** Noch verfügbare Fragen pro Kategorie in diesem Spiel */
    offen: Record<KategorieId, number>;
    /** Fragen pro Kategorie im ganzen Pool */
    gesamt: Record<KategorieId, number>;
    meldung: string | null;
    /** Kategorien, mit denen gespielt wird */
    kategorien: KategorieId[];
    /** Wählt jemand anderes für den aktiven Spieler (Modus „Vorheriger Spieler“)? */
    waehler: Spieler | null;
    /** Spieler, der die Frage beantwortet */
    fuer: Spieler;
    onWahl: (w: Wahl) => void;
    onBeenden: () => void;
  } = $props();

  const sichtbar = $derived(KATEGORIEN.filter((k) => kategorien.includes(k.id)));
  const irgendwas = $derived(sichtbar.some((k) => offen[k.id] > 0));
  let hinweis = $state<string | null>(null);
  const anzeige = $derived(hinweis ?? meldung);

  function waehlen(id: KategorieId) {
    if (offen[id] > 0) {
      hinweis = null;
      onWahl(id);
      return;
    }
    const name = KATEGORIE_MAP[id].name;
    hinweis =
      gesamt[id] === 0
        ? `Für „${name}“ gibt es noch keine Fragen. Bitte wähle eine andere Kategorie.`
        : `Alle Fragen aus „${name}“ wurden in diesem Spiel schon gestellt. Bitte wähle eine andere Kategorie.`;
  }
</script>

{#if waehler}
  <h1 class="titel">Kategorie für <span style:color={fuer.farbe}>{fuer.name}</span></h1>
  <p class="muted untertitel">
    <strong style:color={waehler.farbe}>{waehler.name}</strong> wählt – danach geht das Gerät an {fuer.name}.
  </p>
{:else}
  <h1 class="titel">Wähle eine Kategorie</h1>
{/if}

{#if anzeige}
  <p class="hinweis" role="alert">{anzeige}</p>
{/if}

{#if irgendwas}
  <div class="raster">
    {#each sichtbar as k (k.id)}
      {@const leer = offen[k.id] === 0}
      <button
        class="kat"
        class:leer
        style:--kf={k.farbe}
        style:--kt={k.text}
        aria-disabled={leer}
        onclick={() => waehlen(k.id)}
      >
        <span class="icon" aria-hidden="true">{k.icon}</span>
        <span class="name">{k.name}</span>
        {#if leer}
          <span class="status">{gesamt[k.id] === 0 ? 'bald verfügbar' : 'keine Fragen mehr'}</span>
        {/if}
      </button>
    {/each}
    <button class="kat zufall" onclick={() => onWahl('zufall')}>
      <span class="icon" aria-hidden="true">🎲</span>
      <span class="name">Zufall</span>
    </button>
  </div>
{:else}
  <div class="karte">
    <p>Es sind keine Fragen mehr übrig. Das Spiel endet hier.</p>
  </div>
  <div class="unten">
    <button class="btn" onclick={onBeenden}>Zur Rangliste</button>
  </div>
{/if}

<style>
  .titel {
    font-size: 1.4rem;
    overflow-wrap: anywhere;
  }
  .untertitel {
    margin: -8px 0 0;
    overflow-wrap: anywhere;
  }
  .raster {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
    margin-top: auto;
  }
  .kat {
    min-height: 104px;
    border: 0;
    border-radius: var(--radius);
    background: var(--kf);
    color: var(--kt);
    padding: 12px;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    justify-content: space-between;
    text-align: left;
    gap: 6px;
    box-shadow: var(--shadow);
    font-weight: 700;
    line-height: 1.2;
    transition: transform 0.08s ease;
  }
  .kat:active {
    transform: scale(0.97);
  }
  .kat.leer {
    filter: grayscale(1);
    opacity: 0.5;
  }
  .icon {
    font-size: 1.8rem;
  }
  .name {
    overflow-wrap: anywhere;
    hyphens: auto;
  }
  .status {
    font-size: 0.8rem;
    font-weight: 600;
  }
  .zufall {
    grid-column: 1 / -1;
    min-height: 72px;
    flex-direction: row;
    align-items: center;
    justify-content: center;
    font-size: 1.2rem;
    background: linear-gradient(90deg, #1565c0, #8e24aa, #e65100, #2e7d32);
    color: #fff;
  }
  .hinweis {
    margin: 0;
    padding: 12px 14px;
    border-radius: 12px;
    background: var(--bad-bg);
    color: var(--text);
    border-left: 4px solid var(--bad);
  }
</style>
