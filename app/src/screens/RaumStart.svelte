<script lang="ts">
  import { CODE_LAENGE, codeNormalisieren } from '../lib/raum';

  let {
    name: startName,
    fehler,
    onEroeffnen,
    onBeitreten,
    onZurueck,
  }: {
    name: string;
    fehler: string | null;
    onEroeffnen: (name: string) => void;
    onBeitreten: (code: string, name: string) => void;
    onZurueck: () => void;
  } = $props();

  // svelte-ignore state_referenced_locally
  let name = $state(startName);
  let code = $state('');
  const nameOk = $derived(name.trim().length > 0);
  const codeOk = $derived(codeNormalisieren(code).length === CODE_LAENGE);

  function beitreten(e: SubmitEvent) {
    e.preventDefault();
    if (nameOk && codeOk) onBeitreten(codeNormalisieren(code), name.trim());
  }
</script>

<div class="screen">
  <header>
    <h1>Mit mehreren Geräten</h1>
    <p class="muted">
      Jedes Gerät ist ein Spieler. Ein Gerät eröffnet einen Raum, die anderen treten mit dem Code bei.
    </p>
    <p class="muted klein">Vorschau: funktioniert vorerst nur zwischen Tabs im selben Browser.</p>
  </header>

  <section class="karte">
    <label class="feld">
      <span>Dein Name</span>
      <input type="text" bind:value={name} maxlength="20" autocomplete="off" placeholder="Name" />
    </label>
  </section>

  <section class="karte">
    <h2>Raum eröffnen</h2>
    <button class="btn" disabled={!nameOk} onclick={() => onEroeffnen(name.trim())}>Raum eröffnen</button>
  </section>

  <form class="karte" onsubmit={beitreten}>
    <h2>Raum beitreten</h2>
    <label class="feld">
      <span>Raumcode</span>
      <input
        class="code"
        type="text"
        bind:value={code}
        maxlength={CODE_LAENGE + 2}
        autocomplete="off"
        autocapitalize="characters"
        spellcheck="false"
        placeholder="ABCD"
      />
    </label>
    <button class="btn sekundaer" type="submit" disabled={!nameOk || !codeOk}>Beitreten</button>
  </form>

  {#if fehler}
    <p class="fehler" role="alert">{fehler}</p>
  {/if}

  <div class="unten">
    <button class="textlink" onclick={onZurueck}>Zurück</button>
  </div>
</div>

<style>
  header p {
    margin: 4px 0 0;
  }
  .klein {
    font-size: 0.9rem;
  }
  .karte {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  h2 {
    font-size: 1.1rem;
  }
  .feld {
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-weight: 700;
  }
  input {
    min-height: 52px;
    border: 2px solid var(--line);
    border-radius: 12px;
    padding: 8px 12px;
    background: var(--bg);
    font-weight: 400;
    min-width: 0;
  }
  .code {
    font-size: 1.4rem;
    letter-spacing: 0.3em;
    text-transform: uppercase;
    font-weight: 700;
  }
  .fehler {
    color: var(--bad);
    margin: 0;
  }
</style>
