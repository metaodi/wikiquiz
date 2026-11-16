<script lang="ts">
  import { onDestroy, onMount, untrack } from 'svelte';
  import Kopf from './components/Kopf.svelte';
  import { aktionAnwenden, type Aktion } from './lib/aktionen';
  import { SPIELER_FARBEN, ZEITLIMIT_S } from './lib/config';
  import * as game from './lib/game';
  import { haptik } from './lib/haptics';
  import { broadcastKanal, lokalerKanal, type Kanal, type Nachricht } from './lib/kanal';
  import { anzahlProKategorie } from './lib/picker';
  import { ladePool } from './lib/pool';
  import {
    BEITRITTS_FEHLER,
    beitreten,
    darf,
    HOST,
    verlassen,
    zufallsCode,
    zustaendig,
    type Teilnehmer,
  } from './lib/raum';
  import * as storage from './lib/storage';
  import type { Einstellungen, Pool, Spielstand } from './lib/types';
  import Feedback from './screens/Feedback.svelte';
  import Frage from './screens/Frage.svelte';
  import Info from './screens/Info.svelte';
  import Kategorie from './screens/Kategorie.svelte';
  import Lobby from './screens/Lobby.svelte';
  import Rangliste from './screens/Rangliste.svelte';
  import RaumStart from './screens/RaumStart.svelte';
  import Setup from './screens/Setup.svelte';
  import Uebergabe from './screens/Uebergabe.svelte';
  import Warten from './screens/Warten.svelte';
  import Zufall from './screens/Zufall.svelte';
  import Zwischenstand from './screens/Zwischenstand.svelte';

  /** Mehrere Geräte sind eine Vorschau und nur mit `?mehrgeraete` in der URL sichtbar (siehe app/README.md) */
  const mehrgeraeteSichtbar = new URLSearchParams(location.search).has('mehrgeraete');

  interface Raum {
    code: string;
    rolle: 'host' | 'gast';
    name: string;
    teilnehmer: Teilnehmer[];
    /** Gerät des Hosts (bei Gästen bekannt, sobald der erste Spielstand eintrifft) */
    hostGeraet: string | null;
  }

  let pool = $state<Pool | null>(null);
  let ladefehler = $state<string | null>(null);
  let spiel = $state<Spielstand | null>(null);
  let infoOffen = $state(false);
  let meldung = $state<string | null>(null);
  let history = storage.ladeHistory();
  let letzte = $state(storage.ladeLetzteSpieler());
  let raum = $state<Raum | null>(null);
  let raumStartOffen = $state(false);
  let raumFehler = $state<string | null>(null);
  const geraet = storage.geraetId(() => zufallsCode(Math.random, 12));

  const fragen = $derived(pool?.fragen ?? []);
  const phase = $derived(spiel?.phase);
  const aktuelleFrage = $derived(spiel?.zug ? fragen.find((f) => f.id === spiel!.zug!.frageId) : undefined);
  const gesamt = $derived(anzahlProKategorie(fragen, []));
  const offen = $derived(anzahlProKategorie(fragen, spiel?.gestellt ?? []));
  const offenGewaehlt = $derived(!!spiel && spiel.kategorien.some((k) => offen[k] > 0));
  const letzterZug = $derived(
    !!spiel && spiel.aktiverSpieler === spiel.spieler.length - 1 && spiel.runde >= spiel.runden,
  );

  // Mehrere Geräte: Wer bin ich, und bediene ich die aktuelle Phase?
  const istGast = $derived(raum?.rolle === 'gast');
  const ich = $derived(raum ? raum.teilnehmer.findIndex((t) => t.geraet === geraet) : -1);
  const amZug = $derived.by(() => {
    if (!raum || !spiel) return true;
    const z = zustaendig(spiel);
    return z === HOST ? !istGast : z === ich;
  });
  const hostName = $derived(raum?.teilnehmer[0]?.name ?? '');

  // Spielzüge laufen als Aktionen über einen Kanal. Ohne Raum ist das Gerät zugleich Host und empfängt
  // seine eigenen Aktionen (Pass-and-Play); im Raum wendet nur der Host Aktionen an. Siehe docs/ARCHITEKTUR.md.
  let kanal: Kanal = lokalerKanal();
  let abmelden = kanal.beiEmpfang(empfangen);
  let halloTimer: ReturnType<typeof setInterval> | undefined;

  function kanalWechseln(neu: Kanal) {
    abmelden();
    kanal.schliessen();
    kanal = neu;
    abmelden = kanal.beiEmpfang(empfangen);
  }

  onDestroy(() => {
    clearInterval(halloTimer);
    kanal.schliessen();
  });

  onMount(() => {
    ladePool()
      .then((p) => {
        pool = p;
        const sitzung = storage.ladeRaum();
        if (sitzung) {
          raumWiederaufnehmen(sitzung, p);
          return;
        }
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

  // Spielstand bei jeder Änderung sichern; der Host eines Raums verteilt ihn zusätzlich an alle Geräte
  $effect(() => {
    if (!pool || istGast) return;
    if (!raum) {
      storage.speichereSpiel(spiel ? $state.snapshot(spiel) : null);
      return;
    }
    const n = standNachricht();
    storage.speichereRaum({ code: raum.code, rolle: 'host', name: raum.name, teilnehmer: n.teilnehmer, spiel: n.stand });
    untrack(() => kanal.senden(n));
  });

  // Host: Zeitablauf selbst überwachen – auch wenn das Gerät des Spielers nicht mehr antwortet
  $effect(() => {
    if (!raum || istGast || spiel?.phase !== 'frage' || !spiel.zug || spiel.zug.timerStart === null) return;
    const ms = spiel.zug.timerStart + ZEITLIMIT_S * 1000 - Date.now() + 50;
    const t = setTimeout(() => ausfuehren({ typ: 'zeitPruefen' }), Math.max(0, ms));
    return () => clearTimeout(t);
  });

  // Nach jedem Zustandswechsel nach oben scrollen
  $effect(() => {
    void phase;
    void infoOffen;
    void raumStartOffen;
    window.scrollTo(0, 0);
  });

  // Modus „Immer Zufall“: Kategorie ohne Zutun auslosen (bei mehreren Geräten das Gerät, das dran ist)
  $effect(() => {
    if (phase === 'kategorie' && spiel?.modus === 'zufall' && amZug) untrack(() => waehlen('zufall'));
  });

  function ausfuehren(aktion: Aktion) {
    kanal.senden({ typ: 'aktion', von: geraet, aktion });
  }

  /** Host: Aktion auf den Spielstand anwenden */
  function anwenden(von: string, aktion: Aktion) {
    if (!spiel) return;
    if (raum && !darf(spiel, raum.teilnehmer, geraet, von, aktion)) return;
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

  function empfangen(n: Nachricht) {
    if (!raum) {
      if (n.typ === 'aktion') anwenden(n.von, n.aktion);
      return;
    }
    if (raum.rolle === 'host') {
      if (n.typ === 'aktion') anwenden(n.von, n.aktion);
      else if (n.von === geraet) return; // eigene Nachrichten
      else if (n.typ === 'hallo') gastBegruessen(n.von, n.name);
      else if (n.typ === 'tschuess' && !spiel) raum.teilnehmer = verlassen(raum.teilnehmer, n.von);
      return;
    }
    // Gast
    if (n.typ === 'stand' && n.von !== geraet && n.teilnehmer.some((t) => t.geraet === geraet)) {
      raum.hostGeraet = n.von;
      raum.teilnehmer = n.teilnehmer;
      spiel = n.stand;
      meldung = n.meldung;
    } else if (n.typ === 'abgelehnt' && n.an === geraet) {
      raumVerlassen(n.grund);
    } else if (n.typ === 'tschuess' && n.von === raum.hostGeraet) {
      raumVerlassen('Der Raum wurde geschlossen.');
    }
  }

  function standNachricht(): Extract<Nachricht, { typ: 'stand' }> {
    return {
      typ: 'stand',
      von: geraet,
      stand: spiel ? $state.snapshot(spiel) : null,
      teilnehmer: $state.snapshot(raum?.teilnehmer ?? []),
      meldung,
    };
  }

  /** Host: Gast aufnehmen (oder nach Neuladen wieder begrüssen) */
  function gastBegruessen(von: string, name: string) {
    if (!raum) return;
    const r = beitreten(raum.teilnehmer, von, name, spiel !== null);
    if (!r.ok) {
      kanal.senden({ typ: 'abgelehnt', von: geraet, an: von, grund: BEITRITTS_FEHLER[r.fehler] });
      return;
    }
    raum.teilnehmer = r.teilnehmer;
    // Auch ohne Änderung antworten (der Gast hat nach dem Neuladen keinen Spielstand)
    kanal.senden(standNachricht());
  }

  function raumEroeffnen(name: string) {
    const code = zufallsCode(Math.random);
    const farbe = letzte?.farben[0] ?? SPIELER_FARBEN[0];
    raum = { code, rolle: 'host', name, teilnehmer: [{ geraet, name, farbe }], hostGeraet: geraet };
    spiel = null;
    meldung = null;
    raumFehler = null;
    raumStartOffen = false;
    kanalWechseln(broadcastKanal(code));
  }

  function raumBeitreten(code: string, name: string) {
    raum = { code, rolle: 'gast', name, teilnehmer: [], hostGeraet: null };
    spiel = null;
    meldung = null;
    raumFehler = null;
    raumStartOffen = false;
    storage.speichereRaum({ code, rolle: 'gast', name });
    kanalWechseln(broadcastKanal(code));
    halloStarten();
  }

  /** Nach dem Neuladen: dem Raum wieder beitreten bzw. ihn als Host weiterführen */
  function raumWiederaufnehmen(s: storage.RaumSitzung, p: Pool) {
    raum = {
      code: s.code,
      rolle: s.rolle,
      name: s.name,
      teilnehmer: s.teilnehmer ?? [],
      hostGeraet: s.rolle === 'host' ? geraet : null,
    };
    if (s.rolle === 'host' && s.spiel) spiel = game.wiederherstellen(s.spiel, p.fragen, Date.now());
    kanalWechseln(broadcastKanal(s.code));
    if (s.rolle === 'gast') halloStarten();
  }

  /** Gast: so lange anklopfen, bis der Host antwortet */
  function halloStarten() {
    const hallo = () => {
      if (raum?.rolle === 'gast' && ich < 0) kanal.senden({ typ: 'hallo', von: geraet, name: raum.name });
    };
    clearInterval(halloTimer);
    hallo();
    halloTimer = setInterval(hallo, 2000);
  }

  /** Raum verlassen (Gast) bzw. schliessen (Host); mit `fehler` zurück zum Raum-Einstieg */
  function raumVerlassen(fehler?: string) {
    if (!raum) return;
    kanal.senden({ typ: 'tschuess', von: geraet });
    clearInterval(halloTimer);
    kanalWechseln(lokalerKanal());
    storage.speichereRaum(null);
    raum = null;
    spiel = null;
    meldung = null;
    raumFehler = fehler ?? null;
    raumStartOffen = !!fehler;
  }

  function starten(spieler: { name: string; farbe: string }[], runden: number, einstellungen: Einstellungen) {
    letzte = {
      // Im Raum stammen die Spieler von den Geräten – die Namen fürs Spiel auf einem Gerät bleiben
      namen: raum ? (letzte?.namen ?? []) : spieler.map((p) => p.name),
      farben: raum ? (letzte?.farben ?? []) : spieler.map((p) => p.farbe),
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

  function zurUebersicht() {
    spiel = null;
    meldung = null;
  }

  function abbrechen() {
    if (istGast) {
      if (confirm('Raum verlassen? Ohne dich kann das Spiel nicht weitergehen.')) raumVerlassen();
    } else if (confirm(raum ? 'Spiel für alle beenden?' : 'Spiel wirklich beenden? Der Spielstand geht verloren.')) {
      zurUebersicht();
    }
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
{:else if raumStartOffen}
  <RaumStart
    name={letzte?.namen[0] ?? ''}
    fehler={raumFehler}
    onEroeffnen={raumEroeffnen}
    onBeitreten={raumBeitreten}
    onZurueck={() => {
      raumStartOffen = false;
      raumFehler = null;
    }}
  />
{:else if !spiel}
  {#if raum && istGast}
    <Lobby code={raum.code} teilnehmer={raum.teilnehmer} ich={geraet} onVerlassen={() => raumVerlassen()} />
  {:else}
    <Setup
      {letzte}
      {gesamt}
      onStart={starten}
      onInfo={() => (infoOffen = true)}
      raum={raum ? { code: raum.code, teilnehmer: raum.teilnehmer, ich: geraet } : undefined}
      onMehrgeraete={mehrgeraeteSichtbar && !raum ? () => (raumStartOffen = true) : undefined}
      onRaumSchliessen={() => raumVerlassen()}
    />
  {/if}
{:else if spiel.phase === 'uebergabe'}
  {@const aktiv = spiel.spieler[spiel.aktiverSpieler]}
  {#if amZug}
    <Uebergabe
      spieler={aktiv}
      runde={spiel.runde}
      runden={spiel.runden}
      eigenesGeraet={!!raum}
      onBereit={() => ausfuehren({ typ: 'bereit' })}
    />
  {:else}
    <div class="screen">
      <Kopf {spiel} onBeenden={abbrechen} />
      <Warten spieler={aktiv} text={`${aktiv.name} ist dran`} hinweis={`Runde ${spiel.runde} von ${spiel.runden}`} />
    </div>
  {/if}
{:else if spiel.phase === 'zwischenstand'}
  <Zwischenstand
    {spiel}
    onWeiter={amZug ? () => ausfuehren({ typ: 'zwischenstandWeiter' }) : undefined}
    warteText={`Warte auf ${hostName} …`}
  />
{:else if spiel.phase === 'rangliste'}
  <Rangliste
    {spiel}
    onNochmals={amZug ? () => ausfuehren({ typ: 'nochmals' }) : undefined}
    onNeu={istGast ? () => raumVerlassen() : zurUebersicht}
    neuText={istGast ? 'Raum verlassen' : raum ? 'Zurück zum Raum' : 'Neues Spiel'}
    warteText={`Warte auf ${hostName} …`}
  />
{:else}
  {@const aktiv = spiel.spieler[spiel.aktiverSpieler]}
  <div class="screen">
    <Kopf {spiel} onBeenden={abbrechen} />
    {#if spiel.phase === 'kategorie'}
      {@const w = game.waehler(spiel)}
      {#if !amZug}
        <Warten
          spieler={spiel.spieler[w]}
          text={spiel.modus === 'zufall'
            ? `Kategorie für ${aktiv.name} wird ausgelost …`
            : w !== spiel.aktiverSpieler
              ? `${spiel.spieler[w].name} wählt eine Kategorie für ${aktiv.name}`
              : `${aktiv.name} wählt eine Kategorie`}
        />
      {:else if spiel.modus !== 'zufall' || !offenGewaehlt}
        <!-- Bei „Immer Zufall“ wird automatisch gelost; der Screen erscheint nur, wenn nichts mehr übrig ist -->
        <Kategorie
          {offen}
          {gesamt}
          {meldung}
          kategorien={spiel.kategorien}
          waehler={w !== spiel.aktiverSpieler ? spiel.spieler[w] : null}
          fuer={aktiv}
          onWahl={waehlen}
          onBeenden={() => ausfuehren({ typ: 'beenden' })}
        />
      {/if}
    {:else if spiel.phase === 'zufall' && spiel.zug}
      <Zufall
        ziel={spiel.zug.kategorie}
        kategorien={spiel.kategorien}
        onFertig={() => {
          if (amZug) ausfuehren({ typ: 'zufallFertig' });
        }}
      />
    {:else if spiel.phase === 'frage' && spiel.zug && aktuelleFrage}
      {#key spiel.zug.frageId}
        <Frage
          frage={aktuelleFrage}
          reihenfolge={spiel.zug.reihenfolge}
          timerStart={spiel.zug.timerStart}
          zuschauen={!amZug}
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
        onWeiter={amZug ? () => ausfuehren({ typ: 'weiter' }) : undefined}
        warteText={`Warte auf ${spiel.spieler[spiel.zug.spieler].name} …`}
      />
    {/if}
  </div>
{/if}

<style>
  .laden {
    margin: auto;
  }
</style>
