<template>
  <div class="space-y-6">
    <div class="bg-amber-50 border border-amber-200 rounded p-4">
      <div class="font-semibold text-amber-900">Review & Edit Calibration</div>
      <div class="text-sm text-amber-800 mt-1">
        Changes here affect your personal pace profile used for predictions.
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div class="lg:col-span-1 space-y-4">
        <div class="bg-white border border-gray-200 rounded p-4">
          <div class="flex items-center justify-between">
            <h3 class="font-semibold">Flat Pace</h3>
            <button
              class="text-sm text-blue-600 hover:text-blue-800"
              type="button"
              @click="resetToOriginal"
            >
              Reset
            </button>
          </div>

          <div class="mt-3">
            <label class="block text-sm text-gray-600 mb-1">min/km</label>
            <input
              v-model.number="editableFlatPace"
              type="number"
              min="2.5"
              max="20"
              step="0.1"
              class="w-full border rounded px-3 py-2"
            />
            <div v-if="flatPaceError" class="text-sm text-red-600 mt-2">
              {{ flatPaceError }}
            </div>
          </div>
        </div>

        <div class="bg-white border border-gray-200 rounded p-4">
          <h3 class="font-semibold">Pace at Grades</h3>
          <div class="text-sm text-gray-600 mt-1">
            Set your expected pace at each grade
          </div>

          <div class="mt-4 space-y-2">
            <div
              v-for="grade in anchorGrades"
              :key="grade"
              class="grid grid-cols-12 gap-2 items-center"
            >
              <div class="col-span-2 text-sm text-gray-700 font-medium">
                {{ formatGradeLabel(grade) }}
              </div>
              <div class="col-span-5">
                <input
                  :value="getPaceForGrade(grade)"
                  type="text"
                  placeholder="m:ss"
                  class="w-full border rounded px-2 py-1 text-sm"
                  @input="onPaceInput(grade, $event)"
                  @blur="formatPaceInput(grade, $event)"
                />
              </div>
              <div class="col-span-5 text-xs text-gray-500 text-right">
                <span v-if="anchorSampleCounts[String(grade)] !== undefined">
                  {{ anchorSampleCounts[String(grade)] }} samples
                </span>
                <span v-else class="italic">no data</span>
              </div>
            </div>
          </div>

          <div v-if="anchorsError" class="text-sm text-red-600 mt-3">
            {{ anchorsError }}
          </div>
        </div>
      </div>

      <div class="lg:col-span-2 bg-white border border-gray-200 rounded p-4">
        <div class="flex items-center justify-between">
          <h3 class="font-semibold">Pace Profile (Star Plot)</h3>
          <div class="text-sm text-gray-500">
            Baseline vs Your Personalization
          </div>
        </div>
        <div class="text-xs text-gray-500 mt-1">
          Larger area = better performance. Baseline (gray) is reference, your personalization (blue) shows deviation.
        </div>
        <div class="text-xs font-medium text-blue-600">
          Click the BLUE DOTS to quick-edit each anchor point
        </div>

        <div class="mt-3 h-[480px] relative">
          <!-- Downhill label (left) -->
          <div class="absolute left-4 top-1/2 -translate-y-1/2 z-10 font-semibold text-green-600">
            Downhill
          </div>

          <!-- Uphill label (right) -->
          <div class="absolute right-4 top-1/2 -translate-y-1/2 z-10 font-semibold text-red-600">
            Uphill
          </div>

          <v-chart
            :option="radarChartOption"
            autoresize
            class="w-full h-full"
            @click="handleChartClick"
          />

          <!-- Quick edit popover -->
          <div
            v-if="editingAnchor !== null"
            class="absolute bg-white border-2 border-blue-500 rounded-lg shadow-xl p-4 z-50 min-w-[280px]"
            :style="popoverStyle"
          >
            <div class="flex items-center justify-between mb-3">
              <div class="font-semibold text-sm">
                {{ formatGradeLabel(editingAnchor) }}
              </div>
              <button
                type="button"
                class="text-gray-400 hover:text-gray-600"
                @click="editingAnchor = null"
              >
                ✕
              </button>
            </div>

            <div class="space-y-3">
              <label class="block text-sm font-medium text-gray-700">Pace (min/km)</label>
              <input
                v-model.number="quickEditPaceValue"
                type="range"
                :min="MIN_PACE"
                :max="MAX_PACE"
                step="0.1"
                class="w-full"
                @input="updateQuickEditFromPace"
              />
              <div class="flex items-center gap-2">
                <input
                  :value="formatPace(quickEditPaceValue)"
                  type="text"
                  placeholder="m:ss"
                  class="w-20 border rounded px-2 py-1 text-sm"
                  @input="onQuickEditPaceInput"
                  @blur="formatQuickEditPace"
                />
                <span class="text-xs text-gray-600">
                  min/km
                </span>
              </div>

              <div v-if="quickEditPaceError" class="text-xs text-red-600">
                {{ quickEditPaceError }}
              </div>

              <div class="flex items-center justify-between pt-2 border-t">
                <button
                  type="button"
                  class="text-xs text-gray-600 hover:text-gray-800 underline"
                  @click="resetAnchorToBaseline"
                >
                  Reset to baseline
                </button>
                <button
                  type="button"
                  class="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
                  @click="editingAnchor = null"
                >
                  Done
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="flex items-center justify-end gap-3">
      <button
        type="button"
        class="px-4 py-2 rounded border border-gray-300 hover:bg-gray-50"
        @click="$emit('skip')"
      >
        Skip
      </button>
      <button
        type="button"
        class="px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-60"
        :disabled="!canSave"
        @click="emitSave"
      >
        Save & Continue
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { RadarChart } from 'echarts/charts'
import { RadarComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, RadarChart, RadarComponent, TooltipComponent, LegendComponent])

const props = defineProps({
  flatPace: { type: Number, required: true },
  anchorRatios: { type: Object, required: true },
  globalCurve: { type: Array, required: true },
  diagnostics: { type: Object, required: false, default: () => ({}) },
  calibrationActivityStreams: { type: Object, required: false, default: () => ({}) }
})

const emit = defineEmits(['save', 'skip'])

// Radar display order: 0% at top, downhill on left, uphill on right
const anchorGrades = [-30, -20, -10, 0, 10, 20, 30]
const radarDisplayOrder = [0, -10, -20, -30, 30, 20, 10] // Counter-clockwise from top

const editableFlatPace = ref(props.flatPace)
const editableAnchorRatios = reactive({})

// Quick edit state
const editingAnchor = ref(null)
const quickEditValue = ref(1.0)
const quickEditPaceValue = ref(5.0)
const popoverPosition = ref({ x: 0, y: 0 })

const resetToOriginal = () => {
  editableFlatPace.value = props.flatPace
  Object.keys(editableAnchorRatios).forEach(k => delete editableAnchorRatios[k])
  for (const [k, v] of Object.entries(props.anchorRatios || {})) {
    editableAnchorRatios[String(k)] = v
  }
}

watch(
  () => [props.flatPace, props.anchorRatios],
  () => resetToOriginal(),
  { immediate: true, deep: true }
)

const clamp = (value, min, max) => Math.min(max, Math.max(min, value))

// Parse pace string "m:ss" or decimal to minutes
const parsePaceString = (str) => {
  if (!str) return null
  str = String(str).trim()

  // Check for m:ss format
  if (str.includes(':')) {
    const parts = str.split(':')
    if (parts.length !== 2) return null
    const mins = parseInt(parts[0], 10)
    const secs = parseInt(parts[1], 10)
    if (!Number.isFinite(mins) || !Number.isFinite(secs)) return null
    return mins + secs / 60
  }

  // Decimal format
  const parsed = parseFloat(str)
  return Number.isFinite(parsed) ? parsed : null
}

// Get displayed pace for a grade (converts ratio to pace)
const getPaceForGrade = (grade) => {
  const ratio = editableAnchorRatios[String(grade)]
  if (!ratio || !Number.isFinite(ratio)) return ''
  const pace = editableFlatPace.value * ratio
  return formatPace(pace)
}

// Handle pace input (converts pace to ratio)
const onPaceInput = (grade, event) => {
  const raw = event?.target?.value
  if (!raw || raw === '') {
    delete editableAnchorRatios[String(grade)]
    return
  }

  const paceMinutes = parsePaceString(raw)
  if (paceMinutes === null || !Number.isFinite(paceMinutes)) return

  const flatPace = Number(editableFlatPace.value)
  if (!flatPace || flatPace <= 0) return

  const ratio = paceMinutes / flatPace
  const clampedRatio = clamp(ratio, 0.3, 6.0)
  editableAnchorRatios[String(grade)] = clampedRatio
}

// Format pace input on blur
const formatPaceInput = (grade, event) => {
  const ratio = editableAnchorRatios[String(grade)]
  if (ratio && Number.isFinite(ratio)) {
    const pace = editableFlatPace.value * ratio
    event.target.value = formatPace(pace)
  }
}

const formatGradeLabel = (grade) => (grade >= 0 ? `+${grade}%` : `${grade}%`)

const formatPace = (decimalMinutes) => {
  if (!Number.isFinite(decimalMinutes) || decimalMinutes <= 0) {
    return 'N/A'
  }
  const mins = Math.floor(decimalMinutes)
  const secs = Math.round((decimalMinutes - mins) * 60)
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

const anchorSampleCounts = computed(() => props.diagnostics?.anchor_sample_counts || {})

const cleanedAnchorRatios = computed(() => {
  const out = {}
  for (const [k, v] of Object.entries(editableAnchorRatios)) {
    const ratio = Number(v)
    if (Number.isFinite(ratio)) out[String(k)] = ratio
  }
  return out
})

const flatPaceError = computed(() => {
  const pace = Number(editableFlatPace.value)
  if (!Number.isFinite(pace)) return 'Flat pace must be a number'
  if (pace <= 0 || pace > 20) return 'Flat pace must be between 0 and 20 min/km'
  return null
})

const anchorsError = computed(() => {
  const anchors = cleanedAnchorRatios.value
  const count = Object.keys(anchors).length
  if (count < 3) return 'Set at least 3 pace values to save'
  const flatPace = Number(editableFlatPace.value)
  for (const [grade, ratio] of Object.entries(anchors)) {
    const pace = flatPace * ratio
    if (pace < MIN_PACE || pace > MAX_PACE) {
      return `Pace at ${grade}% out of range (${formatPace(MIN_PACE)}–${formatPace(MAX_PACE)}/km)`
    }
  }
  return null
})

const canSave = computed(() => !flatPaceError.value && !anchorsError.value)

const emitSave = () => {
  if (!canSave.value) return
  emit('save', {
    flat_pace_min_per_km: Number(editableFlatPace.value),
    anchor_ratios: cleanedAnchorRatios.value
  })
}

const sortByGrade = (curve) =>
  [...(curve || [])]
    .map(p => ({ grade: Number(p.grade), median: Number(p.median) }))
    .filter(p => Number.isFinite(p.grade) && Number.isFinite(p.median))
    .sort((a, b) => a.grade - b.grade)

const interp1 = (xs, ys, x) => {
  if (!xs.length) return null
  if (x <= xs[0]) return ys[0]
  if (x >= xs[xs.length - 1]) return ys[ys.length - 1]
  for (let i = 1; i < xs.length; i++) {
    if (x <= xs[i]) {
      const x0 = xs[i - 1]
      const x1 = xs[i]
      const y0 = ys[i - 1]
      const y1 = ys[i]
      const t = (x - x0) / (x1 - x0)
      return y0 + t * (y1 - y0)
    }
  }
  return ys[ys.length - 1]
}

// Chart interaction handlers
const handleChartClick = (params) => {
  console.log('Chart click params:', params) // Debug log

  // ONLY accept clicks on "Your Personalization" series (blue dots)
  if (params.componentType === 'series' && params.seriesName === 'Your Personalization') {
    // For radar charts, the actual indicator index is in __dimIdx, not dataIndex!
    const dimIdx = params.event?.target?.__dimIdx
    console.log('__dimIdx:', dimIdx, 'params.dataIndex:', params.dataIndex)

    let dataIndex = dimIdx !== undefined ? dimIdx : params.dataIndex

    // Validate dataIndex
    if (dataIndex !== undefined && dataIndex >= 0 && dataIndex < radarDisplayOrder.length) {
      const grade = radarDisplayOrder[dataIndex]
      console.log('Opening edit for grade:', grade, '(index:', dataIndex, ')')

      editingAnchor.value = grade

      // Get current ratio or fallback to baseline
      const currentRatio = editableAnchorRatios[String(grade)]
      let ratio
      if (currentRatio && Number.isFinite(currentRatio)) {
        ratio = currentRatio
      } else {
        // Fallback to global baseline
        const globalCurveSorted = sortByGrade(props.globalCurve)
        ratio = interp1(
          globalCurveSorted.map(p => p.grade),
          globalCurveSorted.map(p => p.median),
          grade
        ) || 1.0
      }

      quickEditValue.value = ratio
      quickEditPaceValue.value = editableFlatPace.value * ratio

      // Position popover
      popoverPosition.value = {
        x: params.event?.offsetX || 250,
        y: params.event?.offsetY || 200
      }
    } else {
      console.log('Invalid dataIndex:', dataIndex)
    }
  } else {
    console.log('Not personalization series. SeriesName:', params.seriesName)
  }
}

// Pace validation constants
const MIN_PACE = 2.67  // 2:40/km in decimal minutes
const MAX_PACE = 25.0  // 25:00/km

const minRatioForPace = computed(() => {
  const pace = Number(editableFlatPace.value)
  return Math.max(0.3, MIN_PACE / pace)
})

const maxRatioForPace = computed(() => {
  const pace = Number(editableFlatPace.value)
  return Math.min(6.0, MAX_PACE / pace)
})

const quickEditPaceError = computed(() => {
  if (editingAnchor.value === null) return null
  const pace = quickEditPaceValue.value
  if (pace < MIN_PACE) {
    return `Pace too fast (min: ${formatPace(MIN_PACE)}/km)`
  }
  if (pace > MAX_PACE) {
    return `Pace too slow (max: ${formatPace(MAX_PACE)}/km)`
  }
  return null
})

const updateQuickEditFromPace = () => {
  if (editingAnchor.value !== null) {
    const clampedPace = clamp(quickEditPaceValue.value, MIN_PACE, MAX_PACE)
    quickEditPaceValue.value = clampedPace

    const flatPace = Number(editableFlatPace.value)
    if (!flatPace || flatPace <= 0) return

    const ratio = clampedPace / flatPace
    const clampedRatio = clamp(ratio, 0.3, 6.0)
    quickEditValue.value = clampedRatio
    editableAnchorRatios[String(editingAnchor.value)] = clampedRatio
  }
}

const onQuickEditPaceInput = (event) => {
  const raw = event?.target?.value
  if (!raw) return

  const paceMinutes = parsePaceString(raw)
  if (paceMinutes === null || !Number.isFinite(paceMinutes)) return

  quickEditPaceValue.value = paceMinutes
  updateQuickEditFromPace()
}

const formatQuickEditPace = (event) => {
  if (Number.isFinite(quickEditPaceValue.value)) {
    event.target.value = formatPace(quickEditPaceValue.value)
  }
}

const resetAnchorToBaseline = () => {
  if (editingAnchor.value !== null) {
    // Get baseline ratio for this grade
    const globalCurveSorted = sortByGrade(props.globalCurve)
    const globalRatio = interp1(
      globalCurveSorted.map(p => p.grade),
      globalCurveSorted.map(p => p.median),
      editingAnchor.value
    ) || 1.0

    quickEditValue.value = globalRatio
    quickEditPaceValue.value = editableFlatPace.value * globalRatio
    editableAnchorRatios[String(editingAnchor.value)] = globalRatio
  }
}

const popoverStyle = computed(() => {
  return {
    left: `${popoverPosition.value.x + 20}px`,
    top: `${popoverPosition.value.y - 60}px`
  }
})

const radarChartOption = computed(() => {
  const pace = Number(editableFlatPace.value)
  const globalCurveSorted = sortByGrade(props.globalCurve)
  const anchors = cleanedAnchorRatios.value

  // Use PERFORMANCE SCORE (inverted ratio) for intuitive visualization:
  // - Higher score = better performance = larger area = GOOD
  // - Lower score = worse performance = smaller area = BAD
  // - Baseline is always 1.0 (perfect equilateral heptagon)
  // - User score = baseline_ratio / user_ratio

  // Build radar indicators in display order (0% top, -grades left, +grades right)
  const indicators = radarDisplayOrder.map(grade => {
    return {
      name: `${grade >= 0 ? '+' : ''}${grade}%`,
      max: 2.0,  // Max performance (2x better than baseline)
      min: 0.3,  // Min performance (3x worse than baseline)
      splitNumber: 4  // Explicitly set split number to avoid warnings
    }
  })

  // Baseline data (ALWAYS 1.0 = perfect equilateral heptagon)
  const baselineData = radarDisplayOrder.map(() => 1.0)

  // User performance score (baseline_ratio / user_ratio)
  const personalizedData = radarDisplayOrder.map(grade => {
    const globalRatio = interp1(
      globalCurveSorted.map(p => p.grade),
      globalCurveSorted.map(p => p.median),
      grade
    ) || 1.0

    const userRatio = anchors[String(grade)]
    if (!userRatio || !Number.isFinite(userRatio) || userRatio <= 0) {
      // No user data = same as baseline = 1.0
      return 1.0
    }

    // Performance score = baseline / user
    // If user is faster (lower ratio): score > 1.0 (good, larger area)
    // If user is slower (higher ratio): score < 1.0 (bad, smaller area)
    const performanceScore = globalRatio / userRatio

    // Validate result
    if (!Number.isFinite(performanceScore) || performanceScore <= 0) {
      return 1.0
    }

    return performanceScore
  })

  return {
    tooltip: {
      show: editingAnchor.value === null, // Hide tooltip when edit popup is open
      trigger: 'item',
      confine: true,
      formatter: (params) => {
        // Show organized layout: 0% at top, then downhill/uphill columns
        const values = Array.isArray(params.value) ? params.value : [params.value]

        // Helper to get pace for a grade
        const getPace = (grade) => {
          const index = radarDisplayOrder.indexOf(grade)
          if (index === -1) return null

          const performanceScore = values[index]
          if (!Number.isFinite(performanceScore) || !Number.isFinite(pace)) return null

          const globalRatio = interp1(
            globalCurveSorted.map(p => p.grade),
            globalCurveSorted.map(p => p.median),
            grade
          )
          if (!globalRatio || !Number.isFinite(globalRatio)) return null

          const userRatio = globalRatio / performanceScore
          const paceValue = pace * userRatio
          if (!Number.isFinite(paceValue)) return null

          return formatPace(paceValue)
        }

        // Start with series name and 0% (flat)
        const flatPace = getPace(0)
        let tooltipHtml = `<div style="font-weight: 600; margin-bottom: 4px;">${params.seriesName}</div>`
        tooltipHtml += `<div style="margin-bottom: 8px; padding: 4px 0; border-bottom: 1px solid #e5e7eb;">
          <span style="font-weight: 600;">Flat (0%):</span> ${flatPace}/km
        </div>`

        // Two-column layout for downhill/uphill
        tooltipHtml += `<div style="display: flex; gap: 16px; font-size: 12px;">
          <div style="flex: 1;">
            <div style="font-weight: 600; margin-bottom: 4px; color: #22c55e;">Downhill</div>
            <div style="margin-bottom: 2px;">-10%: ${getPace(-10)}/km</div>
            <div style="margin-bottom: 2px;">-20%: ${getPace(-20)}/km</div>
            <div>-30%: ${getPace(-30)}/km</div>
          </div>
          <div style="flex: 1;">
            <div style="font-weight: 600; margin-bottom: 4px; color: #ef4444;">Uphill</div>
            <div style="margin-bottom: 2px;">+10%: ${getPace(10)}/km</div>
            <div style="margin-bottom: 2px;">+20%: ${getPace(20)}/km</div>
            <div>+30%: ${getPace(30)}/km</div>
          </div>
        </div>`

        return tooltipHtml
      }
    },
    legend: {
      top: 0,
      data: ['Baseline (Global)', 'Your Personalization']
    },
    radar: {
      indicator: indicators,
      radius: '75%',
      center: ['50%', '50%'],
      startAngle: 90, // Start at top
      axisName: {
        color: '#374151',
        fontSize: 14,
        fontWeight: 600
      },
      splitArea: {
        show: true,
        areaStyle: {
          color: ['rgba(59, 130, 246, 0.05)', 'rgba(59, 130, 246, 0.1)']
        }
      },
      splitLine: {
        lineStyle: {
          color: '#d1d5db',
          width: 1
        }
      },
      axisLine: {
        lineStyle: {
          color: '#9ca3af',
          width: 1
        }
      },
      axisLabel: {
        show: false
      },
      scale: true,
      splitNumber: 4
    },
    series: [
      {
        name: 'Baseline (Global)',
        type: 'radar',
        symbolSize: 0,
        silent: true, // Make baseline non-interactive
        data: [
          {
            value: baselineData,
            name: 'Baseline',
            lineStyle: {
              type: 'dashed',
              width: 2,
              color: '#9ca3af'
            },
            areaStyle: {
              color: 'rgba(156, 163, 175, 0.2)'
            }
          }
        ]
      },
      {
        name: 'Your Personalization',
        type: 'radar',
        symbol: 'circle',
        symbolSize: 18, // Even larger dots for clicking
        emphasis: {
          focus: 'self',
          lineStyle: {
            width: 5
          },
          itemStyle: {
            symbolSize: 24, // Much bigger on hover
            shadowBlur: 12,
            shadowColor: 'rgba(37, 99, 235, 0.6)'
          }
        },
        data: [
          {
            value: personalizedData,
            name: 'Personalized',
            lineStyle: {
              width: 4,
              color: '#2563eb'
            },
            // NO areaStyle - removed to prevent area clicks
            itemStyle: {
              color: '#2563eb',
              borderWidth: 3,
              borderColor: '#fff',
              shadowBlur: 5,
              shadowColor: 'rgba(0, 0, 0, 0.4)'
            }
          }
        ],
        // Enable click on data points
        silent: false
      }
    ]
  }
})
</script>
