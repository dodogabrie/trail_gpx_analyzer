<template>
  <div>
    <section class="py-12 md:py-20">
      <div class="layout max-w-4xl">
        <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-100 border border-slate-200 text-slate-600 text-xs font-bold uppercase tracking-widest">
          {{ $t('howitworks.badge') }}
        </div>
        <h1 class="text-4xl md:text-5xl font-bold text-slate-900 mt-6">
          {{ $t('howitworks.title') }}
        </h1>
        <p class="text-lg text-slate-600 mt-4 leading-relaxed">
          {{ $t('howitworks.subtitle') }}
        </p>

        <div class="mt-10 grid gap-6">
          <div class="rounded-2xl border border-slate-200 bg-white p-6 md:p-8 shadow-sm">
            <h2 class="text-xl md:text-2xl font-bold text-slate-900">
              {{ $t('howitworks.physics.title') }}
            </h2>
            <p class="text-slate-600 mt-3 leading-relaxed">
              {{ $t('howitworks.physics.text') }}
            </p>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-white p-6 md:p-8 shadow-sm">
            <h2 class="text-xl md:text-2xl font-bold text-slate-900">
              {{ $t('howitworks.ml.title') }}
            </h2>
            <p class="text-slate-600 mt-3 leading-relaxed">
              {{ $t('howitworks.ml.text') }}
            </p>
          </div>
          <div class="rounded-2xl border border-slate-200 bg-white p-6 md:p-8 shadow-sm">
            <h2 class="text-xl md:text-2xl font-bold text-slate-900">
              {{ $t('howitworks.output.title') }}
            </h2>
            <p class="text-slate-600 mt-3 leading-relaxed">
              {{ $t('howitworks.output.text') }}
            </p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
