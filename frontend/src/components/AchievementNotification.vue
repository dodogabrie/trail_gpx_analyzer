<template>
  <!-- Compact notification badge -->
  <div v-if="unreadCount > 0" class="fixed top-4 right-4 z-50">
    <button
      @click="showPanel = !showPanel"
      class="relative bg-yellow-400 hover:bg-yellow-500 text-yellow-900 px-4 py-2 rounded-full shadow-lg transition-all flex items-center gap-2 font-semibold"
    >
      <span class="text-xl">🏆</span>
      <span>{{ unreadCount }} new achievement{{ unreadCount > 1 ? 's' : '' }}</span>
    </button>

    <!-- Expandable panel -->
    <Transition name="slide-down">
      <div
        v-if="showPanel"
        class="absolute top-14 right-0 w-96 max-h-[500px] overflow-y-auto bg-white rounded-lg shadow-xl border border-gray-200"
      >
        <div class="sticky top-0 bg-gradient-to-r from-yellow-400 to-yellow-500 p-4 flex items-center justify-between">
          <h3 class="font-bold text-yellow-900">New Achievements</h3>
          <button
            @click="markAllAsRead"
            class="text-xs text-yellow-900 hover:text-yellow-800 underline"
          >
            Mark all read
          </button>
        </div>

        <div class="p-2 space-y-2">
          <div
            v-for="achievement in visibleAchievements"
            :key="achievement.id"
            class="p-3 bg-yellow-50 border border-yellow-200 rounded hover:bg-yellow-100 transition-colors cursor-pointer"
            @click="markAsRead(achievement.id)"
          >
            <div class="flex items-start gap-3">
              <div class="text-3xl">{{ achievement.icon }} {{ achievement.category_icon }}</div>
              <div class="flex-1 min-w-0">
                <h4 class="font-bold text-gray-900 text-sm">{{ achievement.name }}</h4>
                <p class="text-xs text-gray-600 mt-1">{{ achievement.description }}</p>
                <p class="text-xs text-gray-400 mt-1">{{ formatDate(achievement.earned_at) }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../services/api'

const visibleAchievements = ref([])
const pollInterval = ref(null)
const showPanel = ref(false)

const unreadCount = computed(() => visibleAchievements.value.length)

const fetchNewAchievements = async () => {
  try {
    const response = await api.get('/performance/achievements', {
      params: { unread_only: true }
    })
    const data = response.data
    const newAchievements = data.achievements || []

    // Update achievements list
    visibleAchievements.value = newAchievements
  } catch (error) {
    console.error('Failed to fetch achievements:', error)
  }
}

const markAsRead = async (achievementId) => {
  try {
    await api.post(`/performance/achievements/${achievementId}/mark-read`)
    const index = visibleAchievements.value.findIndex(a => a.id === achievementId)
    if (index !== -1) {
      visibleAchievements.value.splice(index, 1)
    }
  } catch (error) {
    console.error('Failed to mark achievement as read:', error)
  }
}

const markAllAsRead = async () => {
  for (const achievement of visibleAchievements.value) {
    try {
      await api.post(`/performance/achievements/${achievement.id}/mark-read`)
    } catch (error) {
      console.error('Failed to mark achievement as read:', error)
    }
  }
  visibleAchievements.value = []
  showPanel.value = false
}

const formatDate = (dateStr) => {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now - date
  const diffMins = Math.floor(diffMs / 60000)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffMins < 1440) return `${Math.floor(diffMins / 60)}h ago`
  return `${Math.floor(diffMins / 1440)}d ago`
}

onMounted(() => {
  fetchNewAchievements()
  // Poll every 60 seconds (less frequent)
  pollInterval.value = setInterval(fetchNewAchievements, 60000)
})

import { onUnmounted, computed } from 'vue'
onUnmounted(() => {
  if (pollInterval.value) {
    clearInterval(pollInterval.value)
  }
})
</script>

<style scoped>
.slide-down-enter-active {
  animation: slide-down 0.3s ease-out;
}

.slide-down-leave-active {
  animation: slide-down 0.2s ease-in reverse;
}

@keyframes slide-down {
  from {
    transform: translateY(-10px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}
</style>
