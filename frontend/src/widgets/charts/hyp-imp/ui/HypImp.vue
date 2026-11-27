<script setup lang="ts">
import { ref } from 'vue'
import { usePlotStore } from '../../../../entities/main/model/plot.store'
import { renderHypImp } from '../render'
import { storeToRefs } from 'pinia'
import { MainClientApi } from '../../../../entities/main/api/main.client.store'
import { useMainEventStore } from '../../../../entities/main'
import { trialsOfRegion } from '../../../../entities/experiment/lib/regions'
import type { SearchSpaceRegion } from '../../../../entities/experiment/model/experiment.model'
import { useChartRender, PLOT_REQUEST_INTERVAL_MS } from '../../model/use-chart-render'

const plotStore = usePlotStore()
const store = useMainEventStore()
const { allRes } = storeToRefs(plotStore)
const { plotlyInstance } = storeToRefs(store)
const hypimp = ref<HTMLElement | null>(null)

const props = withDefaults(defineProps<{
    region: SearchSpaceRegion
    hypImpParams: string[]
    hypImpObjective: string
    active?: boolean
}>(), { active: true })

async function render(canDraw: () => boolean) {
    // the plot service takes a requested parameter that a trial lacks as inactive in it
    const trials = trialsOfRegion(allRes.value, props.region)
    // main-node returns the empty result below two trials: no request for it
    if (trials.length < 2) {
        renderHypImp(plotlyInstance.value!, hypimp.value!, {})
        return
    }
    const result = await MainClientApi.calculatePlot(
        "hyperparameter_importances",
        {
            "trials": trials,
            "parameters": props.hypImpParams,
            "objective": props.hypImpObjective
        }
    )

    // the chart may have been unmounted, or stopped being shown, while the request was in flight
    if (!canDraw()) return
    renderHypImp(plotlyInstance.value!, hypimp.value!, result)
}

useChartRender({
    element: hypimp,
    plotly: plotlyInstance,
    sources: [
        allRes,
        // the parameters are a prop array: a getter that reads its items, as the watch is not deep
        () => [...props.hypImpParams],
        () => props.hypImpObjective
    ],
    render,
    active: () => props.active,
    minIntervalMs: PLOT_REQUEST_INTERVAL_MS
})
</script>



<template>
  <div
    ref="hypimp"
  />
</template>