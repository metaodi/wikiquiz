<script lang="ts">
  import { onMount, untrack } from 'svelte';
  import Kopf from './components/Kopf.svelte';
  import * as game from './lib/game';
  import { haptik } from './lib/haptics';
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

  function setzen(neu: Spielstand) {
    spiel = neu;
  }

  function starten(spieler: { name: string; farbe: string }[], runden: number, einstellungen: Einstellungen) {
    letzte = { namen: spieler.map((p) => p.name), farben: spieler.map((p) => p.farbe), runden, ...einstellungen };
    storage.speichereLetzteSpieler(letzte);
    meldung = null;
    setzen(game.neuesSpiel(spieler, runden, einstellungen));
  }

  function waehlen(wahl: game.Wahl) {
    if (!spiel) return;
    if (spiel.modus !== 'zufall') haptik.tippen();
    const r = game.kategorieWaehlen(spiel, fragen, wahl, history);
    if (!r.ok) {
      // Sind alle Fragen aufgebraucht, zeigt der Kategorie-Screen das Spielende bereits an
      meldung =
        r.grund === 'alle_erschoepft' ? null : 'In dieser Kategorie gibt es keine Fragen mehr. Bitte wähle eine andere.';
      return;
    }
    meldung = null;
    history = storage.merkeFrage(r.frage.id);
    setzen(r.stand);
  }

  function zeitPruefen() {
    if (spiel && aktuelleFrage) setzen(game.pruefeTimeout(spiel, aktuelleFrage, Date.now()));
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
    onBereit={() => setzen(game.bereit(spiel!))}
  />
{:else if spiel.phase === 'zwischenstand'}
  <Zwischenstand {spiel} onWeiter={() => setzen(game.zwischenstandWeiter(spiel!))} />
{:else if spiel.phase === 'rangliste'}
  <Rangliste
    {spiel}
    onNochmals={() => setzen(game.nochmals(spiel!))}
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
          onBeenden={() => setzen(game.beenden(spiel!))}
        />
      {/if}
    {:else if spiel.phase === 'zufall' && spiel.zug}
      <Zufall ziel={spiel.zug.kategorie} kategorien={spiel.kategorien} onFertig={() => setzen(game.zufallFertig(spiel!))} />
    {:else if spiel.phase === 'frage' && spiel.zug && aktuelleFrage}
      {#key spiel.zug.frageId}
        <Frage
          frage={aktuelleFrage}
          reihenfolge={spiel.zug.reihenfolge}
          timerStart={spiel.zug.timerStart}
          onTimerStart={() => setzen(game.timerStarten(spiel!, Date.now()))}
          onAntwort={(i) => setzen(game.antworten(spiel!, aktuelleFrage!, i, Date.now()))}
          onTimeout={zeitPruefen}
        />
      {/key}
    {:else if spiel.phase === 'feedback' && spiel.zug && aktuelleFrage}
      <Feedback
        frage={aktuelleFrage}
        zug={spiel.zug}
        spieler={spiel.spieler[spiel.zug.spieler]}
        {letzterZug}
        onWeiter={() => setzen(game.weiter(spiel!))}
      />
    {/if}
  </div>
{/if}

<style>
  .laden {
    margin: auto;
  }
</style>
