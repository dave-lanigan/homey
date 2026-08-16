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
    '@comark/nuxt',
    '@vite-pwa/nuxt',
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

  pwa: {
    registerType: 'autoUpdate',
    manifest: {
      id: '/',
      name: 'Homey',
      short_name: 'Homey',
      description: 'Your friendly AI Airbnb assistant — find the perfect stay.',
      theme_color: '#355070',
      background_color: '#ffffff',
      display: 'standalone',
      orientation: 'portrait-primary',
      start_url: '/',
      scope: '/',
      lang: 'en',
      categories: ['travel', 'lifestyle'],
      icons: [
        {
          src: '/pwa-192x192.png',
          sizes: '192x192',
          type: 'image/png',
          purpose: 'any',
        },
        {
          src: '/pwa-512x512.png',
          sizes: '512x512',
          type: 'image/png',
          purpose: 'any',
        },
        {
          src: '/pwa-512x512-maskable.png',
          sizes: '512x512',
          type: 'image/png',
          purpose: 'maskable',
        },
      ],
    },
    workbox: {
      navigateFallback: '/',
      navigateFallbackDenylist: [/^\/api\//],
      globPatterns: ['**/*.{js,css,html,png,svg,ico,woff2,webmanifest}'],
      // Clerk + AI SDK client chunks exceed Workbox's 2 MiB default.
      maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
      runtimeCaching: [
        {
          urlPattern: /\/api\//,
          handler: 'NetworkOnly',
        },
      ],
    },
    client: {
      installPrompt: true,
      periodicSyncForUpdates: 3600,
    },
    devOptions: {
      // Keep off by default — Chrome installability is validated against a
      // production build (`bun run generate` + served over HTTPS/localhost).
      enabled: false,
    },
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

  app: {
    head: {
      link: [
        { rel: 'manifest', href: '/manifest.webmanifest' },
      ],
    },
  },

  experimental: {
    viewTransition: true
  },

  runtimeConfig: {
    public: {
      apiBase: process.env.NUXT_PUBLIC_API_BASE || '',
    },
  },
})
