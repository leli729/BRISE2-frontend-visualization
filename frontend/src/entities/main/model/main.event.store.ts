import { computed, ref, shallowRef } from 'vue'
import { defineStore } from 'pinia'
import { MainEvent } from './main.types'
import type { ParsedMessage } from './main.types'
import { stompClient } from '../../../shared/api/stomp.client'
import type { ExperimentDescription, ParameterSpec, RawProductConfiguration, SearchSpaceRegion } from '../../experiment/model/experiment.model'
import type { IMessage } from '@stomp/stompjs'
import { EMPTY, mergeMap, of, share } from 'rxjs'
import type { Observable } from 'rxjs'
import { parseJsonWithInfinity } from '../../../shared/lib'

const isConnected = ref(false)
stompClient.connectionState$.subscribe(state => {
   isConnected.value = state === 1
})

export const useMainEventStore = defineStore('mainEvent', () => {
   // the description of the running experiment, written only by the description event
   const experiment_description = ref<ExperimentDescription | null>(null)
   // the uploaded product configuration, written only by the upload and read only by Start: the description event
   // has no search space, so the running description could not start an experiment again
   const raw_product_configuration = ref<RawProductConfiguration | null>(null)
   // the search space regions as main-node describes them, in its canonical order
   const regions = ref<SearchSpaceRegion[]>([])
   // every parameter of the search space by its full name
   const specsByName = computed(() => {
      const specs: Record<string, ParameterSpec> = {}
      for (const region of regions.value) {
         for (const parameter of region.Parameters) {
            specs[parameter.Name] = parameter
         }
      }
      return specs
   })
   const searchspaceReady = ref(false)
   const experimentFinished = ref(false)
   const plotlyInstance = shallowRef<any>(null)
   // the messages of a queue with their bodies parsed, the only place that parses them. The raw Infinity/-Infinity/NaN
   // tokens of main-node, which are not valid JSON, become the real values. A body that does not parse is reported and
   // skipped: an error would end the stream for every subscriber of the queue.
   function parsedMessages(queue: string): Observable<ParsedMessage> {
      return stompClient.watch(queue, { 'x-message-ttl': '1000' }).pipe(
         mergeMap((message: IMessage) => {
            try {
               return of({ headers: message.headers, body: parseJsonWithInfinity(message.body) })
            } catch (error) {
               console.error(`a message of ${queue} does not parse and is skipped:`, error)
               return EMPTY
            }
         }),
         share()
      )
   }

   const listeners: Record<string, Observable<ParsedMessage>> = {
      [MainEvent.EXPERIMENT]: parsedMessages('front_experiment_queue'),
      [MainEvent.FINAL]: parsedMessages('front_final_queue'),
      [MainEvent.DEFAULT]: parsedMessages('front_default_queue'),
      [MainEvent.NEW]: parsedMessages('front_new_queue'),
      [MainEvent.PREDICTIONS]: parsedMessages('front_predictions_queue'),
      [MainEvent.LOG]: parsedMessages('front_log_queue')
   }

   function onEvent(event: MainEvent): Observable<ParsedMessage> | undefined {
      return listeners[String(event)]
   }

   // load plotly async in the background
   async function loadPlotly() {
      if (!plotlyInstance.value) {
         try {
            const [core, heatmap, scattergl, parcoords, contour, bar] = await Promise.all([
               import('plotly.js/lib/core'),
               import('plotly.js/lib/heatmap'),
               import('plotly.js/lib/scattergl'),
               import('plotly.js/lib/parcoords'),
               import('plotly.js/lib/contour'),
               import('plotly.js/lib/bar'),
            ])
            const Plotly = core.default

            // 'scatter' is intentionally not registered here: plotly.js/lib/core
            // registers it internally by default.
            Plotly.register([
               heatmap.default,
               scattergl.default,
               parcoords.default,
               contour.default,
               bar.default,
            ])

            plotlyInstance.value = Plotly
            console.log('Plotly successfully initialized')
         } catch (error) {
            console.error('no success', error)
         }
      }
   }

   // starts the subsription to Experiment event
   function initEvent() {
      console.log('initEvent called, subscribing to EXPERIMENT queue')
      onEvent(MainEvent.EXPERIMENT)?.subscribe((message) => {
         console.log('EXPERIMENT message received:', message.headers['message_subtype'])
         if (message.headers['message_subtype'] === 'description') {
            console.log(message.body)
            const body = message.body as { experiment_description: ExperimentDescription, regions?: SearchSpaceRegion[] }
            console.log('after the setting', experiment_description.value?.Context?.TaskConfiguration?.TaskName)
            experiment_description.value = body.experiment_description
            // regions are always an array, and the search space is ready only once they have arrived
            if (Array.isArray(body.regions)) {
               regions.value = body.regions
               searchspaceReady.value = true
            } else {
               console.error('the description event has no regions')
               regions.value = []
               searchspaceReady.value = false
            }
            experimentFinished.value = false

         }
      })

      onEvent(MainEvent.FINAL)?.subscribe((message) => {
         if (message.headers['message_subtype'] === 'configuration') {
            experimentFinished.value = true
         }
      })
   }



   return { regions, specsByName, searchspaceReady, experiment_description, raw_product_configuration, experimentFinished, isConnected, onEvent, initEvent, loadPlotly, plotlyInstance }
})