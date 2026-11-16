<script lang="ts">
  import { onDestroy, onMount, untrack } from 'svelte';
  import Kopf from './components/Kopf.svelte';
  import NetzDiagnose from './components/NetzDiagnose.svelte';
  import { aktionAnwenden, type Aktion } from './lib/aktionen';
  import { NETZ_TOLERANZ_S, RUNDEN_STANDARD, SCHWIERIGKEIT_STANDARD, SPIELER_FARBEN, ZEITLIMIT_S } from './lib/config';
  import * as game from './lib/game';
  import { haptik } from './lib/haptics';
  import { broadcastKanal, lokalerKanal, netzKanal, type Kanal, type Nachricht, type NetzStatus } from './lib/kanal';
  import { anzahlProKategorie } from './lib/picker';
  import { ladePool, poolKennung } from './lib/pool';
  import {
    ALLE,
    BEITRITTS_FEHLER,
    beitreten,
    CODE_LAENGE,
    codeNormalisieren,
    darf,
    HOST,
    verlassen,
    zufallsCode,
    stufenWahlPruefen,
    zustaendig,
    type Teilnehmer,
  } from './lib/raum';
  import * as storage from './lib/storage';
  import type { Einstellungen, Pool, Spielstand, StufenWahl } from './lib/types';
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

  /**
   * Übertragungsweg für Räume: WebRTC über das Internet; `?kanal=tabs` verbindet stattdessen Tabs im selben Browser
   * (E2E-Tests und Entwicklung, ohne Netzwerk).
   */
  const kanalArt: storage.KanalArt = new URLSearchParams(location.search).get('kanal') === 'tabs' ? 'tabs' : 'netz';
  const TOLERANZ_MS = NETZ_TOLERANZ_S * 1000;

  interface Raum {
    code: string;
    rolle: 'host' | 'gast';
    kanal: storage.KanalArt;
    name: string;
    /** Eigene Schwierigkeitswahl dieses Geräts */
    wahl: StufenWahl;
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
  /** Raumcode aus einem Beitrittslink (`?raum=…`), vorausgefüllt im Raum-Einstieg */
  let linkCode = $state('');
  /** Gast: geschätzter Unterschied Host-Uhr minus eigene Uhr (ms) */
  let versatz = $state(0);
  let versatzBekannt = false;
  /** Netz: Anzahl verbundener anderer Geräte (null = nicht bekannt, z. B. Tabs) */
  let verbindungen = $state<number | null>(null);
  /** Netz: Zustand der Verbindung für die Diagnose-Anzeige */
  let netzStatus = $state<NetzStatus | null>(null);
  const geraet = storage.geraetId(() => zufallsCode(Math.random, 12));

  const fragen = $derived(pool?.fragen ?? []);
  const phase = $derived(spiel?.phase);
  const aktuelleFrage = $derived(spiel?.zug ? fragen.find((f) => f.id === spiel!.zug!.frageId) : undefined);
  const gesamt = $derived(anzahlProKategorie(fragen, []));
  const offen = $derived(anzahlProKategorie(fragen, spiel?.gestellt ?? []));
  const offenGewaehlt = $derived(!!spiel && spiel.kategorien.some((k) => offen[k] > 0));
  const gleichzeitig = $derived(spiel?.ablauf === 'gleichzeitig');
  const letzterZug = $derived(
    !!spiel && (gleichzeitig || spiel.aktiverSpieler === spiel.spieler.length - 1) && spiel.runde >= spiel.runden,
  );

  // Mehrere Geräte: Wer bin ich, und bediene ich die aktuelle Phase?
  const istGast = $derived(raum?.rolle === 'gast');
  const ich = $derived(raum ? raum.teilnehmer.findIndex((t) => t.geraet === geraet) : -1);
  const amZug = $derived.by(() => {
    if (!raum || !spiel) return true;
    const z = zustaendig(spiel);
    if (z === ALLE) return ich >= 0;
    return z === HOST ? !istGast : z === ich;
  });
  const hostName = $derived(raum?.teilnehmer[0]?.name ?? '');
  /** „Alle gleichzeitig“: der eigene Spieler (für Kopfzeile, Antwort und Ergebnis) */
  const ichSpieler = $derived(gleichzeitig && spiel && ich >= 0 ? spiel.spieler[ich] : undefined);
  const eigeneAntwort = $derived(ich >= 0 ? (spiel?.zug?.alle?.[ich] ?? null) : null);
  const beantwortet = $derived(spiel?.zug?.alle?.filter((a) => a !== null).length ?? 0);
  const fragenKennung = $derived(pool ? poolKennung(pool) : '');
  const verbindungWeg = $derived(!!raum && verbindungen === 0 && (spiel !== null || (istGast && ich >= 0)));

  // Spielzüge laufen als Aktionen über einen Kanal. Ohne Raum ist das Gerät zugleich Host und empfängt
  // seine eigenen Aktionen (Pass-and-Play); im Raum wendet nur der Host Aktionen an. Siehe docs/ARCHITEKTUR.md.
  let kanal: Kanal = lokalerKanal();
  let abmelden = kanal.beiEmpfang(empfangen);
  let halloTimer: ReturnType<typeof setInterval> | undefined;

  function kanalWechseln(neu: Kanal) {
    abmelden();
    kanal.schliessen();
    kanal = neu;
    const empfangAb = kanal.beiEmpfang(empfangen);
    const verbindungAb = kanal.beiVerbindung?.(verbindungGeaendert);
    netzStatus = null;
    const statusAb = kanal.beiStatus?.((s) => (netzStatus = s));
    abmelden = () => {
      empfangAb();
      verbindungAb?.();
      statusAb?.();
    };
    verbindungen = kanal.beiVerbindung ? 0 : null;
  }

  function raumKanal(code: string, art: storage.KanalArt): Kanal {
    return art === 'tabs' ? broadcastKanal(code) : netzKanal(code);
  }

  /** Netz: Ein Gerät ist (wieder) verbunden → Host schickt den Stand, ein wartender Gast klopft an */
  function verbindungGeaendert(anzahl: number, neu: boolean) {
    verbindungen = anzahl;
    if (!neu || !raum) return;
    if (raum.rolle === 'host') kanal.senden(standNachricht());
    else halloSenden();
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
        // Beitrittslink …/?raum=CODE: Raum-Einstieg mit vorausgefülltem Code; Parameter aus der Adresse entfernen
        const url = new URL(location.href);
        const code = codeNormalisieren(url.searchParams.get('raum') ?? '');
        if (url.searchParams.has('raum')) {
          url.searchParams.delete('raum');
          window.history.replaceState(window.history.state, '', url);
        }
        if (code.length === CODE_LAENGE) {
          linkCode = code;
          raumStartOffen = true;
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
    storage.speichereRaum({
      code: raum.code,
      rolle: 'host',
      kanal: raum.kanal,
      name: raum.name,
      wahl: $state.snapshot(raum.wahl),
      teilnehmer: n.teilnehmer,
      spiel: n.stand,
    });
    untrack(() => kanal.senden(n));
  });

  // Host: Zeitablauf selbst überwachen – auch wenn das Gerät des Spielers nicht mehr antwortet.
  // Mit Toleranz, damit unterwegs befindliche Antworten noch zählen.
  $effect(() => {
    if (!raum || istGast || spiel?.phase !== 'frage' || !spiel.zug || spiel.zug.timerStart === null) return;
    const ms = spiel.zug.timerStart + ZEITLIMIT_S * 1000 + TOLERANZ_MS - Date.now() + 50;
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

  /** Antwort senden; im Raum mit der selbst gemessenen Zeit (Host-Uhr geschätzt über `versatz`) */
  function antwortGeben(index: number) {
    const start = spiel?.zug?.timerStart;
    if (!raum || start === null || start === undefined) {
      ausfuehren({ typ: 'antworten', index });
      return;
    }
    ausfuehren({ typ: 'antworten', index, zeit: (Date.now() + versatz - start) / 1000 });
  }

  /** Host: Aktion auf den Spielstand anwenden */
  function anwenden(von: string, aktion: Aktion) {
    if (!spiel) return;
    if (raum && !darf(spiel, raum.teilnehmer, geraet, von, aktion)) return;
    // Wer antwortet? Im Raum bestimmt der Host das aus dem Gerät, nie aus der Nachricht
    const spieler = raum ? raum.teilnehmer.findIndex((t) => t.geraet === von) : spiel.aktiverSpieler;
    const r = aktionAnwenden(spiel, aktion, {
      pool: fragen,
      history,
      jetzt: Date.now(),
      spieler,
      toleranzMs: raum ? TOLERANZ_MS : 0,
    });
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
      else if (n.typ === 'hallo') gastBegruessen(n.von, n.name, n.fragen, n);
      else if (n.typ === 'tschuess' && !spiel) raum.teilnehmer = verlassen(raum.teilnehmer, n.von);
      return;
    }
    // Gast
    if (n.typ === 'stand' && n.von !== geraet && n.teilnehmer.some((t) => t.geraet === geraet)) {
      // Uhrabweichung zum Host: Die Übertragungszeit lässt sie kleiner erscheinen, also das Maximum nehmen
      const d = n.jetzt - Date.now();
      versatz = versatzBekannt ? Math.max(versatz, d) : d;
      versatzBekannt = true;
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
      jetzt: Date.now(),
    };
  }

  /** Host: Gast aufnehmen (oder nach Neuladen wieder begrüssen) */
  function gastBegruessen(von: string, name: string, fragen: string, wahl: Partial<StufenWahl>) {
    if (!raum) return;
    const r = beitreten(raum.teilnehmer, von, name, spiel !== null, fragen === fragenKennung, wahl);
    if (!r.ok) {
      kanal.senden({ typ: 'abgelehnt', von: geraet, an: von, grund: BEITRITTS_FEHLER[r.fehler] });
      return;
    }
    raum.teilnehmer = r.teilnehmer;
    // Auch ohne Änderung antworten (der Gast hat nach dem Neuladen keinen Spielstand)
    kanal.senden(standNachricht());
  }

  /** Eigene Schwierigkeitswahl fürs nächste Mal merken */
  function raumWahlMerken(wahl: StufenWahl) {
    letzte = { ...(letzte ?? { namen: [], farben: [], runden: RUNDEN_STANDARD }), raumWahl: wahl };
    storage.speichereLetzteSpieler(letzte);
  }

  function raumEroeffnen(name: string, wahl: StufenWahl) {
    const code = zufallsCode(Math.random);
    const farbe = letzte?.farben[0] ?? SPIELER_FARBEN[0];
    const w = stufenWahlPruefen(wahl);
    raumWahlMerken(w);
    raum = {
      code,
      rolle: 'host',
      kanal: kanalArt,
      name,
      wahl: w,
      teilnehmer: [{ geraet, name, farbe, ...w }],
      hostGeraet: geraet,
    };
    spiel = null;
    meldung = null;
    raumFehler = null;
    raumStartOffen = false;
    kanalWechseln(raumKanal(code, kanalArt));
  }

  function raumBeitreten(code: string, name: string, wahl: StufenWahl) {
    const w = stufenWahlPruefen(wahl);
    raumWahlMerken(w);
    raum = { code, rolle: 'gast', kanal: kanalArt, name, wahl: w, teilnehmer: [], hostGeraet: null };
    spiel = null;
    meldung = null;
    raumFehler = null;
    raumStartOffen = false;
    linkCode = '';
    versatzBekannt = false;
    storage.speichereRaum({ code, rolle: 'gast', kanal: kanalArt, name, wahl: w });
    kanalWechseln(raumKanal(code, kanalArt));
    halloStarten();
  }

  /** Nach dem Neuladen: dem Raum wieder beitreten bzw. ihn als Host weiterführen */
  function raumWiederaufnehmen(s: storage.RaumSitzung, p: Pool) {
    raum = {
      code: s.code,
      rolle: s.rolle,
      kanal: s.kanal ?? 'netz',
      name: s.name,
      wahl: stufenWahlPruefen(s.wahl),
      teilnehmer: s.teilnehmer ?? [],
      hostGeraet: s.rolle === 'host' ? geraet : null,
    };
    if (s.rolle === 'host' && s.spiel) spiel = game.wiederherstellen(s.spiel, p.fragen, Date.now());
    kanalWechseln(raumKanal(s.code, s.kanal ?? 'netz'));
    if (s.rolle === 'gast') halloStarten();
  }

  /** Gast: beim Host anklopfen (nur solange er uns noch nicht aufgenommen hat) */
  function halloSenden() {
    if (raum?.rolle === 'gast' && ich < 0) {
      kanal.senden({ typ: 'hallo', von: geraet, name: raum.name, fragen: fragenKennung, ...$state.snapshot(raum.wahl) });
    }
  }

  /** Gast: so lange anklopfen, bis der Host antwortet */
  function halloStarten() {
    clearInterval(halloTimer);
    halloSenden();
    halloTimer = setInterval(halloSenden, 2000);
  }

  /** Link zum Beitreten (auch als QR-Code); im Tab-Modus mit `?kanal=tabs` */
  function raumLink(code: string): string {
    const url = new URL(import.meta.env.BASE_URL, location.origin);
    if (kanalArt === 'tabs') url.searchParams.set('kanal', 'tabs');
    url.searchParams.set('raum', code);
    return url.toString();
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
    versatz = 0;
    versatzBekannt = false;
  }

  function starten(spieler: game.NeuerSpieler[], runden: number, einstellungen: Einstellungen) {
    letzte = {
      // Im Raum stammen die Spieler von den Geräten – die Namen fürs Spiel auf einem Gerät bleiben
      namen: raum ? (letzte?.namen ?? []) : spieler.map((p) => p.name),
      farben: raum ? (letzte?.farben ?? []) : spieler.map((p) => p.farbe),
      schwierigkeiten: raum
        ? letzte?.schwierigkeiten
        : spieler.map((p) => p.schwierigkeit ?? SCHWIERIGKEIT_STANDARD),
      proKategorie: raum ? letzte?.proKategorie : spieler.map((p) => p.proKategorie),
      raumSchwierigkeit:
        raum && einstellungen.ablauf === 'gleichzeitig' ? spieler[0]?.schwierigkeit : letzte?.raumSchwierigkeit,
      raumWahl: letzte?.raumWahl,
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

{#if verbindungWeg}
  <div class="verbindung" role="status">
    <p>Keine Verbindung zu den anderen Geräten – wird erneut versucht …</p>
    {#if netzStatus}<NetzDiagnose status={netzStatus} />{/if}
  </div>
{/if}

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
    wahl={letzte?.raumWahl ?? { schwierigkeit: letzte?.schwierigkeiten?.[0] ?? SCHWIERIGKEIT_STANDARD, proKategorie: letzte?.proKategorie?.[0] }}
    code={linkCode}
    fehler={raumFehler}
    onEroeffnen={raumEroeffnen}
    onBeitreten={raumBeitreten}
    onZurueck={() => {
      raumStartOffen = false;
      raumFehler = null;
      linkCode = '';
    }}
  />
{:else if !spiel}
  {#if raum && istGast}
    <Lobby
      code={raum.code}
      link={raumLink(raum.code)}
      teilnehmer={raum.teilnehmer}
      ich={geraet}
      netz={netzStatus}
      onVerlassen={() => raumVerlassen()}
    />
  {:else}
    <Setup
      {letzte}
      {gesamt}
      onStart={starten}
      onInfo={() => (infoOffen = true)}
      raum={raum ? { code: raum.code, teilnehmer: raum.teilnehmer, ich: geraet, netz: netzStatus } : undefined}
      raumLink={raum ? raumLink(raum.code) : undefined}
      onMehrgeraete={raum ? undefined : () => (raumStartOffen = true)}
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
    <Kopf {spiel} onBeenden={abbrechen} spieler={ichSpieler} />
    {#if spiel.phase === 'kategorie'}
      {@const w = game.waehler(spiel)}
      {#if !amZug}
        <Warten
          spieler={spiel.spieler[w]}
          text={spiel.modus === 'zufall'
            ? `Kategorie für ${gleichzeitig ? 'alle' : aktiv.name} wird ausgelost …`
            : gleichzeitig
              ? `${aktiv.name} wählt eine Kategorie für alle`
              : w !== spiel.aktiverSpieler
                ? `${spiel.spieler[w].name} wählt eine Kategorie für ${aktiv.name}`
                : `${aktiv.name} wählt eine Kategorie`}
          hinweis={gleichzeitig ? `Runde ${spiel.runde} von ${spiel.runden}` : undefined}
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
          fuerAlle={gleichzeitig}
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
          eigeneWahl={gleichzeitig ? (eigeneAntwort?.gewaehlt ?? null) : undefined}
          warteText={gleichzeitig ? `Warte auf die anderen … (${beantwortet}/${spiel.spieler.length})` : undefined}
          onTimerStart={() => ausfuehren({ typ: 'timerStarten' })}
          onAntwort={antwortGeben}
          {versatz}
          onTimeout={zeitPruefen}
        />
      {/key}
    {:else if spiel.phase === 'feedback' && spiel.zug?.alle && aktuelleFrage}
      {@const alle = spiel.zug.alle}
      {@const meine = ich >= 0 ? alle[ich] : null}
      <!-- „Alle gleichzeitig“: oben das eigene Ergebnis, darunter alle -->
      <Feedback
        frage={aktuelleFrage}
        zug={meine ? { ...spiel.zug, ...meine } : spiel.zug}
        spieler={ichSpieler ?? aktiv}
        {letzterZug}
        ergebnisse={spiel.spieler.flatMap((p, i) => (alle[i] ? [{ spieler: p, antwort: alle[i] }] : []))}
        onWeiter={amZug ? () => ausfuehren({ typ: 'weiter' }) : undefined}
        warteText={`Warte auf ${hostName} …`}
      />
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
  .verbindung {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 10;
    margin: 0;
    padding: calc(env(safe-area-inset-top) + 8px) 16px 8px;
    background: var(--warn);
    color: #fff;
    font-weight: 700;
    font-size: 0.95rem;
    text-align: center;
  }
  .verbindung p {
    margin: 0;
  }
  .verbindung :global(.diagnose) {
    color: #fff;
    font-weight: 400;
    text-align: left;
  }
</style>
