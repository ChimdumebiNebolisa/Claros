#!/usr/bin/env node
/**
 * One-time build: bundle @google/genai for browser into frontend/genai.bundle.js.
 * Run from project root: npm run build:genai
 * Output is checked in so deploy does not need Node or this step.
 */
import * as esbuild from 'esbuild';
import { createRequire } from 'module';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const outFile = join(__dirname, 'frontend', 'genai.bundle.js');

await esbuild.build({
  entryPoints: [require.resolve('@google/genai/web')],
  bundle: true,
  platform: 'browser',
  format: 'esm',
  outfile: outFile,
  minify: false,
  sourcemap: false,
  target: ['es2020'],
  logLevel: 'info',
});

console.log('Wrote', outFile);
