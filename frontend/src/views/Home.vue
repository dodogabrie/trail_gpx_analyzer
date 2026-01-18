<template>
  <div>
    <!-- HERO SECTION -->
    <section
      class="relative pt-8 pb-16 sm:pt-10 sm:pb-20 md:pt-16 md:pb-28 lg:pt-20 lg:pb-32 overflow-hidden bg-cover bg-center bg-no-repeat"
      :style="{ backgroundImage: `url(${heroBackground})` }"
    >
      <div class="absolute inset-0 -z-10">
        <div class="absolute inset-0 bg-gradient-to-r from-slate-50/90 via-slate-50/65 to-slate-50/25"></div>
        <div class="absolute inset-0 bg-gradient-to-b from-white/45 via-transparent to-white/75"></div>
      </div>

      <div class="layout flex">
        <!-- Text Content -->
        <div class="space-y-8 w-full">
          <div class="max-w-2xl rounded-[28px] sm:rounded-[32px] bg-white/70 backdrop-blur-lg border border-white/60 shadow-2xl shadow-slate-200/70 px-6 py-8 sm:px-8 sm:py-10 md:px-12 md:py-12 relative overflow-hidden">
            <div class="pointer-events-none absolute inset-0 bg-gradient-to-b from-white/95 via-white/70 to-transparent"></div>
            <div class="pointer-events-none absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-white/0"></div>
            <div class="relative z-10">
             <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-100 border border-slate-200 text-slate-600 text-[11px] sm:text-xs font-bold uppercase tracking-widest">
              <span class="w-2 h-2 rounded-full bg-slate-500"></span>
              {{ $t('common.version') }}
            </div>
            
            <h1 class="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-bold text-slate-900 leading-[0.95] tracking-tight mt-5 sm:mt-6">
              {{ $t('home.hero.title_line1') }}<br/>
              <span class="text-transparent bg-clip-text bg-gradient-to-r from-emerald-600 to-sky-600">{{ $t('home.hero.title_line2') }}</span>
            </h1>
            
            <p class="text-base sm:text-lg md:text-xl text-slate-600 max-w-lg leading-relaxed mt-4 sm:mt-6">
              {{ $t('home.hero.subtitle') }}
            </p>

            <div class="flex flex-col sm:flex-row flex-wrap gap-4 pt-6">
               <router-link :to="{ name: 'Predict', params: { lang: $route.params.lang } }" class="btn btn-primary text-base px-8 py-4 shadow-xl shadow-emerald-700/20 w-full sm:w-auto">
                 {{ $t('common.buttons.create_plan') }}
               </router-link>
               <button @click="scrollToFeatures" class="btn btn-outline text-base px-8 py-4 w-full sm:w-auto">
                 {{ $t('common.buttons.about') }}
               </button>
            </div>
            </div>
          </div>
        </div>

      </div>
    </section>

    <!-- FEATURES -->
    <section id="features" class="py-24 bg-white border-y border-slate-100">
       <div class="layout">
          <div class="text-center max-w-3xl mx-auto mb-16">
             <h2 class="text-3xl font-bold text-slate-900 mb-4">{{ $t('home.features.title') }}</h2>
             <p class="text-slate-600">{{ $t('home.features.subtitle') }}</p>
          </div>

          <div class="grid md:grid-cols-3 gap-8">
             <!-- Feature 1 -->
             <div class="p-8 rounded-2xl bg-slate-50 border border-slate-100 hover:shadow-lg transition-shadow">
                <div class="w-12 h-12 bg-emerald-100 rounded-xl flex items-center justify-center text-emerald-700 mb-6">
                   <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                   </svg>
                </div>
                <h3 class="text-xl font-bold text-slate-900 mb-3">{{ $t('home.features.biometric.title') }}</h3>
                <p class="text-slate-600 leading-relaxed text-sm">
                   {{ $t('home.features.biometric.desc') }}
                </p>
             </div>

             <!-- Feature 2 -->
             <div class="p-8 rounded-2xl bg-slate-50 border border-slate-100 hover:shadow-lg transition-shadow">
                <div class="w-12 h-12 bg-sky-100 rounded-xl flex items-center justify-center text-sky-700 mb-6">
                   <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
                   </svg>
                </div>
                <h3 class="text-xl font-bold text-slate-900 mb-3">{{ $t('home.features.terrain.title') }}</h3>
                <p class="text-slate-600 leading-relaxed text-sm">
                   {{ $t('home.features.terrain.desc') }}
                </p>
             </div>

             <!-- Feature 3 -->
             <div class="p-8 rounded-2xl bg-slate-50 border border-slate-100 hover:shadow-lg transition-shadow">
                <div class="w-12 h-12 bg-amber-100 rounded-xl flex items-center justify-center text-amber-700 mb-6">
                   <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-6 h-6">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                   </svg>
                </div>
                <h3 class="text-xl font-bold text-slate-900 mb-3">{{ $t('home.features.pacing.title') }}</h3>
                <p class="text-slate-600 leading-relaxed text-sm">
                   {{ $t('home.features.pacing.desc') }}
                </p>
             </div>
          </div>
       </div>
    </section>

    <!-- TRUST / DISCLAIMER -->
    <section class="py-16">
       <div class="layout max-w-4xl mx-auto text-center">
          <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-50 border border-amber-100 text-amber-700 text-xs font-bold uppercase tracking-widest mb-6">
             <span class="text-lg">⚠</span> {{ $t('home.disclaimer.badge') }}
          </div>
          <h2 class="text-2xl font-bold text-slate-900 mb-4">{{ $t('home.disclaimer.title') }}</h2>
          <p class="text-slate-600 leading-relaxed">
             {{ $t('home.disclaimer.text') }}
          </p>
       </div>
    </section>
  </div>
</template>

<script setup>
import heroBackground from '../assets/background_hero.png'
const scrollToFeatures = () => {
  document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' })
}
</script>
