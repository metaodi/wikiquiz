<script lang="ts">
  import { onDestroy, onMount, untrack } from 'svelte';
  import Kopf from './components/Kopf.svelte';
  import { aktionAnwenden, type Aktion } from './lib/aktionen';
  import * as game from './lib/game';
  import { haptik } from './lib/haptics';
  import { lokalerKanal } from './lib/kanal';
  import { anzahlProKategorie } from './lib/picker';
  import { ladePool } from './lib/pool';
  import * as storage from './lib/storage';
  import type { Einstellungen, Pool, Spielstand } from './lib/types';
  import Feedback from './screens/Feedback.svelte';
  import Frage from './screens/Frage.svelte';
  import Info from './screens/Info.svelte';
  import Kategorie from './screens/Kategorie.svelte';
  import Rangliste from './screens/Rangliste.svelte';
  import Setup from './screens/Setup.svelte';
  import Uebergabe from './screens/Uebergabe.svelte';
  import Zufall from './screens/Zufall.svelte';
  import Zwischenstand from './screens/Zwischenstand.svelte';

  let pool = $state<Pool | null>(null);
  let ladefehler = $state<string | null>(null);
  let spiel = $state<Spielstand | null>(null);
  let infoOffen = $state(false);
  let meldung = $state<string | null>(null);
  let history = storage.ladeHistory();
  let letzte = $state(storage.ladeLetzteSpieler());

  const fragen = $derived(pool?.fragen ?? []);
  const aktuelleFrage = $derived(spiel?.zug ? fragen.find((f) => f.id === spiel!.zug!.frageId) : undefined);
  const gesamt = $derived(anzahlProKategorie(fragen, []));
  const offen = $derived(anzahlProKategorie(fragen, spiel?.gestellt ?? []));
  const offenGewaehlt = $derived(!!spiel && spiel.kategorien.some((k) => offen[k] > 0));
  const letzterZug = $derived(
    !!spiel && spiel.aktiverSpieler === spiel.spieler.length - 1 && spiel.runde >= spiel.runden,
  );

  onMount(() => {
    ladePool()
      .then((p) => {
        pool = p;
        const gespeichert = storage.ladeSpiel();
        if (gespeichert && gespeichert.phase !== 'setup') {
          spiel = game.wiederherstellen(gespeichert, p.fragen, Date.now());
        }
      })
      .catch((e: Error) => (ladefehler = e.message));

    // Beim Zurückkehren in die App sofort prüfen, ob die Zeit abgelaufen ist
    const sichtbar = () => {
      if (document.visibilityState === 'visible') zeitPruefen();
    };
    document.addEventListener('visibilitychange', sichtbar);
    return () => document.removeEventListener('visibilitychange', sichtbar);
  });

  // Spielstand bei jeder Änderung sichern
  $effect(() => {
    if (pool) storage.speichereSpiel(spiel ? $state.snapshot(spiel) : null);
  });

  // Nach jedem Zustandswechsel nach oben scrollen
  $effect(() => {
    void spiel?.phase;
    void infoOffen;
    window.scrollTo(0, 0);
  });

  // Modus „Immer Zufall“: Kategorie ohne Zutun auslosen
  $effect(() => {
    if (spiel?.phase === 'kategorie' && spiel.modus === 'zufall') untrack(() => waehlen('zufall'));
  });

  // Spielzüge laufen als Aktionen über einen Kanal. Heute ist das Gerät zugleich Host: Es empfängt
  // seine eigenen Aktionen und wendet sie an (Pass-and-Play). Siehe docs/ARCHITEKTUR.md.
  const kanal = lokalerKanal();
  kanal.beiEmpfang((n) => {
    if (n.typ === 'aktion') anwenden(n.aktion);
  });
  onDestroy(() => kanal.schliessen());

  function ausfuehren(aktion: Aktion) {
    kanal.senden({ typ: 'aktion', aktion });
  }

  /** Host: Aktion auf den Spielstand anwenden */
  function anwenden(aktion: Aktion) {
    if (!spiel) return;
    const r = aktionAnwenden(spiel, aktion, { pool: fragen, history, jetzt: Date.now() });
    if (r.fehler) {
      // Sind alle Fragen aufgebraucht, zeigt der Kategorie-Screen das Spielende bereits an
      meldung =
        r.fehler === 'alle_erschoepft' ? null : 'In dieser Kategorie gibt es keine Fragen mehr. Bitte wähle eine andere.';
      return;
    }
    if (aktion.typ === 'kategorie') meldung = null;
    if (r.neueFrage) history = storage.merkeFrage(r.neueFrage.id);
    spiel = r.stand;
  }

  function starten(spieler: { name: string; farbe: string }[], runden: number, einstellungen: Einstellungen) {
    letzte = {
      namen: spieler.map((p) => p.name),
      farben: spieler.map((p) => p.farbe),
      runden,
      ...einstellungen,
      bekannteKategorien: [...game.ALLE_KATEGORIEN],
    };
    storage.speichereLetzteSpieler(letzte);
    meldung = null;
    spiel = game.neuesSpiel(spieler, runden, einstellungen);
  }

  function waehlen(wahl: game.Wahl) {
    if (!spiel) return;
    if (spiel.modus !== 'zufall') haptik.tippen();
    ausfuehren({ typ: 'kategorie', wahl });
  }

  function zeitPruefen() {
    ausfuehren({ typ: 'zeitPruefen' });
  }

  function abbrechen() {
    if (confirm('Spiel wirklich beenden? Der Spielstand geht verloren.')) spiel = null;
  }
</script>

{#if ladefehler}
  <div class="screen">
    <h1>Fehler</h1>
    <p>{ladefehler}</p>
    <div class="unten"><button class="btn" onclick={() => location.reload()}>Erneut versuchen</button></div>
  </div>
{:else if !pool}
  <div class="screen"><p class="muted laden">Fragen werden geladen …</p></div>
{:else if infoOffen}
  <Info {pool} onZurueck={() => (infoOffen = false)} />
{:else if !spiel}
  <Setup {letzte} {gesamt} onStart={starten} onInfo={() => (infoOffen = true)} />
{:else if spiel.phase === 'uebergabe'}
  <Uebergabe
    spieler={spiel.spieler[spiel.aktiverSpieler]}
    runde={spiel.runde}
    runden={spiel.runden}
    onBereit={() => ausfuehren({ typ: 'bereit' })}
  />
{:else if spiel.phase === 'zwischenstand'}
  <Zwischenstand {spiel} onWeiter={() => ausfuehren({ typ: 'zwischenstandWeiter' })} />
{:else if spiel.phase === 'rangliste'}
  <Rangliste
    {spiel}
    onNochmals={() => ausfuehren({ typ: 'nochmals' })}
    onNeu={() => (spiel = null)}
  />
{:else}
  <div class="screen">
    <Kopf {spiel} onBeenden={abbrechen} />
    {#if spiel.phase === 'kategorie'}
      <!-- Bei „Immer Zufall“ wird automatisch gelost; der Screen erscheint nur, wenn nichts mehr übrig ist -->
      {#if spiel.modus !== 'zufall' || !offenGewaehlt}
        {@const w = game.waehler(spiel)}
        <Kategorie
          {offen}
          {gesamt}
          {meldung}
          kategorien={spiel.kategorien}
          waehler={w !== spiel.aktiverSpieler ? spiel.spieler[w] : null}
          fuer={spiel.spieler[spiel.aktiverSpieler]}
          onWahl={waehlen}
          onBeenden={() => ausfuehren({ typ: 'beenden' })}
        />
      {/if}
    {:else if spiel.phase === 'zufall' && spiel.zug}
      <Zufall ziel={spiel.zug.kategorie} kategorien={spiel.kategorien} onFertig={() => ausfuehren({ typ: 'zufallFertig' })} />
    {:else if spiel.phase === 'frage' && spiel.zug && aktuelleFrage}
      {#key spiel.zug.frageId}
        <Frage
          frage={aktuelleFrage}
          reihenfolge={spiel.zug.reihenfolge}
          timerStart={spiel.zug.timerStart}
          onTimerStart={() => ausfuehren({ typ: 'timerStarten' })}
          onAntwort={(i) => ausfuehren({ typ: 'antworten', index: i })}
          onTimeout={zeitPruefen}
        />
      {/key}
    {:else if spiel.phase === 'feedback' && spiel.zug && aktuelleFrage}
      <Feedback
        frage={aktuelleFrage}
        zug={spiel.zug}
        spieler={spiel.spieler[spiel.zug.spieler]}
        {letzterZug}
        onWeiter={() => ausfuehren({ typ: 'weiter' })}
      />
    {/if}
  </div>
{/if}

<style>
  .laden {
    margin: auto;
  }
</style>
