<script lang="ts">
  import type { Spieler } from '../lib/types';

  /** Mehrere Geräte: Anzeige auf den Geräten, die gerade nicht dran sind */
  let { spieler, text, hinweis }: { spieler: Pick<Spieler, 'name' | 'farbe'>; text: string; hinweis?: string } =
    $props();
</script>

<div class="warten" style:--farbe={spieler.farbe} role="status">
  <div class="avatar" aria-hidden="true">{spieler.name.slice(0, 1).toUpperCase()}</div>
  <h1>{text}</h1>
  {#if hinweis}<p class="muted">{hinweis}</p>{/if}
  <div class="punkte" aria-hidden="true"><span></span><span></span><span></span></div>
</div>

<style>
  .warten {
    margin: auto 0;
    padding: 24px 0;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 14px;
  }
  .avatar {
    width: 80px;
    height: 80px;
    border-radius: 50%;
    background: var(--farbe);
    color: #fff;
    display: grid;
    place-items: center;
    font-size: 2.2rem;
    font-weight: 800;
  }
  h1 {
    font-size: 1.4rem;
    font-weight: 600;
    overflow-wrap: anywhere;
  }
  p {
    margin: 0;
  }
  .punkte {
    display: flex;
    gap: 8px;
  }
  .punkte span {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--farbe);
    animation: puls 1.2s infinite ease-in-out;
  }
  .punkte span:nth-child(2) {
    animation-delay: 0.2s;
  }
  .punkte span:nth-child(3) {
    animation-delay: 0.4s;
  }
  @keyframes puls {
    0%,
    100% {
      opacity: 0.25;
    }
    50% {
      opacity: 1;
    }
  }
</style>
