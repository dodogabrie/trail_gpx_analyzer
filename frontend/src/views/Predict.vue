<template>
  <div class="space-y-16">
    <!-- Header / Nav (New Simulation specific) -->
    <div class="flex items-center justify-between pb-6 border-b border-slate-200">
       <h1 class="text-3xl font-bold text-slate-900 uppercase tracking-tight">{{ $t('predict.title') }}</h1>
       
    </div>

    <div class="grid lg:grid-cols-2 gap-12 items-stretch">
        
        <!-- Upload Card -->
        <div class="relative order-2 lg:order-1 h-full">
           <!-- Decorative blob -->
           <div class="absolute -inset-4 bg-gradient-to-tr from-emerald-100 to-sky-100 rounded-[2rem] opacity-70 blur-2xl"></div>
           
           <!-- Main Card -->
           <div class="relative bg-white rounded-2xl shadow-xl border border-slate-100 p-8 md:p-10 space-y-6 h-full flex flex-col">
              <div v-if="!authStore.isAuthenticated" class="absolute inset-0 z-20 rounded-2xl bg-white/80 backdrop-blur-sm flex flex-col items-center justify-center text-center px-6">
                <div class="max-w-sm">
                  <div class="w-12 h-12 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center mx-auto mb-4">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.75" stroke="currentColor" class="w-6 h-6">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M16.5 10.5V7.875a4.125 4.125 0 10-8.25 0V10.5m-.75 0h9a2.25 2.25 0 012.25 2.25v5.25A2.25 2.25 0 0116.5 20.25h-9a2.25 2.25 0 01-2.25-2.25v-5.25A2.25 2.25 0 017.5 10.5z" />
                    </svg>
                  </div>
                  <h3 class="text-lg font-bold text-emerald-900 mb-2">{{ $t('predict.auth_required.title') }}</h3>
                  <p class="text-sm text-emerald-900/80 mb-5">{{ $t('predict.auth_required.text') }}</p>
                  <button @click="connectStrava" class="w-full btn btn-primary py-3">
                    {{ $t('predict.auth_required.button') }}
                  </button>
                </div>
              </div>
              
              <div class="flex items-center justify-between pb-4 border-b border-slate-100">
                 <h3 class="text-2xl md:text-3xl font-bold text-slate-800 uppercase tracking-wide">{{ $t('predict.upload_card.title') }}</h3>
                 <span class="text-xs text-slate-400 font-mono">.GPX</span>
              </div>

              <!-- Upload Area -->
              <div 
                class="border-2 border-dashed border-slate-300 rounded-xl p-12 text-center transition-all duration-300 hover:border-emerald-500 hover:bg-emerald-50/30 hover:scale-[1.02] cursor-pointer group flex-1 flex flex-col items-center justify-center"
                :class="!authStore.isAuthenticated ? 'opacity-40 pointer-events-none' : ''"
                @dragover.prevent="dragover = true"
                @dragleave.prevent="dragover = false"
                @drop.prevent="handleDrop"
                @click="triggerFileInput"
              >
                 <input 
                    type="file" 
                    ref="fileInput" 
                    class="hidden" 
                    accept=".gpx" 
                    @change="handleFileSelect" 
                 />
                 
                 <div class="w-20 h-20 bg-slate-50 rounded-full flex items-center justify-center mx-auto mb-6 text-slate-400 group-hover:text-emerald-600 group-hover:bg-white group-hover:shadow-md transition-all">
                    <svg v-if="uploading" class="animate-spin w-10 h-10" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <svg v-else xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-10 h-10">
                       <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                    </svg>
                 </div>
                 
                 <h4 class="text-lg font-bold text-slate-900 group-hover:text-emerald-700 mb-2">
                    {{ uploading ? $t('predict.upload_card.processing_text') : $t('predict.upload_card.drop_text') }}
                 </h4>
                 <p class="text-sm text-slate-500">{{ $t('predict.upload_card.browse_text') }}</p>
              </div>

              <!-- Error Message -->
              <div v-if="uploadError" class="p-4 bg-rose-50 border border-rose-100 rounded-lg text-sm text-rose-700 flex items-center gap-3">
                 <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-5 h-5"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clip-rule="evenodd" /></svg>
                 {{ uploadError }}
              </div>
           </div>
        </div>

        <!-- Instructions / Context -->
        <div class="space-y-8 order-1 lg:order-2 h-full">
           <div class="bg-white rounded-2xl p-8 md:p-10 border border-slate-200 shadow-sm h-full">
              <h3 class="text-2xl md:text-3xl font-bold text-slate-900 mb-6">{{ $t('predict.instructions.title') }}</h3>
              <ul class="space-y-6">
                 <li class="flex gap-4">
                    <div class="w-10 h-10 rounded-full bg-emerald-600 text-white flex items-center justify-center text-base font-bold shadow-md shadow-emerald-600/30 shrink-0">1</div>
                    <div>
                       <h4 class="font-bold text-slate-900 text-base md:text-lg">{{ $t('predict.instructions.step1.title') }}</h4>
                       <p class="text-base text-slate-600 mt-2 leading-relaxed">{{ $t('predict.instructions.step1.desc') }}</p>
                    </div>
                 </li>
                 <li class="flex gap-4">
                    <div class="w-10 h-10 rounded-full bg-emerald-600 text-white flex items-center justify-center text-base font-bold shadow-md shadow-emerald-600/30 shrink-0">2</div>
                    <div>
                       <h4 class="font-bold text-slate-900 text-base md:text-lg">{{ $t('predict.instructions.step2.title') }}</h4>
                       <p class="text-base text-slate-600 mt-2 leading-relaxed">{{ $t('predict.instructions.step2.desc') }}</p>
                    </div>
                 </li>
                 <li class="flex gap-4">
                    <div class="w-10 h-10 rounded-full bg-emerald-600 text-white flex items-center justify-center text-base font-bold shadow-md shadow-emerald-600/30 shrink-0">3</div>
                    <div>
                       <h4 class="font-bold text-slate-900 text-base md:text-lg">{{ $t('predict.instructions.step3.title') }}</h4>
                       <p class="text-base text-slate-600 mt-2 leading-relaxed">{{ $t('predict.instructions.step3.desc') }}</p>
                    </div>
                 </li>
              </ul>
           </div>
        </div>
    </div>

    <!-- Recent Files -->
    <section v-if="authStore.isAuthenticated">
       <div class="flex items-center justify-between mb-8">
         <h2 class="text-2xl font-bold text-slate-900 uppercase tracking-tight flex items-center gap-2">
           <span class="w-8 h-1 bg-emerald-700 rounded-full"></span>
           {{ $t('predict.recent.title') }}
         </h2>
       </div>

       <div v-if="loadingRecent" class="py-12 text-center text-slate-500">
          <div class="animate-spin inline-block w-6 h-6 border-2 border-current border-t-transparent rounded-full mb-2"></div>
          <div>{{ $t('predict.recent.loading') }}</div>
       </div>

       <div v-else-if="recentFiles.length === 0" class="bg-white border border-slate-200 rounded-xl p-12 text-center">
          <div class="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mx-auto mb-4 text-slate-300">
             <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="w-8 h-8">
               <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
             </svg>
          </div>
          <p class="text-slate-500">{{ $t('predict.recent.empty') }}</p>
       </div>

       <div v-else class="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          <router-link 
            v-for="file in recentFiles" 
            :key="file.id"
            :to="{ name: 'Prediction', params: { gpxId: file.id, lang: $route.params.lang } }"
            class="group bg-white border border-slate-200 rounded-xl p-5 hover:shadow-lg hover:border-emerald-300 transition-all"
          >
             <div class="flex justify-between items-start mb-4">
                <div class="bg-emerald-50 text-emerald-700 p-2 rounded-lg group-hover:bg-emerald-600 group-hover:text-white transition-colors">
                   <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-5 h-5">
                      <path stroke-linecap="round" stroke-linejoin="round" d="M9 6.75V15m6-6v8.25m.503 3.498l4.875-2.437c.381-.19.622-.58.622-1.006V4.82c0-.836-.88-1.38-1.628-1.006l-3.869 1.934c-.317.159-.69.159-1.006 0L9.503 3.252a1.125 1.125 0 00-1.006 0L3.622 5.689C3.24 5.88 3 6.27 3 6.695V19.18c0 .836.88 1.38 1.628 1.006l3.869-1.934c.317-.159.69-.159 1.006 0l4.994 2.497c.317.158.69.158 1.006 0z" />
                   </svg>
                </div>
                <span class="text-xs font-mono text-slate-400">{{ formatDate(file.created_at) }}</span>
             </div>
             
             <h3 class="font-bold text-slate-800 mb-1 truncate" :title="file.original_filename">
                {{ file.original_filename }}
             </h3>
             <div class="text-xs text-slate-500 flex gap-3">
                <span v-if="file.distance_km">📍 {{ file.distance_km.toFixed(1) }} km</span>
                <!-- Elevation would be good here if available in the shallow object -->
             </div>
          </router-link>
       </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useI18n } from 'vue-i18n'
import api from '../services/api'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const { locale } = useI18n()

const fileInput = ref(null)
const dragover = ref(false)
const uploading = ref(false)
const uploadError = ref(null)

const recentFiles = ref([])
const loadingRecent = ref(true)

onMounted(async () => {
  await fetchRecentFiles()
})

const connectStrava = async () => {
  const authUrl = await authStore.getStravaAuthUrl()
  window.location.href = authUrl
}

const triggerFileInput = () => {
  if (!authStore.isAuthenticated) return
  fileInput.value.click()
}

const handleFileSelect = (event) => {
  const file = event.target.files[0]
  if (file) processFile(file)
}

const handleDrop = (event) => {
  if (!authStore.isAuthenticated) return
  dragover.value = false
  const file = event.dataTransfer.files[0]
  if (file) processFile(file)
}

const processFile = async (file) => {
  if (!authStore.isAuthenticated) return
  if (!file.name.toLowerCase().endsWith('.gpx')) {
    uploadError.value = "Please upload a valid .gpx file"
    return
  }

  uploading.value = true
  uploadError.value = null

  const formData = new FormData()
  formData.append('file', file)

  try {
    const response = await api.post('/gpx/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
    
    // Assuming backend returns { id: ..., ... }
    const gpxId = response.data.id
    router.push({ name: 'Prediction', params: { gpxId, lang: route.params.lang } })
    
  } catch (err) {
    console.error(err)
    uploadError.value = err.response?.data?.error || "Failed to upload file"
  } finally {
    uploading.value = false
  }
}

const fetchRecentFiles = async () => {
  try {
    const response = await api.get('/gpx/list') 
    recentFiles.value = response.data.files || []
  } catch (err) {
    console.warn("Could not fetch recent files", err)
    recentFiles.value = []
  } finally {
    loadingRecent.value = false
  }
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString(locale.value, {
     month: 'short', day: 'numeric'
  })
}
</script>
