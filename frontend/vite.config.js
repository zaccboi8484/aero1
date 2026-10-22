import {fileURLToPath} from 'node:url';
import {dirname,resolve} from 'node:path';
import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
const here=dirname(fileURLToPath(import.meta.url));
export default defineConfig({
 root:here,
 plugins:[react()],
 build:{outDir:resolve(here,'../public'),emptyOutDir:false,assetsDir:'assets',
  rollupOptions:{input:resolve(here,'index.html')}},
 server:{host:'0.0.0.0',port:5173,proxy:{
  '/api':{target:'http://127.0.0.1:8787',changeOrigin:true}
 }}
});
