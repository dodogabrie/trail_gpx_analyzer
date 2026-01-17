<template>
  <div class="w-full h-[500px]">
    <v-chart ref="chartRef" :option="chartOption" autoresize class="w-full h-full" />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart, LinesChart, CustomChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  DataZoomComponent,
  MarkAreaComponent,
  BrushComponent,
  MarkPointComponent,
  MarkLineComponent
} from 'echarts/components'
import VChart from 'vue-echarts'

use([
  CanvasRenderer,
  LineChart,
  BarChart,
  LinesChart,
  CustomChart,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  DataZoomComponent,
  MarkAreaComponent,
  BrushComponent,
  MarkPointComponent,
  MarkLineComponent
])

const props = defineProps({
  points: {
    type: Array,
    required: true
  },
  segments: {
    type: Array,
    required: true
  },
  rawSegments: {
    type: Array,
    default: () => []
  },
  averagePace: {
    type: Number,
    required: true
  },
  annotations: {
    type: Array,
    default: () => []
  },
  selectedRange: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['click-chart', 'range-selected'])

const chartRef = ref(null)
const hoveredSegmentIndex = ref(null)
const elevationBoundsRef = ref({ min: 0, max: 0 })
const zoomRange = ref(null) // [startKm, endKm]
const isZooming = ref(false)
const zoomDebounceTimer = ref(null)

const formatPace = (paceDecimal) => {
  const minutes = Math.floor(paceDecimal)
  const seconds = Math.round((paceDecimal - minutes) * 60)
  return `${minutes}:${seconds.toString().padStart(2, '0')}`
}

const getElevationAtDistance = (distanceKm) => {
  let closest = props.points[0]
  let minDiff = Math.abs(props.points[0].distance / 1000 - distanceKm)

  for (const point of props.points) {
    const diff = Math.abs(point.distance / 1000 - distanceKm)
    if (diff < minDiff) {
      minDiff = diff
      closest = point
    }
  }

  return closest.elevation
}

const setupEventListeners = () => {
  if (!chartRef.value) return

  const vueChartComponent = chartRef.value
  let chart = null

  if (vueChartComponent.chart) {
    chart = vueChartComponent.chart
  } else if (typeof vueChartComponent.getEchartsInstance === 'function') {
    chart = vueChartComponent.getEchartsInstance()
  }

  if (chart) {
    // Listen to axis pointer updates to track mouse position
    chart.on('updateAxisPointer', (event) => {
      const xAxisInfo = event.axesInfo[0]
      if (xAxisInfo && xAxisInfo.value !== undefined) {
        const distanceKm = xAxisInfo.value
        const segmentIndex = segmentCentersRef.value.findIndex(seg =>
          distanceKm >= seg.startKm && distanceKm <= seg.endKm
        )
        hoveredSegmentIndex.value = segmentIndex !== -1 ? segmentIndex : null
      }
    })

    chart.on('globalout', () => {
      hoveredSegmentIndex.value = null
    })

    // Click event for adding annotations (anywhere on chart)
    chart.getZr().on('click', (event) => {
      const pointInGrid = [event.offsetX, event.offsetY]

      const elevationGridModel = chart.getModel().getComponent('grid', 0)
      if (elevationGridModel) {
        const gridRect = elevationGridModel.coordinateSystem.getRect()

        if (pointInGrid[0] >= gridRect.x &&
            pointInGrid[0] <= gridRect.x + gridRect.width &&
            pointInGrid[1] >= gridRect.y &&
            pointInGrid[1] <= gridRect.y + gridRect.height) {

          // Convert pixel to data coordinates
          const distanceKm = chart.convertFromPixel({ gridIndex: 0 }, pointInGrid)[0]

          if (distanceKm >= 0) {
            emit('click-chart', { distanceKm })
          }
        }
      }
    })

    // Brush events for range selection
    chart.on('brushEnd', (params) => {
      if (params.areas && params.areas.length > 0) {
        const range = params.areas[0].coordRange
        emit('range-selected', {
          start_km: range[0],
          end_km: range[1]
        })
      }
    })

    chart.on('brush', (params) => {
      if (!params.areas || params.areas.length === 0) {
        emit('range-selected', null)
      }
    })

    // Listen to dataZoom events to update visible range
    chart.on('dataZoom', (params) => {
      isZooming.value = true

      const xAxis = chart.getModel().getComponent('xAxis', 0)
      if (xAxis) {
        const axis = xAxis.axis
        const extent = axis.scale.getExtent()
        zoomRange.value = [extent[0], extent[1]]
      }

      // Debounce: mark as not zooming after 300ms of no zoom events
      if (zoomDebounceTimer.value) {
        clearTimeout(zoomDebounceTimer.value)
      }
      zoomDebounceTimer.value = setTimeout(() => {
        isZooming.value = false
      }, 300)
    })
  }
}

onMounted(() => {
  nextTick(() => {
    setupEventListeners()
  })
})

onUnmounted(() => {
  if (zoomDebounceTimer.value) {
    clearTimeout(zoomDebounceTimer.value)
  }
})

// Store segment centers outside computed for use in tooltip
const segmentCentersRef = ref([])

watch(hoveredSegmentIndex, () => {
  nextTick(() => {
    if (!chartRef.value) return

    const vueChartComponent = chartRef.value
    const chart = vueChartComponent.chart ||
      (typeof vueChartComponent.getEchartsInstance === 'function'
        ? vueChartComponent.getEchartsInstance()
        : null)

    if (!chart) return

    const bounds = elevationBoundsRef.value
    const hoveredSegment = hoveredSegmentIndex.value !== null
      ? segmentCentersRef.value[hoveredSegmentIndex.value]
      : null

    const elevationMarkArea = hoveredSegment ? {
      silent: true,
      itemStyle: {
        color: 'rgba(251, 191, 36, 0.4)',
        borderColor: 'rgba(251, 191, 36, 1)',
        borderWidth: 2
      },
      data: [[
        { xAxis: hoveredSegment.startKm, yAxis: bounds.min },
        { xAxis: hoveredSegment.endKm, yAxis: bounds.max }
      ]]
    } : undefined

    chart.setOption({
      series: [{ id: 'elevation', markArea: elevationMarkArea }]
    }, { notMerge: false, lazyUpdate: true })
  })
})

const chartOption = computed(() => {
  // Skip expensive computations during zoom
  const skipColors = isZooming.value

  const paceSegmentRanges = props.segments.map(segment => {
    const startKm = segment.start_km ?? 0
    const endKm = segment.end_km ?? segment.segment_km ?? 0
    const pace = segment.avg_pace_min_per_km
    return { startKm, endKm, pace }
  }).filter(seg => Number.isFinite(seg.startKm) && Number.isFinite(seg.endKm) && Number.isFinite(seg.pace))

  let segmentIndex = 0
  const elevationData = props.points.map((p, idx) => {
    const distanceKm = p.distance / 1000
    while (segmentIndex < paceSegmentRanges.length - 1 &&
      distanceKm > paceSegmentRanges[segmentIndex].endKm) {
      segmentIndex += 1
    }
    const pace = paceSegmentRanges[segmentIndex]?.pace ?? props.averagePace
    return [
      distanceKm,
      p.elevation,
      pace,
      idx
    ]
  })

  const paceValues = elevationData.map(d => d[2]).filter(v => Number.isFinite(v))

  // Use percentiles to avoid outliers dominating the color scale
  const sortedPaces = [...paceValues].sort((a, b) => a - b)
  const p10 = sortedPaces[Math.floor(sortedPaces.length * 0.1)]
  const p90 = sortedPaces[Math.floor(sortedPaces.length * 0.9)]
  const minPace = p10
  const maxPace = p90
  const paceRange = Math.max(maxPace - minPace, 0.01)

  const segmentCenters = props.segments.map(segment => {
    const startKm = segment.start_km || 0
    const endKm = segment.end_km || segment.segment_km || 0
    const centerKm = (startKm + endKm) / 2
    const pace = segment.avg_pace_min_per_km
    const grade = segment.avg_grade_percent

    // Get elevation profile for this segment
    const segmentPoints = props.points.filter(p => {
      const km = p.distance / 1000
      return km >= startKm && km <= endKm
    })
    const segmentElevations = segmentPoints.map(p => p.elevation)
    const minElev = segmentElevations.length > 0 ? Math.min(...segmentElevations) : 0
    const maxElev = segmentElevations.length > 0 ? Math.max(...segmentElevations) : 0

    return {
      distance: centerKm,
      pace,
      grade,
      startKm,
      endKm,
      elevationRange: `${minElev.toFixed(0)}m - ${maxElev.toFixed(0)}m`,
      segmentLength: endKm - startKm
    }
  })

  // Store for use in watcher
  segmentCentersRef.value = segmentCenters

  // Skip expensive boundary computation during zoom
  let segmentBoundaries = []

  if (!skipColors) {
    // Filter segment boundaries by significant pace changes (> 0.5 min/km difference)
    const segmentBoundariesWithPace = []
    for (let i = 0; i < props.segments.length - 1; i++) {
      const curr = props.segments[i]
      const next = props.segments[i + 1]
      const paceChange = Math.abs(curr.avg_pace_min_per_km - next.avg_pace_min_per_km)

      if (paceChange > 0.5) {
        const boundaryKm = curr.end_km || curr.segment_km || 0
        if (Number.isFinite(boundaryKm)) {
          // Find elevation at this distance
          const closestPoint = props.points.reduce((closest, p) => {
            const distKm = p.distance / 1000
            const diff = Math.abs(distKm - boundaryKm)
            const closestDiff = Math.abs(closest.distance / 1000 - boundaryKm)
            return diff < closestDiff ? p : closest
          }, props.points[0])

          segmentBoundariesWithPace.push({
            km: boundaryKm,
            elevation: closestPoint.elevation,
            paceChange: paceChange
          })
        }
      }
    }

    // Filter boundaries based on zoom level
    // Calculate visible range
    const totalDistance = props.points[props.points.length - 1].distance / 1000
    const visibleStart = zoomRange.value ? zoomRange.value[0] : 0
    const visibleEnd = zoomRange.value ? zoomRange.value[1] : totalDistance
    const visibleDistance = visibleEnd - visibleStart

    // Target: min 30px between lines on a ~900px wide chart
    const chartWidth = 900
    const minPixelDistance = 30
    const minKmDistance = (visibleDistance / chartWidth) * minPixelDistance

    // Filter visible boundaries with sufficient spacing
    const visibleBoundaries = segmentBoundariesWithPace
      .filter(b => b.km >= visibleStart && b.km <= visibleEnd)
      .sort((a, b) => a.km - b.km)

    const filteredBoundaries = []
    let lastKm = -Infinity

    for (const boundary of visibleBoundaries) {
      if (boundary.km - lastKm >= minKmDistance) {
        filteredBoundaries.push(boundary)
        lastKm = boundary.km
      }
    }

    segmentBoundaries = filteredBoundaries
  }

  // Calculate min/max for elevation
  const elevations = elevationData.map(d => d[1])
  const minElev = Math.min(...elevations)
  const maxElev = Math.max(...elevations)
  const elevRange = maxElev - minElev
  const elevationMin = minElev - elevRange * 0.1
  const elevationMax = maxElev + elevRange * 0.1
  elevationBoundsRef.value = { min: elevationMin, max: elevationMax }

  const clamp01 = (value) => Math.max(0, Math.min(1, value))

  const getPaceColor = (pace) => {
    // Apply non-linear transformation for better color distribution
    let t = clamp01((pace - minPace) / paceRange)
    t = Math.pow(t, 0.7) // Emphasize mid-range colors

    const start = [16, 185, 129] // emerald (fast)
    const mid = [251, 191, 36] // amber
    const end = [220, 38, 38] // red (slow)

    const mix = (a, b, amount) => Math.round(a + (b - a) * amount)
    const from = t < 0.5 ? start : mid
    const to = t < 0.5 ? mid : end
    const localT = t < 0.5 ? t / 0.5 : (t - 0.5) / 0.5

    const r = mix(from[0], to[0], localT)
    const g = mix(from[1], to[1], localT)
    const b = mix(from[2], to[2], localT)
    return `rgb(${r}, ${g}, ${b})`
  }

  const paceSegments = []
  const paceAreaData = []

  if (!skipColors) {
    paceSegmentRanges.forEach(seg => {
      const pace = seg.pace
      if (!Number.isFinite(pace)) return
      const color = getPaceColor(pace)

      for (let i = 0; i < elevationData.length - 1; i++) {
        const start = elevationData[i]
        const end = elevationData[i + 1]
        if (start[0] < seg.startKm || end[0] > seg.endKm) continue

        paceSegments.push({
          coords: [
            [start[0], start[1]],
            [end[0], end[1]]
          ],
          lineStyle: {
            color
          }
        })

        paceAreaData.push([
          start[0],
          start[1],
          end[0],
          end[1],
          pace
        ])
      }
    })
  }

  return {
    tooltip: {
      trigger: 'axis',
      position: function (point, params, dom, rect, size) {
        // point: [x, y] mouse position
        // size: {contentSize: [width, height], viewSize: [width, height]}
        const [mouseX, mouseY] = point
        const tooltipWidth = size.contentSize[0]
        const tooltipHeight = size.contentSize[1]
        const viewWidth = size.viewSize[0]

        // Position tooltip to the right of cursor by default
        let x = mouseX + 20
        let y = mouseY - tooltipHeight / 2

        // If tooltip would go off right edge, position to the left
        if (x + tooltipWidth > viewWidth) {
          x = mouseX - tooltipWidth - 20
        }

        // Keep y within bounds
        if (y < 0) y = 10
        if (y + tooltipHeight > size.viewSize[1]) {
          y = size.viewSize[1] - tooltipHeight - 10
        }

        return [x, y]
      },
      axisPointer: {
        type: 'line',
        animation: false,
        lineStyle: {
          color: '#fbbf24',
          width: 2,
          type: 'solid'
        },
        label: {
          backgroundColor: '#505765',
          formatter: (params) => {
            if (params.axisDimension === 'x') {
              return params.value.toFixed(2) + ' km'
            }
            return params.value.toFixed(0) + ' m'
          }
        }
      },
      formatter: (params) => {
        if (!Array.isArray(params)) params = [params]
        const elevationParam = params.find(param => param.seriesName === 'Elevation')
        let result = ''

        if (elevationParam) {
          const dataIndex = elevationParam.dataIndex
          const paceValue = elevationData[dataIndex]?.[2]
          result += `<b>Distance:</b> ${elevationParam.value[0].toFixed(2)} km<br/>`
          result += `<b>Elevation:</b> ${elevationParam.value[1].toFixed(0)} m<br/>`
          if (Number.isFinite(paceValue)) {
            result += `<b>Pace:</b> ${formatPace(paceValue)}/km<br/>`
          }
        }

        // Add segment info if available
        if (hoveredSegmentIndex.value !== null && segmentCentersRef.value[hoveredSegmentIndex.value]) {
          const seg = segmentCentersRef.value[hoveredSegmentIndex.value]
          result += `<br/><b>Segment:</b> ${seg.startKm.toFixed(2)} - ${seg.endKm.toFixed(2)} km<br/>`
          result += `<b>Pace:</b> ${formatPace(seg.pace)}/km<br/>`
          result += `<b>Mean Slope:</b> ${seg.grade.toFixed(1)}%<br/>`
          result += `<b>Elevation Range:</b> ${seg.elevationRange}`
        }

        return result
      }
    },
    grid: [
      {
        left: 100,
        right: 50,
        top: 60,
        height: '70%'
      }
    ],
    xAxis: [
      {
        type: 'value',
        gridIndex: 0,
        name: 'Distance (km)',
        nameLocation: 'middle',
        nameGap: 30,
        splitLine: {
          show: false
        }
      }
    ],
    yAxis: [
      {
        type: 'value',
        gridIndex: 0,
        name: 'Elevation (m)',
        nameLocation: 'middle',
        nameGap: 45,
        min: elevationMin,
        max: elevationMax
      }
    ],
    series: [
      // Segment boundary grid lines (stop at elevation profile)
      {
        name: 'Grid',
        type: 'lines',
        coordinateSystem: 'cartesian2d',
        xAxisIndex: 0,
        yAxisIndex: 0,
        silent: true,
        animation: false,
        data: segmentBoundaries.map(boundary => ({
          coords: [
            [boundary.km, elevationMin],
            [boundary.km, boundary.elevation]
          ],
          lineStyle: {
            color: 'rgba(148, 163, 184, 0.3)',
            width: 1,
            type: 'solid'
          }
        })),
        z: 0
      },
      // Elevation profile
      {
        name: 'Elevation',
        id: 'elevation',
        type: 'line',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: elevationData.map(point => [point[0], point[1]]),
        smooth: false,
        symbol: 'none',
        lineStyle: {
          width: skipColors ? 2 : 1.5,
          color: skipColors ? '#0f172a' : '#334155'
        },
        z: 10,
        markPoint: {
          symbol: 'pin',
          symbolSize: 50,
          data: props.annotations
            .filter(a => a.type === 'aid_station')
            .map(a => ({
              name: a.label,
              coord: [a.distance_km, getElevationAtDistance(a.distance_km)],
              itemStyle: { color: '#10b981' },
              label: {
                formatter: '{b}',
                position: 'top',
                fontSize: 11,
                color: '#000',
                backgroundColor: 'rgba(255,255,255,0.9)',
                padding: [3, 6],
                borderRadius: 3,
                borderColor: '#10b981',
                borderWidth: 1
              }
            }))
        },
        markLine: {
          symbol: 'none',
          data: [
            ...props.annotations
              .filter(a => a.type === 'generic')
              .map(a => ({
                name: a.label,
                xAxis: a.distance_km,
                lineStyle: { color: '#9333ea', type: 'dashed', width: 2 },
                label: {
                  formatter: '{b}',
                  position: 'end',
                  fontSize: 11,
                  color: '#fff',
                  backgroundColor: '#9333ea',
                  padding: [3, 6],
                  borderRadius: 3
                }
              }))
          ]
        }
      },
      {
        name: 'Pace Area',
        type: 'custom',
        coordinateSystem: 'cartesian2d',
        xAxisIndex: 0,
        yAxisIndex: 0,
        silent: true,
        data: paceAreaData,
        renderItem: (params, api) => {
          const x0 = api.value(0)
          const y0 = api.value(1)
          const x1 = api.value(2)
          const y1 = api.value(3)
          const pace = api.value(4)

          const p0 = api.coord([x0, y0])
          const p1 = api.coord([x1, y1])
          const p2 = api.coord([x1, elevationMin])
          const p3 = api.coord([x0, elevationMin])

          return {
            type: 'polygon',
            shape: {
              points: [p0, p1, p2, p3]
            },
            style: api.style({
              fill: getPaceColor(pace),
              opacity: 0.35
            })
          }
        },
        z: 2
      },
      {
        name: 'Pace Coloring',
        type: 'lines',
        coordinateSystem: 'cartesian2d',
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: paceSegments,
        silent: true,
        lineStyle: {
          width: 4,
          opacity: 1
        },
        z: 15
      }
    ],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0],
        throttle: 50
      },
      {
        type: 'slider',
        xAxisIndex: [0],
        bottom: 10,
        throttle: 50
      }
    ],
    brush: {
      xAxisIndex: [0],
      brushType: 'lineX',
      brushMode: 'single',
      outOfBrush: {
        colorAlpha: 0.3
      },
      brushStyle: {
        borderWidth: 2,
        color: 'rgba(59, 130, 246, 0.2)',
        borderColor: 'rgba(59, 130, 246, 0.8)'
      },
      throttleType: 'debounce',
      throttleDelay: 300
    }
  }
})

</script>

<style scoped>
/* Ensure proper rendering */
.echarts {
  width: 100%;
  height: 100%;
}
</style>
