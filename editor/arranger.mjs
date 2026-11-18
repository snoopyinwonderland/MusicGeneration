// Run musicomp's own UI and API. Only its initial new-score selection is supplied by the host.
import { createRequire, registerHooks } from 'node:module';
import { resolve, join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { writeFile } from 'node:fs/promises';
const [project, state, readyFile] = process.argv.slice(2);
const require = createRequire(join(project, 'package.json'));
// Resolve the upstream config against its declared dependencies, including on
// Windows workbenches with a separate node_modules tree for preview builds.
const parentURL = pathToFileURL(join(project,'package.json')).href;
const hook = registerHooks({resolve(specifier,context,next){
  return next(specifier, ['vite','@vitejs/plugin-react'].includes(specifier) ? {...context,parentURL} : context);
}});
const { createServer } = await import(pathToFileURL(require.resolve('vite')).href);
const { default: original } = await import(pathToFileURL(join(project,'workbench/vite.config.mjs')).href);
hook.deregister();
const seed = {
  name: 'motifind-start-with-score', enforce: 'pre',
  transformIndexHtml() {
    return [{tag:'style',children:`
      body .wb {height:auto;min-height:100vh}
      body .wb-main {flex:auto;align-items:start}
      body .wb-score {min-width:0;overflow:visible}
      body .wb-side {max-height:100vh;position:sticky;top:0}
      @media(max-width:760px){
        body .wb-main {grid-template-columns:minmax(0,1fr)}
        body .wb-side {position:static;max-height:none}
      }` ,injectTo:'head'}];
  },
  transform(code, id) {
    if (!id.replaceAll('\\','/').endsWith('/workbench/src/App.tsx')) return;
    const replacements = [
      ['[newOpen, setNewOpen] = useState(false)', '[newOpen, setNewOpen] = useState(Boolean(motifindInput))'],
      ['[pickListOpen, setPickListOpen] = useState(true)', '[pickListOpen, setPickListOpen] = useState(!motifindInput)'],
      ["[newPick, setNewPick] = useState('')", '[newPick, setNewPick] = useState(motifindInput)'],
    ];
    for (const [before, after] of replacements) {
      if (!code.includes(before)) throw Error('편곡기 새 곡 입력 인터페이스가 변경되었습니다.');
      code = code.replace(before, after);
    }
    return 'const motifindName = new URLSearchParams(location.search).get("score") || "";\n' +
      'const motifindInput = /^[^/\\\\:]+-[a-f0-9]{32}\\.musicxml$/.test(motifindName) ? ' +
      JSON.stringify(resolve(state,'uploads').replaceAll('\\','/')+'/') + ' + motifindName : "";\n' + code;
  }
};
const server = await createServer({...original, configFile:false, cacheDir:join(state,'vite-cache'),
  resolve:{...original.resolve,alias:['react/jsx-dev-runtime','react/jsx-runtime','react-dom/client','react-dom','react','verovio/esm','verovio/wasm'].map(name=>({
    find:new RegExp('^'+name+'$'),replacement:require.resolve(name).replace(/verovio\.cjs$/, 'verovio.mjs')
  }))},
  plugins:[seed,...original.plugins], server:{...original.server,host:'127.0.0.1',port:0,open:false,hmr:false,watch:null}});
await server.listen();
const parent = process.ppid;
async function shutdown() { await server.close(); process.exit(0); }
const lifetime = setInterval(() => {
  try { process.kill(parent, 0); } catch { void shutdown(); }
}, 5000);
lifetime.unref();
process.stdin.resume();
process.stdin.once('end', shutdown);
await writeFile(readyFile,String(server.httpServer.address().port));
