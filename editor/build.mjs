import { build } from 'vite';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(fileURLToPath(import.meta.url));
await build({
  root,
  base: './',
  configFile: false,
  logLevel: 'warn',
  define: { 'process.env.NODE_ENV': '"production"' },
  build: {
    outDir: resolve(process.argv[2] || resolve(root, '../output/editor')),
    emptyOutDir: false,
    lib: {
      entry: resolve(root, 'index.tsx'),
      formats: ['es'],
      fileName: () => 'motif-input.js',
      cssFileName: 'motif-input',
    },
  },
});
