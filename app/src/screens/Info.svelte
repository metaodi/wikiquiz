<script lang="ts">
  import { KATEGORIEN } from '../lib/categories';
  import type { Pool } from '../lib/types';

  let { pool, onZurueck }: { pool: Pool | null; onZurueck: () => void } = $props();

  const anzahl = $derived(
    Object.fromEntries(KATEGORIEN.map((k) => [k.id, pool?.fragen.filter((f) => f.kategorie === k.id).length ?? 0])),
  );
  const stand = $derived(
    pool?.generiert_am ? new Date(pool.generiert_am).toLocaleDateString('de-CH', { dateStyle: 'long' }) : null,
  );
</script>

<div class="screen">
  <header class="kopf">
    <button class="textlink" onclick={onZurueck}>← Zurück</button>
  </header>
  <h1>Info</h1>

  <section class="karte">
    <h2>So wird gespielt</h2>
    <p>
      Bis zu 4 Spieler beantworten abwechselnd Fragen auf einem Gerät. Pro Frage gibt es 15 Sekunden. Eine richtige
      Antwort bringt bis zu 100 Punkte – je schneller, desto mehr (mindestens 10). Falsche Antworten und abgelaufene
      Zeit geben 0 Punkte. Jeder Spieler wählt vor dem Start seine Schwierigkeit (leicht, mittel oder schwer); sind
      in einer Kategorie keine Fragen dieser Stufe mehr übrig, kommt die nächstliegende Stufe dran.
    </p>
  </section>

  <section class="karte">
    <h2>Quellen</h2>
    <p>
      Alle Fragen stammen aus der deutschsprachigen
      <a href="https://de.wikipedia.org/" target="_blank" rel="noopener noreferrer">Wikipedia</a> und aus
      <a href="https://www.wikidata.org/" target="_blank" rel="noopener noreferrer">Wikidata</a>, einzelne
      Star-Wars- und Harry-Potter-Fragen aus der
      <a href="https://en.wikipedia.org/" target="_blank" rel="noopener noreferrer">englischsprachigen Wikipedia</a>.
      Nach jeder Frage führt der Link „Mehr auf Wikipedia“ zum Quellartikel.
    </p>
    <ul class="zahlen">
      {#each KATEGORIEN as k (k.id)}
        <li><span aria-hidden="true">{k.icon}</span> {k.name}: {anzahl[k.id]} Fragen</li>
      {/each}
    </ul>
    {#if stand}<p class="muted">Fragenpool vom {stand}.</p>{/if}
  </section>

  <section class="karte">
    <h2>Lizenzen</h2>
    <ul>
      <li>
        Fragen auf Basis von Wikipedia-Artikeln:
        <a href="https://creativecommons.org/licenses/by-sa/4.0/deed.de" target="_blank" rel="noopener noreferrer">CC BY-SA 4.0</a>.
        Die Autorinnen und Autoren sind in der Versionsgeschichte des jeweiligen Artikels aufgeführt.
      </li>
      <li>
        Fragen auf Basis von Wikidata:
        <a href="https://creativecommons.org/publicdomain/zero/1.0/deed.de" target="_blank" rel="noopener noreferrer">CC0 1.0</a>.
      </li>
      <li>Wikipedia und Wikidata sind Marken der Wikimedia Foundation. WikiQuiz ist kein Angebot der Wikimedia Foundation.</li>
    </ul>
  </section>

  <section class="karte">
    <h2>Datenschutz</h2>
    <p>
      WikiQuiz läuft vollständig auf deinem Gerät. Spielstand und zuletzt gestellte Fragen werden nur lokal im Browser
      gespeichert.
    </p>
  </section>

  <p class="muted klein">
    Quellcode: <a href="https://github.com/metaodi/wikiquiz" target="_blank" rel="noopener noreferrer">github.com/metaodi/wikiquiz</a>
  </p>
</div>

<style>
  .kopf {
    min-height: 48px;
  }
  .kopf .textlink {
    padding-left: 0;
    text-decoration: none;
    font-weight: 600;
  }
  h2 {
    font-size: 1.1rem;
    margin-bottom: 8px;
  }
  p {
    margin: 0 0 8px;
  }
  ul {
    margin: 0;
    padding-left: 20px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .zahlen {
    list-style: none;
    padding: 0;
    margin: 8px 0;
  }
  a {
    font-weight: 600;
  }
  .klein {
    font-size: 0.9rem;
  }
</style>
