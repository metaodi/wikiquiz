<script lang="ts">
  import type { NetzStatus } from '../lib/kanal';

  /** Verbindungszustand beim Spielen mit mehreren Geräten – aufklappbar, damit man auf dem Handy sieht, wo es hängt */
  let { status }: { status: NetzStatus } = $props();

  const FEHLER: Record<string, string> = {
    'peer-connect-failed': 'Die Verbindung zu einem Gerät ist gescheitert.',
    'relay-failed': 'Die Vermittlungs-Server (Relays) sind nicht erreichbar.',
    'decrypt-failed': 'Verschlüsselung passt nicht – anderer Raumcode oder andere App-Version?',
    'handshake-failed': 'Verbindungsaufbau abgebrochen – andere App-Version?',
    'room-full': 'Der Raum ist voll.',
  };

  const TURN: Record<NetzStatus['turn'], string> = {
    aus: 'nicht eingerichtet',
    laedt: 'wird geladen …',
    bereit: 'bereit',
    fehler: 'Zugangsdaten nicht ladbar',
  };

  const zusammenfassung = $derived.by(() => {
    if (status.geraete > 0) {
      const art = status.ueberTurn === true ? ' (über TURN)' : status.ueberTurn === false ? ' (direkt)' : '';
      return `verbunden mit ${status.geraete} ${status.geraete === 1 ? 'Gerät' : 'Geräten'}${art}`;
    }
    if (status.fehler === 'peer-connect-failed') return 'Verbindung gescheitert';
    if (status.relays === 0) return 'verbinde …';
    return 'suche andere Geräte …';
  });

  const tipp = $derived(
    status.fehler === 'peer-connect-failed'
      ? status.turn === 'bereit'
        ? 'Auch über den TURN-Server klappt es nicht. Anderes Netz (WLAN ↔ Mobilfunk) versuchen.'
        : 'Ohne TURN-Server klappt die Verbindung oft nicht, wenn ein Gerät im Mobilfunknetz ist. Beide Geräte ins selbe WLAN nehmen.'
      : null,
  );
</script>

<details class="diagnose">
  <summary>Verbindung: {zusammenfassung}</summary>
  <dl>
    <dt>Relays</dt>
    <dd>{status.relays} von {status.relaysGesamt} verbunden</dd>
    <dt>Andere Geräte</dt>
    <dd>{status.geraete}</dd>
    <dt>TURN-Server</dt>
    <dd>{TURN[status.turn]}</dd>
    {#if status.fehler}
      <dt>Letzter Fehler</dt>
      <dd>{FEHLER[status.fehler] ?? 'Unbekannter Fehler.'} <code>{status.fehler}</code></dd>
    {/if}
  </dl>
  {#if tipp}<p class="tipp">{tipp}</p>{/if}
</details>

<style>
  .diagnose {
    font-size: 0.9rem;
    color: var(--text-2);
  }
  summary {
    min-height: 48px;
    display: flex;
    align-items: center;
    cursor: pointer;
  }
  dl {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 4px 12px;
    margin: 0 0 8px;
  }
  dt {
    font-weight: 700;
  }
  dd {
    margin: 0;
    overflow-wrap: anywhere;
  }
  code {
    font-size: 0.8rem;
  }
  .tipp {
    margin: 0;
  }
</style>
