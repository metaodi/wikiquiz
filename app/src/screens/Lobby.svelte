<script lang="ts">
  import { onMount } from 'svelte';
  import RaumKarte from '../components/RaumKarte.svelte';
  import type { NetzStatus } from '../lib/kanal';
  import type { Teilnehmer } from '../lib/raum';

  /** Lobby eines Gasts: warten, bis der Host das Spiel startet */
  let {
    code,
    link,
    teilnehmer,
    ich,
    netz = null,
    onVerlassen,
  }: {
    code: string;
    link?: string;
    teilnehmer: Teilnehmer[];
    ich: string;
    netz?: NetzStatus | null;
    onVerlassen: () => void;
  } = $props();

  // Dauert die Verbindung lange, Hinweise zur Fehlersuche zeigen
  let lange = $state(false);
  onMount(() => {
    const t = setTimeout(() => (lange = true), 15_000);
    return () => clearTimeout(t);
  });

  const dabei = $derived(teilnehmer.some((t) => t.geraet === ich));
  const host = $derived(teilnehmer[0]);
</script>

<div class="screen">
  <h1>Mit mehreren Geräten</h1>
  <RaumKarte {code} {teilnehmer} {ich} link={dabei ? link : undefined} {netz} />
  <p class="muted status" role="status">
    {#if !dabei}
      Verbinde mit Raum {code} …
      {#if lange}
        <br />Noch keine Verbindung. Stimmt der Code, ist der Raum noch offen und sind alle Geräte online?
      {/if}
    {:else}
      Warte, bis {host.name} das Spiel startet …
    {/if}
  </p>
  <div class="unten">
    <button class="btn sekundaer" onclick={onVerlassen}>Raum verlassen</button>
  </div>
</div>

<style>
  .status {
    margin: 0;
    text-align: center;
  }
</style>
