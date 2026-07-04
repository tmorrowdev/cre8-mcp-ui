import esbuild from 'esbuild';
import { readFile } from 'node:fs/promises';
import path from 'node:path';

async function readCaseInsensitive(p) {
  try { return await readFile(p, 'utf8'); }
  catch (e) {
    if (e.code !== 'ENOENT') throw e;
    // Fall back to a lowercased basename (cre8-wc imports Add.svg but ships add.svg).
    const alt = path.join(path.dirname(p), path.basename(p).toLowerCase());
    return await readFile(alt, 'utf8');
  }
}

const querySuffix = {
  name: 'query-suffix',
  setup(b) {
    b.onResolve({ filter: /\?(raw|inline)$/ }, async (args) => {
      const clean = args.path.replace(/\?(raw|inline)$/, '');
      const r = await b.resolve(clean, { resolveDir: args.resolveDir, kind: 'import-statement' });
      if (r.errors.length) return { errors: r.errors };
      return { path: r.path, namespace: 'as-text' };
    });
    b.onLoad({ filter: /.*/, namespace: 'as-text' }, async (args) => ({
      contents: await readCaseInsensitive(args.path),
      loader: 'text',
    }));
  },
};

await esbuild.build({
  entryPoints: ['entry.js'],
  bundle: true, format: 'esm', minify: true, outfile: 'cre8-min.js',
  plugins: [querySuffix], loader: { '.svg': 'text', '.css': 'text' },
  logLevel: 'error', logLimit: 0,
});
console.log('built cre8-min.js');
