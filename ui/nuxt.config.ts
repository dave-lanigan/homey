import { shadcn } from '@clerk/ui/themes'
import tailwindcss from '@tailwindcss/vite'

// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },
  ssr: false,
  modules: [
    '@clerk/nuxt',
    'shadcn-nuxt',
    '@nuxt/icon',
    '@nuxtjs/color-mode',
    '@comark/nuxt'
  ],

  clerk: {
    appearance: {
      theme: shadcn,
      cssLayerName: 'clerk',
    },
  },

  shadcn: {
    prefix: '',
    componentDir: './app/components/ui'
  },

  colorMode: {
    classSuffix: ''
  },

  vite: {
    plugins: [
      tailwindcss()
    ]
  },

  icon: {
    clientBundle: {
      scan: {
        globInclude: ['**/*.{vue,jsx,tsx,ts,js,md,mdc,mdx,yml,yaml}']
      }
    }
  },

  css: ['~/assets/css/main.css'],

  experimental: {
    viewTransition: true
  },

  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || '',
    },
  },
})
