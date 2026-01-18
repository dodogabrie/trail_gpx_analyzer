<template>
  <div>
    <section class="pt-6 pb-12 md:pt-10 md:pb-20">
      <div class="layout grid lg:grid-cols-2 gap-12 items-center">
        <div class="relative">
          <div class="absolute -inset-4 rounded-[36px] bg-gradient-to-tr from-emerald-100/70 via-white/70 to-sky-100/70 blur-2xl"></div>
          <div class="relative rounded-[28px] overflow-hidden border border-white/70 shadow-2xl">
            <img
              :src="aboutImage"
              :alt="$t('about.image_alt')"
              class="w-full h-[420px] object-cover"
            />
          </div>
        </div>

        <div class="space-y-6">
          <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-100 text-emerald-700 text-xs font-bold uppercase tracking-widest">
            {{ $t('about.badge') }}
          </div>

          <h1 class="text-4xl md:text-5xl font-bold text-slate-900">
            {{ $t('about.title') }}
          </h1>
          <p class="text-lg text-slate-600 max-w-xl leading-relaxed">
            {{ $t('about.subtitle') }}
          </p>
          <div class="space-y-4 text-slate-600 leading-relaxed">
            <p>{{ $t('about.body1') }}</p>
            <p>{{ $t('about.body2') }}</p>
          </div>

          <div class="rounded-2xl border border-slate-100 bg-white/80 backdrop-blur-md p-5 text-slate-600 leading-relaxed">
            <p class="font-medium text-slate-900">{{ $t('about.personal_title') }}</p>
            <p class="mt-2">{{ $t('about.personal_text') }}</p>
          </div>

          <div class="flex flex-wrap items-center gap-4 text-sm text-slate-600">
            <span class="text-slate-400 font-semibold uppercase tracking-widest">{{ $t('about.contact_label') }}</span>
            <a href="mailto:dodogabrie97@live.it" class="link">{{ $t('about.contact_email') }}</a>
            <a
              href="https://www.strava.com/athletes/13538059"
              class="inline-flex items-center gap-2 text-slate-600 hover:text-[#FC4C02] transition-colors"
              target="_blank"
              rel="noreferrer"
              aria-label="Strava"
            >
              <span class="w-8 h-8 rounded-full bg-white border border-slate-200 flex items-center justify-center shadow-sm">
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" class="w-4 h-4 text-[#FC4C02]" fill="currentColor" aria-hidden="true">
                  <path d="M28.7 7L12.4 39.6h9.7l6.6-13.1 6.6 13.1h9.7L28.7 7zm13.2 23.4l-4.9 9.2-4.9-9.2h-7.3L37 56l12.3-25.6h-7.4z" />
                </svg>
              </span>
              <span class="text-sm font-medium">{{ $t('about.contact_strava') }}</span>
            </a>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import aboutImage from '../assets/Me.jpg'
</script>
