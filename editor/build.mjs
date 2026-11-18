import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { resolve, dirname } from 'node:path';
const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const roots = [here, ...(process.argv[3] ? [process.argv[3]] : [])];
const find = (name) => require.resolve(name, { paths: roots });
const { build } = await import(pathToFileURL(find('vite')).href);
await build({
  root: here,
  configFile: false,
  logLevel: 'warn',
  define: { 'process.env.NODE_ENV': '"production"' },
  resolve: {
    alias: [
      { find: 'react-dom/client', replacement: find('react-dom/client') },
      { find: /^react$/, replacement: find('react') },
      { find: 'react/jsx-runtime', replacement: find('react/jsx-runtime') },
    ],
  },
  build: {
    outDir: resolve(process.argv[2] || resolve(here, '../output/editor')),
    emptyOutDir: false,
    lib: {
      entry: resolve(here, 'index.tsx'),
      name: 'MotifEditorApp',
      formats: ['iife'],
      fileName: () => 'motif-editor.js',
    },
  },
});
