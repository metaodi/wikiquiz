<script lang="ts">
  import { KATEGORIEN } from '../lib/categories';
  import { SCHWIERIGKEITEN } from '../lib/config';
  import { proKategoriePruefen } from '../lib/game';
  import type { KategorieId, ProKategorie, Schwierigkeit } from '../lib/types';

  /**
   * Schwierigkeit eines Spielers: Gesamtstufe und (aufklappbar) Abweichungen pro Kategorie.
   * Gespeichert werden nur Abweichungen; ändert sich die Gesamtstufe, fallen solche weg, die ihr nun entsprechen.
   */
  let {
    wert = $bindable(),
    pro = $bindable(),
    kategorien,
    wer = '',
  }: {
    wert: Schwierigkeit;
    pro: ProKategorie;
    /** Kategorien, die zum Verfeinern angeboten werden */
    kategorien: KategorieId[];
    /** Zusatz für die Beschriftungen, z. B. „Spieler 1“ */
    wer?: string;
  } = $props();

  const angepasst = $derived(kategorien.filter((k) => pro[k] !== undefined).length);

  function gesamtSetzen(w: Schwierigkeit) {
    wert = w;
    pro = proKategoriePruefen(pro, w) ?? {};
  }

  function kategorieSetzen(k: KategorieId, w: Schwierigkeit) {
    pro = proKategoriePruefen({ ...pro, [k]: w }, wert) ?? {};
  }
</script>

<div class="wahl">
  <div class="segment" role="radiogroup" aria-label={wer ? `Schwierigkeit ${wer}` : 'Schwierigkeit'}>
    {#each SCHWIERIGKEITEN as st (st.wert)}
      <button
        type="button"
        role="radio"
        aria-checked={wert === st.wert}
        class:aktiv={wert === st.wert}
        onclick={() => gesamtSetzen(st.wert)}
      >
        {st.name}
      </button>
    {/each}
  </div>
  <details class="fein">
    <summary>
      <span>Pro Kategorie anpassen{#if angepasst > 0}<span class="anzahl">{` · ${angepasst} angepasst`}</span>{/if}</span>
    </summary>
    <p class="muted hinweis">Ohne Anpassung gilt die Stufe oben.</p>
    <ul class="liste">
      {#each KATEGORIEN.filter((k) => kategorien.includes(k.id)) as k (k.id)}
        {@const w = pro[k.id] ?? wert}
        <li class="zeile" class:abweichend={pro[k.id] !== undefined}>
          <span class="name"><span aria-hidden="true">{k.icon}</span> {k.name}</span>
          <div class="segment" role="radiogroup" aria-label={`Schwierigkeit ${k.name}${wer ? `, ${wer}` : ''}`}>
            {#each SCHWIERIGKEITEN as st (st.wert)}
              <button
                type="button"
                role="radio"
                aria-checked={w === st.wert}
                class:aktiv={w === st.wert}
                onclick={() => kategorieSetzen(k.id, st.wert)}
              >
                {st.name}
              </button>
            {/each}
          </div>
        </li>
      {/each}
    </ul>
    {#if angepasst > 0}
      <button type="button" class="textlink zuruecksetzen" onclick={() => (pro = {})}>Alle wie oben</button>
    {/if}
  </details>
</div>

<style>
  .wahl {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .segment {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
  }
  .segment button {
    min-height: 48px;
    border-radius: 12px;
    border: 2px solid var(--line);
    background: var(--bg);
    font-weight: 700;
    font-size: 1rem;
  }
  .segment button.aktiv {
    background: var(--accent);
    color: var(--accent-text);
    border-color: var(--accent);
  }
  summary {
    min-height: 48px;
    display: flex;
    align-items: center;
    cursor: pointer;
    font-weight: 600;
    color: var(--text-2);
  }
  summary::before {
    content: '▸';
    margin-right: 6px;
  }
  .fein[open] summary::before {
    content: '▾';
  }
  .anzahl {
    color: var(--accent);
  }
  .hinweis {
    margin: 0 0 10px;
    font-size: 0.95rem;
  }
  .liste {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .zeile {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding-left: 8px;
    border-left: 3px solid transparent;
  }
  .zeile.abweichend {
    border-left-color: var(--accent);
  }
  .name {
    font-size: 0.95rem;
    overflow-wrap: anywhere;
  }
  .zuruecksetzen {
    min-height: 48px;
    align-self: flex-start;
  }
</style>
