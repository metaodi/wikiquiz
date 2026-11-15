// Fügt data/fragen/<kategorie>.json zu public/questions.json zusammen (läuft vor dev/build).
import { readdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const hier = dirname(fileURLToPath(import.meta.url));
const quelle = process.env.WIKIQUIZ_DATA_DIR ?? join(hier, '..', '..', 'data', 'fragen');
const ziel = join(hier, '..', 'public', 'questions.json');

const dateien = existsSync(quelle) ? readdirSync(quelle).filter((d) => d.endsWith('.json')).sort() : [];
const fragen = [];
const ids = new Set();
let stand = null;
for (const datei of dateien) {
  const inhalt = JSON.parse(readFileSync(join(quelle, datei), 'utf8'));
  for (const f of inhalt.fragen) {
    if (ids.has(f.id)) throw new Error(`Doppelte Frage-ID ${f.id} in ${datei}`);
    ids.add(f.id);
    fragen.push(f);
  }
  if (inhalt.generiert_am && (!stand || inhalt.generiert_am > stand)) stand = inhalt.generiert_am;
}
writeFileSync(ziel, JSON.stringify({ version: 1, generiert_am: stand, fragen }) + '\n');
console.log(`questions.json: ${fragen.length} Fragen aus ${dateien.length} Dateien`);
