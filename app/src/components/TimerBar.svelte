<script lang="ts">
  import { WARNUNG_AB_S, ZEITLIMIT_S } from '../lib/config';

  let { rest }: { rest: number } = $props();
  const anteil = $derived(Math.max(0, Math.min(1, rest / ZEITLIMIT_S)));
  const warnung = $derived(rest <= WARNUNG_AB_S);
</script>

<div
  class="timer"
  class:warnung
  role="progressbar"
  aria-label="Verbleibende Zeit in Sekunden"
  aria-valuemin={0}
  aria-valuemax={ZEITLIMIT_S}
  aria-valuenow={Math.ceil(rest)}
>
  <div class="balken" style:transform="scaleX({anteil})"></div>
  <span class="zahl">{Math.ceil(rest)}</span>
</div>

<style>
  .timer {
    position: relative;
    height: 28px;
    border-radius: 14px;
    background: var(--line);
    overflow: hidden;
  }
  .balken {
    position: absolute;
    inset: 0;
    background: var(--ok);
    transform-origin: left center;
    transition: background-color 0.3s;
  }
  .warnung .balken {
    background: var(--warn);
    animation: pulsieren 0.5s ease-in-out infinite alternate;
  }
  .zahl {
    position: absolute;
    right: 10px;
    top: 50%;
    transform: translateY(-50%);
    font-weight: 800;
    font-variant-numeric: tabular-nums;
    color: var(--text);
  }
  @keyframes pulsieren {
    to {
      opacity: 0.7;
    }
  }
</style>
