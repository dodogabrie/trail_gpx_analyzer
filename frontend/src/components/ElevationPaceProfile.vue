<template>
    <div class="w-full h-[360px] sm:h-[420px] md:h-[500px] overflow-x-auto overflow-y-hidden touch-pan-x">
        <div :class="props.tapToReveal ? 'min-w-[900px] h-full' : 'h-full'" class="relative">
            <v-chart
                ref="chartRef"
                :option="chartOption"
                autoresize
                class="w-full h-full"
            />
            <div
                v-if="hoverEditHint"
                class="absolute z-50 -translate-x-1/2 rounded-full bg-slate-900 text-white text-[10px] font-semibold uppercase tracking-wide px-2 py-1 shadow-md"
                :style="{ left: `${hoverEditHint.x}px`, top: `${hoverEditHint.y}px` }"
            >
                {{ hoverEditHint.label }}
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from "vue";
import { use } from "echarts/core";
import * as zrender from "zrender";
import { CanvasRenderer } from "echarts/renderers";
import { LineChart, BarChart, LinesChart, CustomChart } from "echarts/charts";
import {
    TitleComponent,
    TooltipComponent,
    GridComponent,
    LegendComponent,
    DataZoomComponent,
    MarkAreaComponent,
    BrushComponent,
    MarkPointComponent,
    MarkLineComponent,
} from "echarts/components";
import VChart from "vue-echarts";

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
    MarkLineComponent,
]);

const props = defineProps({
    points: {
        type: Array,
        required: true,
    },
    segments: {
        type: Array,
        required: true,
    },
    rawSegments: {
        type: Array,
        default: () => [],
    },
    averagePace: {
        type: Number,
        required: true,
    },
    annotations: {
        type: Array,
        default: () => [],
    },
    selectedRange: {
        type: Object,
        default: null,
    },
    tapToReveal: {
        type: Boolean,
        default: false,
    },
    editLabel: {
        type: String,
        default: "Edit",
    },
});

const emit = defineEmits([
    "click-chart",
    "range-selected",
    "zoom-changed",
    "annotation-click",
]);

const chartRef = ref(null);
const hoveredSegmentIndex = ref(null);
const elevationBoundsRef = ref({ min: 0, max: 0 });
const zoomRange = ref(null); // [startKm, endKm]
const isZooming = ref(false);
const zoomDebounceTimer = ref(null);
const hoverBandZrRef = ref(null);
const clickMarkerZrRef = ref(null);
let tooltipHideTimer = null;
let hoverRafId = null;
let pendingHoverDistance = null;
const hoverEditHint = ref(null);
const hoverAnnotationZrRef = ref(null);
let hoverAnnotationId = null;
const annotationStackRef = ref(new Map());

const formatPace = (paceDecimal) => {
    const baseMinutes = Math.floor(paceDecimal);
    const rawSeconds = Math.round((paceDecimal - baseMinutes) * 60);
    const carry = rawSeconds === 60 ? 1 : 0;
    const minutes = baseMinutes + carry;
    const seconds = rawSeconds === 60 ? 0 : rawSeconds;
    return `${minutes}:${seconds.toString().padStart(2, "0")}`;
};

const getPunctualMetrics = (index) => {
    if (!Number.isFinite(index) || index < 0 || index >= props.points.length) {
        return { slope: null };
    }

    const windowDistance = 50;
    const halfWindow = windowDistance / 2;
    const minDistance = 15;

    let startIndex = index;
    let endIndex = index;

    while (
        startIndex > 0 &&
        props.points[index].distance - props.points[startIndex].distance <
            halfWindow
    ) {
        startIndex -= 1;
    }

    while (
        endIndex < props.points.length - 1 &&
        props.points[endIndex].distance - props.points[index].distance <
            halfWindow
    ) {
        endIndex += 1;
    }

    if (startIndex === endIndex) {
        return { slope: null };
    }

    const start = props.points[startIndex];
    const end = props.points[endIndex];
    const distanceDelta = end.distance - start.distance;
    const elevationDelta = end.elevation - start.elevation;

    if (!Number.isFinite(distanceDelta) || distanceDelta <= minDistance) {
        return { slope: null };
    }

    const slope = (elevationDelta / distanceDelta) * 100;

    return {
        slope: Number.isFinite(slope) ? slope : null,
    };
};

const getPaceAtDistance = (distanceKm) => {
    if (!Number.isFinite(distanceKm)) return null;

    const rawSegments = props.rawSegments || [];
    if (rawSegments.length > 0) {
        const first = rawSegments[0];
        if (Number.isFinite(first.distance_m)) {
            const targetM = distanceKm * 1000;
            const seg = rawSegments.find((segment) => {
                const length = segment.length_m || 0;
                return (
                    targetM >= segment.distance_m &&
                    targetM <= segment.distance_m + length
                );
            });
            const pace = seg?.pace_min_km ?? seg?.avg_pace_min_per_km;
            if (Number.isFinite(pace)) return pace;
        } else {
            const seg = rawSegments.find((segment) => {
                const startKm = segment.start_km || 0;
                const endKm = segment.end_km || segment.segment_km || 0;
                return distanceKm >= startKm && distanceKm <= endKm;
            });
            const pace = seg?.avg_pace_min_per_km ?? seg?.pace_min_km;
            if (Number.isFinite(pace)) return pace;
        }
    }

    const fallback = props.segments.find((segment) => {
        const startKm = segment.start_km || 0;
        const endKm = segment.end_km || segment.segment_km || 0;
        return distanceKm >= startKm && distanceKm <= endKm;
    });

    return Number.isFinite(fallback?.avg_pace_min_per_km)
        ? fallback.avg_pace_min_per_km
        : null;
};

const findClosestPointIndex = (distanceKm) => {
    if (!props.points.length || !Number.isFinite(distanceKm)) return -1;
    const target = distanceKm * 1000;
    let low = 0;
    let high = props.points.length - 1;

    while (low <= high) {
        const mid = Math.floor((low + high) / 2);
        const dist = props.points[mid].distance;
        if (dist === target) return mid;
        if (dist < target) {
            low = mid + 1;
        } else {
            high = mid - 1;
        }
    }

    if (low >= props.points.length) return props.points.length - 1;
    if (high < 0) return 0;

    const lowDiff = Math.abs(props.points[low].distance - target);
    const highDiff = Math.abs(props.points[high].distance - target);
    return lowDiff < highDiff ? low : high;
};

const getElevationAtDistance = (distanceKm) => {
    let closest = props.points[0];
    let minDiff = Math.abs(props.points[0].distance / 1000 - distanceKm);

    for (const point of props.points) {
        const diff = Math.abs(point.distance / 1000 - distanceKm);
        if (diff < minDiff) {
            minDiff = diff;
            closest = point;
        }
    }

    return closest.elevation;
};

const getChartInstance = () => {
    const vueChartComponent = chartRef.value;
    if (!vueChartComponent) return null;
    if (vueChartComponent.chart) return vueChartComponent.chart;
    if (typeof vueChartComponent.getEchartsInstance === "function") {
        return vueChartComponent.getEchartsInstance();
    }
    return null;
};

const getTotalDistanceKm = () => {
    if (!props.points.length) return 0;
    return props.points[props.points.length - 1].distance / 1000;
};

const emitZoomState = (range) => {
    const totalDistance = getTotalDistanceKm();
    if (!range || !Number.isFinite(totalDistance) || totalDistance <= 0) {
        emit("zoom-changed", false);
        return;
    }

    const start = range[0];
    const end = range[1];
    const isZoomed = start > 0.01 || end < totalDistance - 0.01;
    emit("zoom-changed", isZoomed);
};

const setupEventListeners = () => {
    if (!chartRef.value) return;

    const chart = getChartInstance();
    let pointerInGrid = false;

    if (chart) {
        const getAnnotationHit = (event) => {
            const coordSys = chart
                .getModel()
                .getComponent("grid", 0)
                ?.coordinateSystem;
            if (!coordSys || props.annotations.length === 0) return null;

            if (typeof coordSys.getRect !== "function") return null;
            const topY = coordSys.getRect().y;
            const hitRadius = 10;
            const hitRadiusSq = hitRadius * hitRadius;

            let closest = null;
            let closestDistSq = Infinity;
            for (const annotation of props.annotations) {
                const distanceKm = Number(annotation.distance_km);
                if (!Number.isFinite(distanceKm)) continue;
                const level = annotationStackRef.value.get(
                    annotation.id || distanceKm,
                );
                const dropletY = Math.max(
                    topY - 12 - (Number.isFinite(level) ? level * 12 : 0),
                    6,
                );
                const xPixel = chart.convertToPixel({ gridIndex: 0 }, [
                    distanceKm,
                    elevationBoundsRef.value.max,
                ])[0];
                const dx = event.offsetX - xPixel;
                const dy = event.offsetY - dropletY;
                const distSq = dx * dx + dy * dy;
                if (distSq < closestDistSq) {
                    closestDistSq = distSq;
                    closest = annotation;
                }
            }

            if (!closest || closestDistSq > hitRadiusSq) return null;
            return closest;
        };

        const removeHoverAnnotation = () => {
            if (!hoverAnnotationZrRef.value) {
                hoverAnnotationId = null;
                return;
            }
            hoverAnnotationZrRef.value.ignore = true;
            hoverAnnotationZrRef.value.dirty();
            hoverAnnotationId = null;
            chart.getZr().refresh();
        };

        const drawHoverAnnotation = (annotation) => {
            const coordSys = chart
                .getModel()
                .getComponent("grid", 0)
                ?.coordinateSystem;
            if (!coordSys || typeof coordSys.getRect !== "function") return;

            const distanceKm = Number(annotation?.distance_km);
            if (!Number.isFinite(distanceKm)) return;

            const elevation = getElevationAtDistance(distanceKm);
            const point = chart.convertToPixel({ gridIndex: 0 }, [
                distanceKm,
                elevation,
            ]);
            const topPoint = chart.convertToPixel({ gridIndex: 0 }, [
                distanceKm,
                elevationBoundsRef.value.max,
            ]);
            const bottomPoint = chart.convertToPixel({ gridIndex: 0 }, [
                distanceKm,
                elevationBoundsRef.value.min,
            ]);

            const accent =
                annotation?.type === "generic" ? "#9333ea" : "#10b981";
            const labelText = String(annotation?.label || "");
            const topY = coordSys.getRect().y;
            const level = annotationStackRef.value.get(
                annotation?.id || distanceKm,
            );
            const dropletRadius = 10;
            const dropletY = Math.max(
                topY - 16 - (Number.isFinite(level) ? level * 16 : 0),
                8,
            );
            const tipY = topY - 4;
            const badgeWidth = Math.max(56, labelText.length * 6.2 + 18);
            const badgeHeight = 22;
            const badgeX = point[0] - badgeWidth / 2;
            const badgeY = Math.max(dropletY - 22, 8);

            let group = hoverAnnotationZrRef.value;
            if (!group) {
                group = new zrender.Group({
                    zlevel: 40,
                    z: 40,
                    silent: true,
                });
                hoverAnnotationZrRef.value = group;
            }
            group.ignore = false;
            group.removeAll();

            group.add(
                new zrender.Line({
                    shape: {
                        x1: point[0],
                        y1: bottomPoint[1],
                        x2: point[0],
                        y2: topPoint[1],
                    },
                    style: {
                        stroke: accent,
                        lineWidth: 2,
                        lineDash: [6, 6],
                    },
                }),
            );
            if (labelText) {
                group.add(
                    new zrender.Rect({
                        shape: {
                            x: badgeX,
                            y: badgeY - badgeHeight / 2,
                            width: badgeWidth,
                            height: badgeHeight,
                            r: 10,
                        },
                        style: {
                            fill: "#ffffff",
                            stroke: accent,
                            lineWidth: 2,
                            shadowBlur: 10,
                            shadowColor: "rgba(15, 23, 42, 0.18)",
                        },
                    }),
                );
                group.add(
                    new zrender.Polygon({
                        shape: {
                            points: [
                                [point[0] - 6, badgeY + badgeHeight / 2 - 2],
                                [point[0] + 6, badgeY + badgeHeight / 2 - 2],
                                [point[0], tipY],
                            ],
                        },
                        style: {
                            fill: "#ffffff",
                            stroke: accent,
                            lineWidth: 2,
                        },
                    }),
                );
                group.add(
                    new zrender.Text({
                        style: {
                            text: labelText,
                            x: point[0],
                            y: badgeY,
                            fill: "#0f172a",
                            font: '600 10px "Space Grotesk", "Trebuchet MS", sans-serif',
                            align: "center",
                            verticalAlign: "middle",
                        },
                    }),
                );
            }
            group.add(
                new zrender.Circle({
                    shape: {
                        cx: point[0],
                        cy: dropletY,
                        r: dropletRadius,
                    },
                    style: {
                        fill: accent,
                        shadowBlur: 12,
                        shadowColor: "rgba(15, 23, 42, 0.25)",
                    },
                }),
            );
            group.add(
                new zrender.Polygon({
                    shape: {
                        points: [
                            [point[0] - dropletRadius, dropletY + dropletRadius],
                            [point[0] + dropletRadius, dropletY + dropletRadius],
                            [point[0], tipY],
                        ],
                    },
                    style: {
                        fill: accent,
                    },
                }),
            );

            if (!group.__zr) {
                chart.getZr().add(group);
            }
            hoverAnnotationId = annotation?.id || annotation?.distance_km;
        };
        // Listen to axis pointer updates to track mouse position
        chart.on("updateAxisPointer", (event) => {
            if (!pointerInGrid) {
                hoveredSegmentIndex.value = null;
                return;
            }
            const xAxisInfo = event.axesInfo[0];
            if (xAxisInfo && xAxisInfo.value !== undefined) {
                pendingHoverDistance = xAxisInfo.value;
                if (hoverRafId) return;
                hoverRafId = requestAnimationFrame(() => {
                    const distanceKm = pendingHoverDistance;
                    pendingHoverDistance = null;
                    const segmentIndex = segmentCentersRef.value.findIndex(
                        (seg) =>
                            distanceKm >= seg.startKm &&
                            distanceKm <= seg.endKm,
                    );
                    const nextIndex = segmentIndex !== -1 ? segmentIndex : null;
                    if (hoveredSegmentIndex.value !== nextIndex) {
                        hoveredSegmentIndex.value = nextIndex;
                    }
                    hoverRafId = null;
                });
            }
        });

        chart.on("globalout", () => {
            hoveredSegmentIndex.value = null;
            hoverEditHint.value = null;
            removeHoverAnnotation();
        });

        // Click event for adding annotations (anywhere on chart)
        chart.getZr().on("click", (event) => {
            const hit = getAnnotationHit(event);
            if (hit) {
                const rect = chartRef.value?.$el?.getBoundingClientRect();
                const screenX = rect ? rect.left + event.offsetX : null;
                const screenY = rect ? rect.top + event.offsetY : null;
                emit("annotation-click", {
                    annotation: hit,
                    screenX,
                    screenY,
                });
                removeHoverAnnotation();
                return;
            }
            const ecInfo = event?.target?.__ecComponentInfo;
            if (ecInfo?.seriesName === "Annotations") {
                return;
            }
            const pointInGrid = [event.offsetX, event.offsetY];

            const elevationGridModel = chart.getModel().getComponent("grid", 0);
            if (elevationGridModel) {
                const gridRect = elevationGridModel.coordinateSystem.getRect();

                if (
                    pointInGrid[0] >= gridRect.x &&
                    pointInGrid[0] <= gridRect.x + gridRect.width &&
                    pointInGrid[1] >= gridRect.y &&
                    pointInGrid[1] <= gridRect.y + gridRect.height
                ) {
                    // Convert pixel to data coordinates
                    const distanceKm = chart.convertFromPixel(
                        { gridIndex: 0 },
                        pointInGrid,
                    )[0];

                    if (distanceKm >= 0) {
                        const pointIndex = findClosestPointIndex(distanceKm);
                        const elevation =
                            pointIndex !== -1
                                ? props.points[pointIndex].elevation
                                : getElevationAtDistance(distanceKm);
                        const segmentIndex = segmentCentersRef.value.findIndex(
                            (seg) =>
                                distanceKm >= seg.startKm &&
                                distanceKm <= seg.endKm,
                        );
                        hoveredSegmentIndex.value =
                            segmentIndex !== -1 ? segmentIndex : null;

                        const [cx, cy] = chart.convertToPixel(
                            { gridIndex: 0 },
                            [distanceKm, elevation],
                        );
                        const rect =
                            chartRef.value?.$el?.getBoundingClientRect();
                        const clickX = rect ? rect.left + cx : cx;
                        const clickY = rect ? rect.top + cy : cy;

                        if (!clickMarkerZrRef.value) {
                            clickMarkerZrRef.value = new zrender.Circle({
                                shape: {
                                    cx,
                                    cy,
                                    r: 6,
                                },
                                style: {
                                    fill: "rgba(0, 0, 0, 0)",
                                    stroke: "#0f172a",
                                    lineWidth: 2,
                                },
                                silent: true,
                            });
                            clickMarkerZrRef.value.z = 20;
                            clickMarkerZrRef.value.zlevel = 20;
                            chart.getZr().add(clickMarkerZrRef.value);
                        } else {
                            clickMarkerZrRef.value.attr({
                                shape: {
                                    cx,
                                    cy,
                                    r: 6,
                                },
                            });
                        }

                        clickMarkerZrRef.value.dirty();
                        chart.getZr().refresh();

                        if (props.tapToReveal) {
                            chart.dispatchAction({
                                type: "updateAxisPointer",
                                xAxisIndex: 0,
                                value: distanceKm,
                            });
                            chart.dispatchAction({
                                type: "showTip",
                                seriesId: "elevation",
                                dataIndex: pointIndex,
                            });
                            if (tooltipHideTimer) {
                                clearTimeout(tooltipHideTimer);
                            }
                            tooltipHideTimer = setTimeout(() => {
                                chart.dispatchAction({ type: "hideTip" });
                            }, 3000);
                        }

                        emit("click-chart", {
                            distanceKm,
                            screenX: clickX,
                            screenY: clickY,
                        });
                    }
                }
            }
        });

        chart.getZr().on("mousemove", (event) => {
            const elevationGridModel = chart
                .getModel()
                .getComponent("grid", 0);
            if (elevationGridModel) {
                const rect = elevationGridModel.coordinateSystem.getRect();
                pointerInGrid =
                    event.offsetX >= rect.x &&
                    event.offsetX <= rect.x + rect.width &&
                    event.offsetY >= rect.y &&
                    event.offsetY <= rect.y + rect.height;
            } else {
                pointerInGrid = false;
            }
            const hit = getAnnotationHit(event);
            if (hit) {
                chart.getZr().setCursorStyle("pointer");
                hoverEditHint.value = null;
                const hitId = hit.id || hit.distance_km;
                if (hoverAnnotationId !== hitId) {
                    removeHoverAnnotation();
                    drawHoverAnnotation(hit);
                }
            } else {
                chart.getZr().setCursorStyle("default");
                hoverEditHint.value = null;
                if (!pointerInGrid) {
                    hoveredSegmentIndex.value = null;
                }
                removeHoverAnnotation();
            }
        });

        chart.getZr().on("mouseout", () => {
            chart.getZr().setCursorStyle("default");
            hoverEditHint.value = null;
            removeHoverAnnotation();
        });

        // Brush events for range selection
        chart.on("brushEnd", (params) => {
            if (params.areas && params.areas.length > 0) {
                const range = params.areas[0].coordRange;
                emit("range-selected", {
                    start_km: range[0],
                    end_km: range[1],
                });
            }
        });

        chart.on("brush", (params) => {
            if (!params.areas || params.areas.length === 0) {
                emit("range-selected", null);
            }
        });

        // Listen to dataZoom events to update visible range
        chart.on("dataZoom", (params) => {
            isZooming.value = true;
            clearClickMarker();

            const xAxis = chart.getModel().getComponent("xAxis", 0);
            if (xAxis) {
                const axis = xAxis.axis;
                const extent = axis.scale.getExtent();
                zoomRange.value = [extent[0], extent[1]];
                emitZoomState(zoomRange.value);
            }

            // Debounce: mark as not zooming after 300ms of no zoom events
            if (zoomDebounceTimer.value) {
                clearTimeout(zoomDebounceTimer.value);
            }
            zoomDebounceTimer.value = setTimeout(() => {
                isZooming.value = false;
            }, 300);
        });
    }
};

const resetZoom = () => {
    const chart = getChartInstance();
    if (!chart) return;

    chart.dispatchAction({ type: "dataZoom", start: 0, end: 100 });
    chart.dispatchAction({ type: "brush", areas: [] });
    zoomRange.value = null;
    emitZoomState(null);
};

const clearClickMarker = () => {
    const chart = getChartInstance();
    if (chart && clickMarkerZrRef.value) {
        chart.getZr().remove(clickMarkerZrRef.value);
        clickMarkerZrRef.value = null;
    }
};

const hideTooltip = () => {
    const chart = getChartInstance();
    if (!chart) return;
    chart.dispatchAction({ type: "hideTip" });
};

defineExpose({ resetZoom, clearClickMarker, hideTooltip });

onMounted(() => {
    nextTick(() => {
        setupEventListeners();
    });
});

onUnmounted(() => {
    if (zoomDebounceTimer.value) {
        clearTimeout(zoomDebounceTimer.value);
    }
    if (tooltipHideTimer) {
        clearTimeout(tooltipHideTimer);
        tooltipHideTimer = null;
    }
    if (hoverRafId) {
        cancelAnimationFrame(hoverRafId);
        hoverRafId = null;
    }

    const chart = getChartInstance();
    if (chart) {
        if (hoverBandZrRef.value) {
            chart.getZr().remove(hoverBandZrRef.value);
            hoverBandZrRef.value = null;
        }
        if (clickMarkerZrRef.value) {
            chart.getZr().remove(clickMarkerZrRef.value);
            clickMarkerZrRef.value = null;
        }
        if (hoverAnnotationZrRef.value) {
            chart.getZr().remove(hoverAnnotationZrRef.value);
            hoverAnnotationZrRef.value = null;
        }
    }
});

watch(
    () => [
        props.annotations,
        props.points.length,
        zoomRange.value?.[0],
        zoomRange.value?.[1],
    ],
    () => {
        const chart = getChartInstance();
        if (!chart || typeof chart.isDisposed === "function" && chart.isDisposed()) {
            hoverAnnotationZrRef.value = null;
            hoverAnnotationId = null;
            hoverEditHint.value = null;
            return;
        }
        const zr = typeof chart.getZr === "function" ? chart.getZr() : null;
        if (hoverAnnotationZrRef.value && zr) {
            try {
                zr.remove(hoverAnnotationZrRef.value);
            } catch (error) {
                // Ignore stale zrender refs during hot reloads.
            }
            hoverAnnotationZrRef.value = null;
            hoverAnnotationId = null;
        }
        hoverEditHint.value = null;
    },
);


// Store segment centers outside computed for use in tooltip
const segmentCentersRef = ref([]);

watch(hoveredSegmentIndex, () => {
    nextTick(() => {
        const chart = getChartInstance();

        if (!chart) return;

        const bounds = elevationBoundsRef.value;
        const hoveredSegment =
            hoveredSegmentIndex.value !== null
                ? segmentCentersRef.value[hoveredSegmentIndex.value]
                : null;

        const elevationGridModel = chart.getModel().getComponent("grid", 0);
        if (!elevationGridModel) return;

        const rect = elevationGridModel.coordinateSystem.getRect();
        const zr = chart.getZr();

        if (!hoveredSegment) {
            if (hoverBandZrRef.value) {
                hoverBandZrRef.value.ignore = true;
                hoverBandZrRef.value.dirty();
                zr.refresh();
            }
            return;
        }

        const startPixel = chart.convertToPixel({ gridIndex: 0 }, [
            hoveredSegment.startKm,
            bounds.min,
        ]);
        const endPixel = chart.convertToPixel({ gridIndex: 0 }, [
            hoveredSegment.endKm,
            bounds.max,
        ]);
        const left = Math.min(startPixel[0], endPixel[0]);
        const right = Math.max(startPixel[0], endPixel[0]);

        const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
        const clampedLeft = clamp(left, rect.x, rect.x + rect.width);
        const clampedRight = clamp(right, rect.x, rect.x + rect.width);
        const width = Math.max(0, clampedRight - clampedLeft);
        if (width <= 0) return;

        if (!hoverBandZrRef.value) {
            hoverBandZrRef.value = new zrender.Rect({
                shape: {
                    x: clampedLeft,
                    y: rect.y,
                    width,
                    height: rect.height,
                },
                style: {
                    fill: "rgba(34, 197, 94, 0.22)",
                    stroke: "rgba(34, 197, 94, 0.85)",
                    lineWidth: 1.5,
                },
                silent: true,
            });
            hoverBandZrRef.value.z = 10;
            hoverBandZrRef.value.zlevel = 10;
            zr.add(hoverBandZrRef.value);
        } else {
            hoverBandZrRef.value.ignore = false;
            hoverBandZrRef.value.attr({
                shape: {
                    x: clampedLeft,
                    y: rect.y,
                    width,
                    height: rect.height,
                },
            });
        }

        hoverBandZrRef.value.dirty();
        zr.refresh();
    });
});

const chartOption = computed(() => {
    // Skip expensive computations during zoom
    const skipColors = isZooming.value;

    const orderedSegments = [...props.segments].sort((a, b) => {
        const aStart = a.start_km ?? 0;
        const bStart = b.start_km ?? 0;
        return aStart - bStart;
    });

    const paceSegmentRanges = orderedSegments
        .map((segment) => {
            const startKm = segment.start_km ?? 0;
            const endKm = segment.end_km ?? segment.segment_km ?? 0;
            const pace = segment.avg_pace_min_per_km;
            return { startKm, endKm, pace };
        })
        .filter(
            (seg) =>
                Number.isFinite(seg.startKm) &&
                Number.isFinite(seg.endKm) &&
                Number.isFinite(seg.pace),
        );

    let segmentIndex = 0;
    const elevationData = props.points.map((p, idx) => {
        const distanceKm = p.distance / 1000;
        while (
            segmentIndex < paceSegmentRanges.length - 1 &&
            distanceKm > paceSegmentRanges[segmentIndex].endKm
        ) {
            segmentIndex += 1;
        }
        const pace = paceSegmentRanges[segmentIndex]?.pace ?? props.averagePace;
        return [distanceKm, p.elevation, pace, idx];
    });

    const paceValues = elevationData
        .map((d) => d[2])
        .filter((v) => Number.isFinite(v));

    // Use percentiles to avoid outliers dominating the color scale
    const sortedPaces = [...paceValues].sort((a, b) => a - b);
    const p10 = sortedPaces[Math.floor(sortedPaces.length * 0.1)];
    const p90 = sortedPaces[Math.floor(sortedPaces.length * 0.9)];
    const minPace = p10;
    const maxPace = p90;
    const paceRange = Math.max(maxPace - minPace, 0.01);

    const segmentStats = orderedSegments.map(() => ({
        min: Infinity,
        max: -Infinity,
    }));
    let segIdx = 0;
    for (const point of props.points) {
        const km = point.distance / 1000;
        while (
            segIdx < orderedSegments.length &&
            km >
                (orderedSegments[segIdx].end_km ??
                    orderedSegments[segIdx].segment_km ??
                    0)
        ) {
            segIdx += 1;
        }
        if (segIdx >= orderedSegments.length) break;
        const seg = orderedSegments[segIdx];
        const startKm = seg.start_km ?? 0;
        const endKm = seg.end_km ?? seg.segment_km ?? 0;
        if (km >= startKm && km <= endKm) {
            const stats = segmentStats[segIdx];
            stats.min = Math.min(stats.min, point.elevation);
            stats.max = Math.max(stats.max, point.elevation);
        }
    }

    const segmentCentersSorted = orderedSegments.map((segment, index) => {
        const startKm = segment.start_km || 0;
        const endKm = segment.end_km || segment.segment_km || 0;
        const centerKm = (startKm + endKm) / 2;
        const pace = segment.avg_pace_min_per_km;
        const grade = segment.avg_grade_percent;
        const stats = segmentStats[index];
        const minElev = Number.isFinite(stats.min) ? stats.min : 0;
        const maxElev = Number.isFinite(stats.max) ? stats.max : 0;

        return {
            distance: centerKm,
            pace,
            grade,
            startKm,
            endKm,
            elevationRange: `${minElev.toFixed(0)}m - ${maxElev.toFixed(0)}m`,
            segmentLength: endKm - startKm,
        };
    });

    // Store for use in watcher
    segmentCentersRef.value = segmentCentersSorted;

    // Skip expensive boundary computation during zoom
    let segmentBoundaries = [];

    if (!skipColors) {
        // Filter segment boundaries by significant pace changes (> 0.5 min/km difference)
        const segmentBoundariesWithPace = [];
        for (let i = 0; i < orderedSegments.length - 1; i++) {
            const curr = orderedSegments[i];
            const next = orderedSegments[i + 1];
            const paceChange = Math.abs(
                curr.avg_pace_min_per_km - next.avg_pace_min_per_km,
            );

            if (paceChange > 0.5) {
                const boundaryKm = curr.end_km || curr.segment_km || 0;
                if (Number.isFinite(boundaryKm)) {
                    const pointIndex = findClosestPointIndex(boundaryKm);
                    const closestPoint =
                        pointIndex !== -1
                            ? props.points[pointIndex]
                            : props.points[0];

                    segmentBoundariesWithPace.push({
                        km: boundaryKm,
                        elevation: closestPoint.elevation,
                        paceChange: paceChange,
                    });
                }
            }
        }

        // Filter boundaries based on zoom level
        // Calculate visible range
        const totalDistance =
            props.points[props.points.length - 1].distance / 1000;
        const visibleStart = zoomRange.value ? zoomRange.value[0] : 0;
        const visibleEnd = zoomRange.value ? zoomRange.value[1] : totalDistance;
        const visibleDistance = visibleEnd - visibleStart;

        // Target: min 30px between lines on a ~900px wide chart
        const chartWidth = 900;
        const minPixelDistance = 30;
        const minKmDistance = (visibleDistance / chartWidth) * minPixelDistance;

        // Filter visible boundaries with sufficient spacing
        const visibleBoundaries = segmentBoundariesWithPace
            .filter((b) => b.km >= visibleStart && b.km <= visibleEnd)
            .sort((a, b) => a.km - b.km);

        const filteredBoundaries = [];
        let lastKm = -Infinity;

        for (const boundary of visibleBoundaries) {
            if (boundary.km - lastKm >= minKmDistance) {
                filteredBoundaries.push(boundary);
                lastKm = boundary.km;
            }
        }

        segmentBoundaries = filteredBoundaries;
    }

    // Calculate min/max for elevation
    const elevations = elevationData.map((d) => d[1]);
    const minElev = Math.min(...elevations);
    const maxElev = Math.max(...elevations);
    const elevRange = maxElev - minElev;
    const elevationMin = Math.floor(minElev - elevRange * 0.1);
    const elevationMax = Math.ceil(maxElev + elevRange * 0.1);
    elevationBoundsRef.value = { min: elevationMin, max: elevationMax };

    const clamp01 = (value) => Math.max(0, Math.min(1, value));

    const getPaceColor = (pace) => {
        // Apply non-linear transformation for better color distribution
        let t = clamp01((pace - minPace) / paceRange);
        t = Math.pow(t, 0.7); // Emphasize mid-range colors

        const start = [16, 185, 129]; // emerald (fast)
        const mid = [251, 191, 36]; // amber
        const end = [220, 38, 38]; // red (slow)

        const mix = (a, b, amount) => Math.round(a + (b - a) * amount);
        const from = t < 0.5 ? start : mid;
        const to = t < 0.5 ? mid : end;
        const localT = t < 0.5 ? t / 0.5 : (t - 0.5) / 0.5;

        const r = mix(from[0], to[0], localT);
        const g = mix(from[1], to[1], localT);
        const b = mix(from[2], to[2], localT);
        return `rgb(${r}, ${g}, ${b})`;
    };

    const paceSegments = [];
    const paceAreaData = [];

    if (!skipColors) {
        for (let i = 0; i < elevationData.length - 1; i++) {
            const start = elevationData[i];
            const end = elevationData[i + 1];
            const pace = start[2];
            if (!Number.isFinite(pace)) continue;
            const color = getPaceColor(pace);

            paceSegments.push({
                coords: [
                    [start[0], start[1]],
                    [end[0], end[1]],
                ],
                lineStyle: {
                    color,
                },
            });

            paceAreaData.push([start[0], start[1], end[0], end[1], pace]);
        }
    }

    const sliderZoom = {
        type: "slider",
        xAxisIndex: [0],
        bottom: 6,
        height: 28,
        backgroundColor: "rgba(148, 163, 184, 0.08)",
        borderColor: "rgba(148, 163, 184, 0.5)",
        fillerColor: "rgba(34, 197, 94, 0.25)",
        borderRadius: 8,
        handleSize: 18,
        handleStyle: {
            color: "#0f172a",
            borderColor: "#0f172a",
            shadowBlur: 6,
            shadowColor: "rgba(15, 23, 42, 0.2)",
        },
        moveHandleSize: 10,
        moveHandleStyle: {
            color: "#16a34a",
        },
        textStyle: {
            color: "#64748b",
        },
        throttle: 50,
    };
    const insideZoom = {
        type: "inside",
        xAxisIndex: [0],
        zoomOnMouseWheel: "ctrl",
        moveOnMouseWheel: false,
        preventDefaultMouseWheel: false,
        preventDefaultMouseMove: false,
        throttle: 50,
    };

    const totalDistance =
        props.points[props.points.length - 1]?.distance / 1000 || 0;
    const approxChartWidth = 900;
    const minPixelGap = 70;
    const minKmGap =
        totalDistance > 0 ? (totalDistance / approxChartWidth) * minPixelGap : 0;
    const validAnnotations = props.annotations.filter((annotation) =>
        Number.isFinite(Number(annotation?.distance_km)),
    );
    const sortedAnnotations = [...validAnnotations].sort(
        (a, b) => (a.distance_km ?? 0) - (b.distance_km ?? 0),
    );
    const lastByLevel = [];
    const stackMap = new Map();
    sortedAnnotations.forEach((annotation) => {
        const dist = Number(annotation.distance_km ?? 0);
        let level = 0;
        while (
            lastByLevel[level] !== undefined &&
            dist - lastByLevel[level] < minKmGap
        ) {
            level += 1;
        }
        lastByLevel[level] = dist;
        stackMap.set(annotation.id || dist, level);
    });
    annotationStackRef.value = stackMap;

    const annotationsData = sortedAnnotations.map((annotation) => {
        const distanceKm = Number(annotation.distance_km);
        const elevation = getElevationAtDistance(distanceKm);
        const level = stackMap.get(annotation.id || distanceKm) || 0;
        return {
            value: [
                distanceKm,
                elevation,
                annotation.type,
                annotation.label,
                level,
            ],
            annotation,
        };
    });
    const option = {
        tooltip: {
            trigger: "axis",
            showContent: true,
            hideDelay: props.tapToReveal ? 3000 : 0,
            backgroundColor: "#0f172a",
            borderColor: "rgba(148, 163, 184, 0.6)",
            borderWidth: 1,
            textStyle: {
                color: "#f8fafc",
                fontFamily: '"Space Grotesk", "Trebuchet MS", sans-serif',
                fontSize: 14,
            },
            extraCssText:
                "border-radius: 12px; box-shadow: 0 20px 45px -35px rgba(15, 23, 42, 0.9); padding: 12px 14px; line-height: 1.5; max-width: 220px;",
            position: function (point, params, dom, rect, size) {
                const tooltipWidth = size.contentSize[0];
                const viewWidth = size.viewSize[0];
                const padding = 12;
                const offset = 14;

                let x = point[0] + offset;
                if (x + tooltipWidth > viewWidth - padding) {
                    x = point[0] - tooltipWidth - offset;
                }
                x = Math.max(
                    padding,
                    Math.min(x, viewWidth - tooltipWidth - padding),
                );

                const y = Math.max(padding, point[1] - size.contentSize[1] / 2);
                return [x, y];
            },
            axisPointer: {
                show: true,
                type: "line",
                animation: false,
                lineStyle: {
                    color: "#22c55e",
                    width: 2.5,
                    type: "solid",
                },
                label: {
                    backgroundColor: "#0f172a",
                    color: "#f8fafc",
                    formatter: (params) => {
                        if (params.axisDimension === "x") {
                            return params.value.toFixed(2) + " km";
                        }
                        return params.value.toFixed(0) + " m";
                    },
                },
            },
            formatter: (params) => {
                if (!Array.isArray(params)) params = [params];
                const elevationParam = params.find(
                    (param) => param.seriesName === "Elevation",
                );
                let result = "";

                if (elevationParam) {
                    const dataIndex = elevationParam.dataIndex;
                    const pointIndex = elevationData[dataIndex]?.[3];
                    const punctualMetrics = getPunctualMetrics(pointIndex);
                    const paceValue = getPaceAtDistance(
                        elevationParam.value[0],
                    );
                    result += `<b>Distance:</b> ${elevationParam.value[0].toFixed(2)} km<br/>`;
                    result += `<b>Elevation:</b> ${elevationParam.value[1].toFixed(0)} m<br/>`;
                    if (Number.isFinite(paceValue)) {
                        result += `<b>Pace:</b> ${formatPace(paceValue)}/km<br/>`;
                    }
                    if (Number.isFinite(punctualMetrics.slope)) {
                        result += `<b>Slope:</b> ${punctualMetrics.slope.toFixed(1)}%<br/>`;
                    }
                }

                // Add segment info if available
                if (
                    hoveredSegmentIndex.value !== null &&
                    segmentCentersRef.value[hoveredSegmentIndex.value]
                ) {
                    const seg =
                        segmentCentersRef.value[hoveredSegmentIndex.value];
                    result += `<br/><b>Segment:</b> ${seg.startKm.toFixed(2)} - ${seg.endKm.toFixed(2)} km<br/>`;
                    result += `<b>Pace:</b> ${formatPace(seg.pace)}/km<br/>`;
                    result += `<b>Mean Slope:</b> ${seg.grade.toFixed(1)}%<br/>`;
                    result += `<b>Elevation Range:</b> ${seg.elevationRange}`;
                }

                return result;
            },
        },
        grid: [
            {
                left: props.tapToReveal ? 42 : 100,
                right: 50,
                top: 60,
                height: "70%",
            },
        ],
        xAxis: [
            {
                type: "value",
                gridIndex: 0,
                name: "Distance (km)",
                nameLocation: "middle",
                nameGap: 30,
                min: 0,
                max: totalDistance,
                axisLine: {
                    lineStyle: {
                        color: "rgba(148, 163, 184, 0.8)",
                    },
                },
                axisLabel: {
                    color: "#64748b",
                    fontSize: props.tapToReveal ? 10 : 12,
                    formatter: (value) => Math.round(value),
                },
                nameTextStyle: {
                    color: "#0f172a",
                    fontWeight: 600,
                    fontSize: props.tapToReveal ? 11 : 12,
                },
                splitLine: {
                    show: true,
                    lineStyle: {
                        color: "rgba(148, 163, 184, 0.18)",
                    },
                },
            },
        ],
        yAxis: [
            {
                type: "value",
                gridIndex: 0,
                name: props.tapToReveal ? "Elev. (m)" : "Elevation (m)",
                nameLocation: "middle",
                nameGap: props.tapToReveal ? 22 : 45,
                axisLine: {
                    lineStyle: {
                        color: "rgba(148, 163, 184, 0.8)",
                    },
                },
                axisLabel: {
                    color: "#64748b",
                    fontSize: props.tapToReveal ? 10 : 12,
                    formatter: (value) => Math.round(value),
                },
                nameTextStyle: {
                    color: "#0f172a",
                    fontWeight: 600,
                    fontSize: props.tapToReveal ? 11 : 12,
                },
                splitLine: {
                    lineStyle: {
                        color: "rgba(148, 163, 184, 0.18)",
                    },
                },
                min: elevationMin,
                max: elevationMax,
            },
        ],
        series: [
            // Segment boundary grid lines (stop at elevation profile)
            {
                name: "Grid",
                type: "lines",
                coordinateSystem: "cartesian2d",
                xAxisIndex: 0,
                yAxisIndex: 0,
                silent: true,
                animation: false,
                data: segmentBoundaries.map((boundary) => ({
                    coords: [
                        [boundary.km, elevationMin],
                        [boundary.km, boundary.elevation],
                    ],
                    lineStyle: {
                        color: "rgba(148, 163, 184, 0.3)",
                        width: 1,
                        type: "solid",
                    },
                })),
                z: 0,
            },
            // Elevation profile
            {
                name: "Elevation",
                id: "elevation",
                type: "line",
                xAxisIndex: 0,
                yAxisIndex: 0,
                data: elevationData.map((point) => [point[0], point[1]]),
                smooth: false,
                symbol: "none",
                lineStyle: {
                    width: skipColors ? 2.5 : 2,
                    color: skipColors ? "#0f172a" : "#1f2937",
                    shadowBlur: 6,
                    shadowColor: "rgba(15, 23, 42, 0.25)",
                },
                z: 10,
            },
            {
                name: "Annotations",
                type: "custom",
                coordinateSystem: "cartesian2d",
                xAxisIndex: 0,
                yAxisIndex: 0,
                clip: false,
                emphasis: {
                    disabled: true,
                },
                silent: true,
                data: annotationsData,
                renderItem: (params, api) => {
                    const x = api.value(0);
                    const y = api.value(1);
                    const type = api.value(2);
                    if (
                        !Number.isFinite(x) ||
                        !Number.isFinite(y) ||
                        !Number.isFinite(elevationMin) ||
                        !Number.isFinite(elevationMax)
                    ) {
                        return null;
                    }

                    const point = api.coord([x, y]);
                    const coordSys = params.coordSys;
                    if (!coordSys) {
                        return null;
                    }
                    const bottomPoint = api.coord([x, elevationMin]);
                    const topPoint = api.coord([x, elevationMax]);
                    const accent = type === "generic" ? "#9333ea" : "#10b981";
                    const topY = coordSys.y;
                    const level = api.value(4) || 0;
                    const tipY = topY - 4;
                    const dropletRadius = 4;
                    const dropletY = Math.max(topY - 12 - level * 12, 6);

                    return {
                        type: "group",
                        emphasis: {
                            disabled: true,
                        },
                        cursor: "pointer",
                        children: [
                            {
                                type: "rect",
                                shape: {
                                    x: point[0] - 12,
                                    y: dropletY - 12,
                                    width: 24,
                                    height: 24,
                                    r: 8,
                                },
                                style: {
                                    fill: "rgba(0,0,0,0)",
                                },
                                silent: false,
                            },
                            {
                                type: "line",
                                shape: {
                                    x1: point[0],
                                    y1: bottomPoint[1],
                                    x2: point[0],
                                    y2: topPoint[1],
                                },
                                style: {
                                    stroke: accent,
                                    lineWidth: 1.5,
                                    lineDash: [5, 5],
                                },
                                silent: true,
                            },
                            {
                                type: "circle",
                                shape: {
                                    cx: point[0],
                                    cy: dropletY,
                                    r: dropletRadius,
                                },
                                style: {
                                    fill: accent,
                                    shadowBlur: 6,
                                    shadowColor: "rgba(15, 23, 42, 0.18)",
                                },
                                silent: true,
                            },
                            {
                                type: "polygon",
                                shape: {
                                    points: [
                                        [point[0] - dropletRadius, dropletY + dropletRadius],
                                        [point[0] + dropletRadius, dropletY + dropletRadius],
                                        [point[0], tipY],
                                    ],
                                },
                                style: {
                                    fill: accent,
                                },
                                silent: true,
                            },
                        ],
                    };
                },
                z: 30,
            },
            {
                name: "Pace Area",
                type: "custom",
                coordinateSystem: "cartesian2d",
                xAxisIndex: 0,
                yAxisIndex: 0,
                silent: true,
                data: paceAreaData,
                renderItem: (params, api) => {
                    const x0 = api.value(0);
                    const y0 = api.value(1);
                    const x1 = api.value(2);
                    const y1 = api.value(3);
                    const pace = api.value(4);

                    const p0 = api.coord([x0, y0]);
                    const p1 = api.coord([x1, y1]);
                    const p2 = api.coord([x1, elevationMin]);
                    const p3 = api.coord([x0, elevationMin]);

                    return {
                        type: "polygon",
                        shape: {
                            points: [p0, p1, p2, p3],
                        },
                        style: api.style({
                            fill: getPaceColor(pace),
                            opacity: 0.18,
                        }),
                    };
                },
                z: 2,
            },
            {
                name: "Pace Coloring",
                type: "lines",
                coordinateSystem: "cartesian2d",
                xAxisIndex: 0,
                yAxisIndex: 0,
                data: paceSegments,
                silent: true,
                lineStyle: {
                    width: 3,
                    opacity: 0.9,
                },
                z: 15,
            },
        ],
        dataZoom: props.tapToReveal ? [sliderZoom] : [insideZoom, sliderZoom],
        brush: {
            xAxisIndex: [0],
            brushType: "lineX",
            brushMode: "single",
            outOfBrush: {
                colorAlpha: 0.3,
            },
            brushStyle: {
                borderWidth: 2,
                color: "rgba(34, 197, 94, 0.18)",
                borderColor: "rgba(34, 197, 94, 0.7)",
            },
            throttleType: "debounce",
            throttleDelay: 300,
        },
    };
    return option;
});
</script>

<style scoped>
/* Ensure proper rendering */
.echarts {
    width: 100%;
    height: 100%;
}
</style>
