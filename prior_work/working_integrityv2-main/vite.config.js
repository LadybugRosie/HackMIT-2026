import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import Vue from '@vitejs/plugin-vue'
import VueMacros from 'unplugin-vue-macros/vite'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { TDesignResolver } from 'unplugin-vue-components/resolvers'
import { createSvgIconsPlugin } from 'vite-plugin-svg-icons'

import pkg from './package.json'
import copyright from './src/utils/copyright'

export default defineConfig({
  base: '/',
  plugins: [
    VueMacros({
      plugins: {
        vue: Vue(),
      },
    }),
    AutoImport({
      dirs: ['./src/composables'],
      imports: ['vue', '@vueuse/core'],
      resolvers: [
        TDesignResolver({
          library: 'vue-next',
          esm: true,
        }),
      ],
      dts: './imports.d.ts',
    }),
    Components({
      directoryAsNamespace: true,
      dirs: ['./src/components'],
      resolvers: [
        TDesignResolver({
          library: 'vue-next',
          esm: true,
        }),
      ],
    }),
    createSvgIconsPlugin({
      iconDirs: [process.cwd() + '/src/assets/icons'],
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  css: {
    preprocessorOptions: {
      less: {
        modifyVars: {
          '@prefix': 'umo',
        },
        javascriptEnabled: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    minify: 'esbuild',
    cssMinify: true,
    rollupOptions: {
      input: fileURLToPath(new URL('./index.html', import.meta.url)),
      output: {
        banner: copyright,
        assetFileNames: 'assets/[name]-[hash][extname]',
        chunkFileNames: 'assets/[name]-[hash].js',
        entryFileNames: 'assets/[name]-[hash].js'
      },
      // external: [
      //   /@vueuse\/.*/,
      //   /@tiptap\/.*/,
      //   /nzh\/.*/,
      //   'vue',
      //   '@eslint/object-schema',
      //   '@imgly/background-removal',
      //   '@vue-monaco/editor',
      //   'dom-to-image-more',
      //   'es-drager',
      //   'file64',
      //   'file-saver',
      //   'hotkeys-js',
      //   'jsbarcode',
      //   'katex',
      //   'mermaid',
      //   'plyr',
      //   'pretty-bytes',
      //   'qrcode-svg',
      //   'svg64',
      //   'vue-i18n',
      //   'vue-esign',
      // ],
    },
  },
  server: {
    port: 9000,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'https://believable-dedication-production.up.railway.app',
        changeOrigin: true,
        secure: true,
        // rewrite is not needed since we keep the /api prefix
      },
    },
  },
  preview: {
    port: process.env.PORT ? parseInt(process.env.PORT) : 8080,
    host: '0.0.0.0',
    strictPort: false,
    allowedHosts: process.env.NODE_ENV === 'production'
      ? ['.railway.app', 'www.editorrah.com', 'editorrah.com']
      : 'all',
  },
})