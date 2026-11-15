<script lang="ts">
  import type { Spieler } from '../lib/types';

  let { spieler, runde, runden, onBereit }: { spieler: Spieler; runde: number; runden: number; onBereit: () => void } =
    $props();
</script>

<div class="screen uebergabe" style:--farbe={spieler.farbe}>
  <p class="muted">Runde {runde} von {runden}</p>
  <div class="mitte">
    <div class="avatar" aria-hidden="true">{spieler.name.slice(0, 1).toUpperCase()}</div>
    <h1>Gib das Gerät an<br /><span class="name">{spieler.name}</span></h1>
    <p class="muted">Die anderen schauen bitte weg.</p>
  </div>
  <div class="unten">
    <button class="btn bereit" onclick={onBereit}>Bereit</button>
  </div>
</div>

<style>
  .uebergabe {
    text-align: center;
    background: linear-gradient(180deg, color-mix(in srgb, var(--farbe) 18%, transparent), transparent 60%);
  }
  .mitte {
    margin-top: 12vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
  }
  .avatar {
    width: 96px;
    height: 96px;
    border-radius: 50%;
    background: var(--farbe);
    color: #fff;
    display: grid;
    place-items: center;
    font-size: 2.6rem;
    font-weight: 800;
  }
  h1 {
    font-size: 1.6rem;
    font-weight: 600;
  }
  .name {
    font-size: 2.2rem;
    font-weight: 800;
    color: var(--farbe);
    overflow-wrap: anywhere;
  }
  .bereit {
    background: var(--farbe);
    color: #fff;
  }
</style>
