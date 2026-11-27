<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Heatmap from './Heatmap.vue'
import RegionTitle from '../../../../entities/experiment/ui/RegionTitle.vue'
import { isCategoricalAxisParameter } from '../../../../entities/experiment/lib/search-space'
import type { SearchSpaceRegion } from '../../../../entities/experiment/model/experiment.model'

defineOptions({ name: 'HeatmapRegionPanel' })

const props = withDefaults(defineProps<{
    region: SearchSpaceRegion
    showTitle: boolean
    heatmapObjective: string
    active?: boolean
}>(), { active: true })

// parameters of the region that can span a heatmap axis: the categorical ones
const heatmapParameterNames = computed(() =>
    props.region.Parameters.filter(isCategoricalAxisParameter).map(parameter => parameter.Name)
)

const heatmapParam1 = ref("")
const heatmapParam2 = ref("")

// each axis offers every parameter except the one chosen for the other axis
const heatmapParam1Items = computed(() => heatmapParameterNames.value.filter(param => param !== heatmapParam2.value))
const heatmapParam2Items = computed(() => heatmapParameterNames.value.filter(param => param !== heatmapParam1.value))

// select the first two parameters of the region on initialization and new experiment description
watch(
    heatmapParameterNames,
    (params) => {
        heatmapParam1.value = params[0] ?? ""
        heatmapParam2.value = params[1] ?? ""
    },
    { immediate: true }
)
</script>

<template>
  <div>
    <RegionTitle
      v-if="showTitle"
      :region="region"
    />
    <div
      v-if="heatmapParameterNames.length < 2"
      class="text-body-2 text-medium-emphasis region-message"
    >
      Not enough categorical parameters in this region for a heatmap.
    </div>
    <template v-else>
      <v-select
        v-model="heatmapParam1"
        :items="heatmapParam1Items"
        label="Parameter 1"
        density="compact"
        variant="outlined"
        hide-details
        class="user-input"
      />
      <v-select
        v-model="heatmapParam2"
        :items="heatmapParam2Items"
        label="Parameter 2"
        density="compact"
        variant="outlined"
        hide-details
        class="user-input"
      />
      <Heatmap
        :active="active"
        :region="region"
        :heatmap-param1="heatmapParam1"
        :heatmap-param2="heatmapParam2"
        :heatmap-objective="heatmapObjective"
      />
    </template>
  </div>
</template>

<style scoped>
.user-input {
  margin: 10px
}
.region-message {
  margin: 10px
}
</style>
