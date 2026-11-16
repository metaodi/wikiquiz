<script lang="ts">
  import { onMount } from 'svelte';
  import TimerBar from '../components/TimerBar.svelte';
  import { KATEGORIE_MAP } from '../lib/categories';
  import { EINBLENDEN_MS, ZEITLIMIT_S } from '../lib/config';
  import type { Frage } from '../lib/types';

  let {
    frage,
    reihenfolge,
    timerStart,
    onTimerStart,
    onAntwort,
    onTimeout,
    zuschauen = false,
    eigeneWahl,
    warteText,
  }: {
    frage: Frage;
    reihenfolge: number[];
    timerStart: number | null;
    onTimerStart: () => void;
    onAntwort: (index: number) => void;
    onTimeout: () => void;
    /** Mehrere Geräte: Frage nur anzeigen – jemand anders antwortet und startet den Timer */
    zuschauen?: boolean;
    /** „Alle gleichzeitig“: bereits gespeicherte eigene Antwort (null = noch keine) */
    eigeneWahl?: number | null;
    /** Erscheint, sobald man selbst geantwortet hat (z. B. „Warte auf die anderen …“) */
    warteText?: string;
  } = $props();

  const kat = $derived(KATEGORIE_MAP[frage.kategorie]);
  let jetzt = $state(Date.now());
  const rest = $derived(
    timerStart === null ? ZEITLIMIT_S : Math.min(ZEITLIMIT_S, Math.max(0, ZEITLIMIT_S - (jetzt - timerStart) / 1000)),
  );
  let gesendet = false;
  // Sofort markieren, nicht erst, wenn der Host die Antwort bestätigt
  let lokaleWahl = $state<number | null>(null);
  const markiert = $derived(eigeneWahl ?? lokaleWahl);
  const gesperrt = $derived(timerStart === null || zuschauen || markiert !== null);

  onMount(() => {
    // Timer erst starten, wenn Frage und Antworten vollständig eingeblendet sind.
    // Nach einem Neuladen läuft ein bereits gestarteter Timer gemäss timerStart weiter.
    const start = timerStart === null && !zuschauen ? setTimeout(onTimerStart, EINBLENDEN_MS) : undefined;
    let raf = 0;
    const tick = () => {
      jetzt = Date.now();
      if (timerStart !== null && rest <= 0 && !gesendet) {
        gesendet = true;
        onTimeout();
        return;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      clearTimeout(start);
      cancelAnimationFrame(raf);
    };
  });

  function waehlen(i: number) {
    if (gesperrt || gesendet) return;
    gesendet = true;
    lokaleWahl = i;
    onAntwort(i);
  }
</script>

<div class="kategorie" style:--kf={kat.farbe} style:--kt={kat.text}>
  <span aria-hidden="true">{kat.icon}</span>
  {kat.name}
</div>

<h1 class="frage">{frage.frage}</h1>

<div class="unten">
  <TimerBar {rest} />
  {#if zuschauen}
    <p class="muted zuschauen">Du schaust zu.</p>
  {:else if markiert !== null && warteText}
    <p class="muted zuschauen" role="status">{warteText}</p>
  {/if}
  <ul class="antworten" aria-label="Antworten">
    {#each reihenfolge as i, pos (i)}
      <li style:--verzoegerung="{pos * 70}ms">
        <button class="antwort" class:gewaehlt={markiert === i} disabled={gesperrt} onclick={() => waehlen(i)}>
          <span class="buchstabe" aria-hidden="true">{'ABCD'[pos]}</span>
          <span class="text">{frage.antworten[i]}</span>
        </button>
      </li>
    {/each}
  </ul>
</div>

<style>
  .zuschauen {
    margin: 0;
    text-align: center;
  }
  .kategorie {
    align-self: flex-start;
    display: inline-flex;
    gap: 8px;
    align-items: center;
    padding: 6px 12px;
    border-radius: 999px;
    background: var(--kf);
    color: var(--kt);
    font-weight: 700;
    font-size: 0.95rem;
  }
  .frage {
    font-size: 1.45rem;
    font-weight: 700;
    overflow-wrap: anywhere;
    hyphens: auto;
  }
  .antworten {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  li {
    animation: einblenden 0.25s ease-out both;
    animation-delay: var(--verzoegerung);
  }
  .antwort {
    width: 100%;
    min-height: 60px;
    display: flex;
    align-items: center;
    gap: 12px;
    text-align: left;
    padding: 10px 14px;
    border-radius: var(--radius);
    border: 2px solid var(--line);
    background: var(--bg-2);
    box-shadow: var(--shadow);
    font-weight: 600;
    transition: transform 0.08s ease;
  }
  .antwort:disabled {
    cursor: default;
    color: inherit;
  }
  .antwort.gewaehlt {
    border-color: var(--accent);
    box-shadow: inset 0 0 0 2px var(--accent);
  }
  .antwort:not(:disabled):active {
    transform: scale(0.98);
    border-color: var(--accent);
  }
  .buchstabe {
    flex: none;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: var(--bg);
    display: grid;
    place-items: center;
    font-weight: 800;
    color: var(--text-2);
  }
  .text {
    overflow-wrap: anywhere;
    hyphens: auto;
  }
  @keyframes einblenden {
    from {
      opacity: 0;
      transform: translateY(8px);
    }
  }
</style>
