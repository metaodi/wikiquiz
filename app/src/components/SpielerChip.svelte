<script lang="ts">
  import type { Spieler } from '../lib/types';

  let { spieler, gross = false }: { spieler: Pick<Spieler, 'name' | 'farbe'>; gross?: boolean } = $props();
</script>

<span class="chip" class:gross style:--farbe={spieler.farbe}>
  <span class="punkt" aria-hidden="true">{spieler.name.slice(0, 1).toUpperCase()}</span>
  <span class="name">{spieler.name}</span>
</span>

<style>
  .chip {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-weight: 700;
    min-width: 0;
  }
  .punkt {
    flex: none;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: var(--farbe);
    color: #fff;
    display: grid;
    place-items: center;
    font-size: 0.85rem;
  }
  .name {
    overflow-wrap: anywhere;
  }
  .gross .punkt {
    width: 40px;
    height: 40px;
    font-size: 1.2rem;
  }
  .gross {
    font-size: 1.3rem;
  }
</style>
