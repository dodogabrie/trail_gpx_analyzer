<template>
  <div>
    <section class="py-12 md:py-20">
      <div class="layout max-w-4xl">
        <!-- Header -->
        <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-100 border border-slate-200 text-slate-600 text-xs font-bold uppercase tracking-widest">
          {{ $t('howitworks.badge') }}
        </div>
        <h1 class="text-4xl md:text-5xl font-bold text-slate-900 mt-6">
          {{ $t('howitworks.title') }}
        </h1>
        <p class="text-lg text-slate-600 mt-4 leading-relaxed">
          {{ $t('howitworks.subtitle') }}
        </p>

        <!-- Three Tier System -->
        <div class="mt-12">
          <h2 class="text-2xl md:text-3xl font-bold text-slate-900 mb-6">
            {{ $t('howitworks.tiers.title') }}
          </h2>
          <p class="text-slate-600 mb-8">
            {{ $t('howitworks.tiers.intro') }}
          </p>

          <!-- Tier Cards -->
          <div class="grid gap-4">
            <!-- Tier 1 -->
            <div class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm relative overflow-hidden">
              <div class="absolute top-0 right-0 w-24 h-24 bg-slate-100 rounded-bl-full opacity-50"></div>
              <div class="flex items-start gap-4">
                <div class="flex-shrink-0 w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center text-slate-600 font-bold text-lg">
                  1
                </div>
                <div class="flex-1">
                  <div class="flex items-center gap-2 mb-1">
                    <h3 class="text-lg font-bold text-slate-900">{{ $t('howitworks.tiers.tier1.title') }}</h3>
                    <span class="text-xs font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">{{ $t('howitworks.tiers.tier1.activities') }}</span>
                  </div>
                  <p class="text-slate-600 text-sm leading-relaxed">
                    {{ $t('howitworks.tiers.tier1.text') }}
                  </p>
                </div>
              </div>
            </div>

            <!-- Tier 2 -->
            <div class="rounded-2xl border border-emerald-200 bg-emerald-50/30 p-6 shadow-sm relative overflow-hidden">
              <div class="absolute top-0 right-0 w-24 h-24 bg-emerald-100 rounded-bl-full opacity-50"></div>
              <div class="flex items-start gap-4">
                <div class="flex-shrink-0 w-12 h-12 rounded-xl bg-emerald-100 flex items-center justify-center text-emerald-700 font-bold text-lg">
                  2
                </div>
                <div class="flex-1">
                  <div class="flex items-center gap-2 mb-1">
                    <h3 class="text-lg font-bold text-slate-900">{{ $t('howitworks.tiers.tier2.title') }}</h3>
                    <span class="text-xs font-medium text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full">{{ $t('howitworks.tiers.tier2.activities') }}</span>
                  </div>
                  <p class="text-slate-600 text-sm leading-relaxed">
                    {{ $t('howitworks.tiers.tier2.text') }}
                  </p>
                </div>
              </div>
            </div>

            <!-- Tier 3 -->
            <div class="rounded-2xl border border-amber-200 bg-amber-50/30 p-6 shadow-sm relative overflow-hidden">
              <div class="absolute top-0 right-0 w-24 h-24 bg-amber-100 rounded-bl-full opacity-50"></div>
              <div class="flex items-start gap-4">
                <div class="flex-shrink-0 w-12 h-12 rounded-xl bg-amber-100 flex items-center justify-center text-amber-700 font-bold text-lg">
                  3
                </div>
                <div class="flex-1">
                  <div class="flex items-center gap-2 mb-1">
                    <h3 class="text-lg font-bold text-slate-900">{{ $t('howitworks.tiers.tier3.title') }}</h3>
                    <span class="text-xs font-medium text-amber-700 bg-amber-100 px-2 py-0.5 rounded-full">{{ $t('howitworks.tiers.tier3.activities') }}</span>
                  </div>
                  <p class="text-slate-600 text-sm leading-relaxed">
                    {{ $t('howitworks.tiers.tier3.text') }}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- What We Learn -->
        <div class="mt-16">
          <h2 class="text-2xl md:text-3xl font-bold text-slate-900 mb-6">
            {{ $t('howitworks.learning.title') }}
          </h2>
          <div class="grid md:grid-cols-2 gap-4">
            <div class="rounded-xl border border-slate-200 bg-white p-5">
              <div class="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center mb-3">
                <span class="text-emerald-600 text-lg">&#x2197;</span>
              </div>
              <h3 class="font-bold text-slate-900 mb-1">{{ $t('howitworks.learning.uphill.title') }}</h3>
              <p class="text-slate-600 text-sm">{{ $t('howitworks.learning.uphill.text') }}</p>
            </div>
            <div class="rounded-xl border border-slate-200 bg-white p-5">
              <div class="w-10 h-10 rounded-lg bg-rose-100 flex items-center justify-center mb-3">
                <span class="text-rose-600 text-lg">&#x2198;</span>
              </div>
              <h3 class="font-bold text-slate-900 mb-1">{{ $t('howitworks.learning.downhill.title') }}</h3>
              <p class="text-slate-600 text-sm">{{ $t('howitworks.learning.downhill.text') }}</p>
            </div>
            <div class="rounded-xl border border-slate-200 bg-white p-5">
              <div class="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center mb-3">
                <span class="text-blue-600 text-lg">&#x23F1;</span>
              </div>
              <h3 class="font-bold text-slate-900 mb-1">{{ $t('howitworks.learning.fatigue.title') }}</h3>
              <p class="text-slate-600 text-sm">{{ $t('howitworks.learning.fatigue.text') }}</p>
            </div>
            <div class="rounded-xl border border-slate-200 bg-white p-5">
              <div class="w-10 h-10 rounded-lg bg-purple-100 flex items-center justify-center mb-3">
                <span class="text-purple-600 text-lg">&#x1F3C3;</span>
              </div>
              <h3 class="font-bold text-slate-900 mb-1">{{ $t('howitworks.learning.baseline.title') }}</h3>
              <p class="text-slate-600 text-sm">{{ $t('howitworks.learning.baseline.text') }}</p>
            </div>
          </div>
        </div>

        <!-- Physics Foundation -->
        <div class="mt-16">
          <h2 class="text-2xl md:text-3xl font-bold text-slate-900 mb-6">
            {{ $t('howitworks.physics.title') }}
          </h2>
          <div class="rounded-2xl border border-slate-200 bg-white p-6 md:p-8 shadow-sm">
            <p class="text-slate-600 leading-relaxed">
              {{ $t('howitworks.physics.text') }}
            </p>
            <!-- Placeholder for pace vs grade chart -->
            <div class="mt-6 rounded-xl bg-slate-50 border border-slate-200 p-8 text-center">
              <p class="text-slate-400 text-sm">{{ $t('howitworks.physics.chart_placeholder') }}</p>
            </div>
          </div>
        </div>

        <!-- Effort Levels -->
        <div class="mt-16">
          <h2 class="text-2xl md:text-3xl font-bold text-slate-900 mb-6">
            {{ $t('howitworks.effort.title') }}
          </h2>
          <p class="text-slate-600 mb-6">
            {{ $t('howitworks.effort.intro') }}
          </p>
          <div class="grid md:grid-cols-3 gap-4">
            <div class="rounded-xl border border-rose-200 bg-rose-50/50 p-5 text-center">
              <div class="text-2xl mb-2">&#x1F3C1;</div>
              <h3 class="font-bold text-slate-900">{{ $t('howitworks.effort.race.title') }}</h3>
              <p class="text-slate-600 text-sm mt-1">{{ $t('howitworks.effort.race.text') }}</p>
            </div>
            <div class="rounded-xl border border-emerald-200 bg-emerald-50/50 p-5 text-center">
              <div class="text-2xl mb-2">&#x1F3C3;</div>
              <h3 class="font-bold text-slate-900">{{ $t('howitworks.effort.training.title') }}</h3>
              <p class="text-slate-600 text-sm mt-1">{{ $t('howitworks.effort.training.text') }}</p>
            </div>
            <div class="rounded-xl border border-blue-200 bg-blue-50/50 p-5 text-center">
              <div class="text-2xl mb-2">&#x1F6B6;</div>
              <h3 class="font-bold text-slate-900">{{ $t('howitworks.effort.recovery.title') }}</h3>
              <p class="text-slate-600 text-sm mt-1">{{ $t('howitworks.effort.recovery.text') }}</p>
            </div>
          </div>
        </div>

        <!-- Privacy Note -->
        <div class="mt-16">
          <div class="rounded-2xl border border-slate-200 bg-slate-50 p-6 md:p-8">
            <div class="flex items-start gap-4">
              <div class="flex-shrink-0 w-10 h-10 rounded-lg bg-slate-200 flex items-center justify-center">
                <span class="text-slate-600 text-lg">&#x1F512;</span>
              </div>
              <div>
                <h3 class="font-bold text-slate-900 mb-2">{{ $t('howitworks.privacy.title') }}</h3>
                <p class="text-slate-600 text-sm leading-relaxed">
                  {{ $t('howitworks.privacy.text') }}
                </p>
              </div>
            </div>
          </div>
        </div>

      </div>
    </section>
  </div>
</template>
