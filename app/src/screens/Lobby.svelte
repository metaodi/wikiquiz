<script lang="ts">
  import RaumKarte from '../components/RaumKarte.svelte';
  import type { Teilnehmer } from '../lib/raum';

  /** Lobby eines Gasts: warten, bis der Host das Spiel startet */
  let {
    code,
    teilnehmer,
    ich,
    onVerlassen,
  }: { code: string; teilnehmer: Teilnehmer[]; ich: string; onVerlassen: () => void } = $props();

  const dabei = $derived(teilnehmer.some((t) => t.geraet === ich));
  const host = $derived(teilnehmer[0]);
</script>

<div class="screen">
  <h1>Mit mehreren Geräten</h1>
  <RaumKarte {code} {teilnehmer} {ich} />
  <p class="muted status" role="status">
    {#if !dabei}
      Verbinde mit Raum {code} …
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
