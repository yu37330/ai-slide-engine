// 初回のcatalogだけをCIログ経由で取り出せるようにする。フォント・AWS素材なし。
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
const buf=await fs.readFile(process.argv[2]);
const s=buf.toString('base64'),chunk=12000,n=Math.ceil(s.length/chunk);
console.log('CATALOG_EXPORT_START',n,buf.length,crypto.createHash('sha256').update(buf).digest('hex'));
for(let i=0;i<n;i++)console.log('CATALOG_CHUNK',i,s.slice(i*chunk,(i+1)*chunk));
console.log('CATALOG_EXPORT_END');
