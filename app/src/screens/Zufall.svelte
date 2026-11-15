<script lang="ts">
  import { onMount } from 'svelte';
  import { KATEGORIEN, KATEGORIE_MAP } from '../lib/categories';
  import { ZUFALL_ANIMATION_MS } from '../lib/config';
  import type { KategorieId } from '../lib/types';

  let {
    ziel,
    kategorien,
    onFertig,
  }: { ziel: KategorieId; kategorien: KategorieId[]; onFertig: () => void } = $props();

  let index = $state(0);
  let gelandet = $state(false);
  // Nur durch die Kategorien drehen, mit denen gespielt wird
  const rad = $derived(KATEGORIEN.filter((k) => kategorien.includes(k.id)));
  const aktuell = $derived(gelandet || rad.length === 0 ? KATEGORIE_MAP[ziel] : rad[index % rad.length]);

  onMount(() => {
    // Immer langsamer durch die Kategorien drehen, dann auf dem Ziel landen
    let verzoegerung = 60;
    let timer: ReturnType<typeof setTimeout>;
    const ende = performance.now() + ZUFALL_ANIMATION_MS * 0.65;
    const drehen = () => {
      if (performance.now() >= ende) {
        gelandet = true;
        timer = setTimeout(onFertig, ZUFALL_ANIMATION_MS * 0.35);
        return;
      }
      index++;
      verzoegerung *= 1.18;
      timer = setTimeout(drehen, verzoegerung);
    };
    timer = setTimeout(drehen, verzoegerung);
    return () => clearTimeout(timer);
  });
</script>

<div class="buehne" aria-live="polite">
  <p class="muted">Zufall …</p>
  <div class="kat" class:gelandet style:--kf={aktuell.farbe} style:--kt={aktuell.text}>
    <span class="icon" aria-hidden="true">{aktuell.icon}</span>
    <span class="name">{aktuell.name}</span>
  </div>
</div>

<style>
  .buehne {
    margin: auto 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
    text-align: center;
  }
  .kat {
    width: min(100%, 320px);
    min-height: 180px;
    border-radius: 24px;
    background: var(--kf);
    color: var(--kt);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 10px;
    padding: 16px;
    font-weight: 800;
    font-size: 1.3rem;
    box-shadow: var(--shadow);
    transition: background-color 0.1s;
  }
  .icon {
    font-size: 3.4rem;
  }
  .gelandet {
    animation: landen 0.45s cubic-bezier(0.3, 1.6, 0.5, 1);
  }
  @keyframes landen {
    from {
      transform: scale(0.85);
    }
    to {
      transform: scale(1);
    }
  }
</style>
