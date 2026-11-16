<script lang="ts">
  import { renderSVG } from 'uqr';
  import type { Teilnehmer } from '../lib/raum';
  import SpielerChip from './SpielerChip.svelte';

  /** Raumcode, QR-Code/Link zum Beitreten und Liste der beigetretenen Geräte (Lobby von Host und Gästen) */
  let {
    code,
    teilnehmer,
    ich,
    link,
  }: { code: string; teilnehmer: Teilnehmer[]; ich: string; link?: string } = $props();

  const qr = $derived(link ? renderSVG(link, { ecc: 'M', border: 2 }) : '');
  let kopiert = $state(false);

  async function teilen() {
    if (!link) return;
    const daten = { title: 'WikiQuiz', text: `Spiel mit im Raum ${code}!`, url: link };
    try {
      if (navigator.share) {
        await navigator.share(daten);
        return;
      }
    } catch (e) {
      if ((e as DOMException).name === 'AbortError') return;
    }
    try {
      await navigator.clipboard.writeText(link);
      kopiert = true;
      setTimeout(() => (kopiert = false), 2500);
    } catch {
      /* Zwischenablage nicht verfügbar – der Link steht ja unter dem QR-Code */
    }
  }
</script>

<section class="karte" aria-labelledby="raum-titel">
  <h2 id="raum-titel">Raum</h2>
  <p class="code" aria-label="Raumcode">{code}</p>
  {#if link}
    <!-- uqr erzeugt reines SVG aus dem Link, kein fremder Inhalt -->
    <div class="qr" role="img" aria-label="QR-Code zum Beitreten">{@html qr}</div>
    <p class="muted hinweis">
      QR-Code mit der Kamera scannen oder den Link schicken. Oder: „Mit mehreren Geräten spielen“ wählen und den Code
      eingeben.
    </p>
    <p class="link" aria-label="Link zum Beitreten">{link}</p>
    <button type="button" class="btn sekundaer" onclick={teilen}>{kopiert ? 'Link kopiert ✓' : 'Link teilen'}</button>
  {:else}
    <p class="muted hinweis">Weitere Geräte wählen „Mit mehreren Geräten spielen“ und geben diesen Code ein.</p>
  {/if}
  <ol class="liste" aria-label="Spieler im Raum">
    {#each teilnehmer as t (t.geraet)}
      <li>
        <SpielerChip spieler={t} />
        {#if t.geraet === ich}<span class="muted">(du)</span>{/if}
        {#if t === teilnehmer[0]}<span class="muted">· leitet das Spiel</span>{/if}
      </li>
    {/each}
  </ol>
</section>

<style>
  .karte {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  h2 {
    font-size: 1.1rem;
  }
  p {
    margin: 0;
  }
  .code {
    font-size: 2.4rem;
    font-weight: 800;
    letter-spacing: 0.25em;
    text-align: center;
  }
  .hinweis {
    font-size: 0.95rem;
  }
  .qr {
    align-self: center;
    width: min(200px, 60vw);
    line-height: 0;
    border-radius: 8px;
    overflow: hidden;
  }
  .qr :global(svg) {
    width: 100%;
    height: auto;
  }
  .link {
    font-size: 0.85rem;
    color: var(--text-2);
    overflow-wrap: anywhere;
    text-align: center;
  }
  .liste {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  li {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    min-height: 40px;
  }
</style>
