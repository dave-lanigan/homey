import { shadcn } from '@clerk/ui/themes'
import tailwindcss from '@tailwindcss/vite'

// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },
  ssr: false,
  // One app-level .env at the repo root (not ui/.env).
  envDir: '..',
  modules: [
    '@clerk/nuxt',
    'shadcn-nuxt',
    '@nuxt/icon',
    '@nuxtjs/color-mode',
    '@comark/nuxt'
  ],

  clerk: {
    // Publishable key is public by design; keep it in source so Cloud Build
    // does not need a build-time env var. Do not put the secret key here.
    publishableKey: 'pk_test_ZGFyaW5nLWFsYmFjb3JlLTY0ODYuY2xlcmsuYWNjb3VudHMuZGV2JA',
    signInUrl: '/sign-in',
    signUpUrl: '/sign-up',
    // SPA (ssr: false): skip server middleware so `nuxt generate` does not
    // require NUXT_CLERK_SECRET_KEY at build time.
    skipServerMiddleware: true,
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
