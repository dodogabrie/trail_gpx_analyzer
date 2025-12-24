<template>
  <div class="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
    <TransitionGroup name="achievement">
      <div
        v-for="achievement in visibleAchievements"
        :key="achievement.id"
        class="bg-white border-2 border-yellow-400 rounded-lg shadow-lg p-4 transform hover:scale-105 transition-all duration-300"
        @click="markAsRead(achievement.id)"
      >
        <div class="flex items-start gap-3">
          <div class="text-4xl">{{ achievement.icon }} {{ achievement.category_icon }}</div>
          <div class="flex-1">
            <div class="flex items-center gap-2">
              <h3 class="font-bold text-gray-900">{{ achievement.name }}</h3>
              <span class="text-xs bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded">NEW</span>
            </div>
            <p class="text-sm text-gray-600 mt-1">{{ achievement.description }}</p>
            <p class="text-xs text-gray-400 mt-2">{{ formatDate(achievement.earned_at) }}</p>
          </div>
          <button
            class="text-gray-400 hover:text-gray-600 text-xs"
            @click.stop="dismiss(achievement.id)"
          >
            ✕
          </button>
        </div>
      </div>
    </TransitionGroup>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const visibleAchievements = ref([])
const pollInterval = ref(null)

const fetchNewAchievements = async () => {
  try {
    const response = await fetch('http://localhost:5000/api/performance/achievements?unread_only=true')
    if (response.ok) {
      const data = await response.json()
      const newAchievements = data.achievements || []

      // Add new achievements that aren't already visible
      for (const achievement of newAchievements) {
        if (!visibleAchievements.value.find(a => a.id === achievement.id)) {
          visibleAchievements.value.push(achievement)

          // Auto-dismiss after 10 seconds
          setTimeout(() => {
            dismiss(achievement.id)
          }, 10000)
        }
      }
    }
  } catch (error) {
    console.error('Failed to fetch achievements:', error)
  }
}

const markAsRead = async (achievementId) => {
  try {
    await fetch(`http://localhost:5000/api/performance/achievements/${achievementId}/mark-read`, {
      method: 'POST'
    })
    dismiss(achievementId)
  } catch (error) {
    console.error('Failed to mark achievement as read:', error)
  }
}

const dismiss = (achievementId) => {
  const index = visibleAchievements.value.findIndex(a => a.id === achievementId)
  if (index !== -1) {
    visibleAchievements.value.splice(index, 1)
  }
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
  // Check immediately
  fetchNewAchievements()

  // Poll every 30 seconds for new achievements
  pollInterval.value = setInterval(fetchNewAchievements, 30000)
})

// Cleanup on unmount
import { onUnmounted } from 'vue'
onUnmounted(() => {
  if (pollInterval.value) {
    clearInterval(pollInterval.value)
  }
})
</script>

<style scoped>
.achievement-enter-active {
  animation: slide-in-right 0.5s ease-out;
}

.achievement-leave-active {
  animation: slide-out-right 0.3s ease-in;
}

@keyframes slide-in-right {
  from {
    transform: translateX(100%) scale(0.8);
    opacity: 0;
  }
  to {
    transform: translateX(0) scale(1);
    opacity: 1;
  }
}

@keyframes slide-out-right {
  from {
    transform: translateX(0) scale(1);
    opacity: 1;
  }
  to {
    transform: translateX(100%) scale(0.8);
    opacity: 0;
  }
}
</style>
