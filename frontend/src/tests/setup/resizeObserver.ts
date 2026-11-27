import { beforeEach } from 'vitest'

// jsdom has no ResizeObserver, and every chart creates one. This stub, installed for all specs through `setupFiles`
// (vite.config.ts), does nothing until a test reports a size with `resizeTo`.

// eslint-disable-next-line no-unused-vars -- the names document the parameters
type Callback = (entries: ResizeObserverEntry[], observer: ResizeObserver) => void

class StubResizeObserver {
    static instances: StubResizeObserver[] = []

    readonly observed = new Set<Element>()
    disconnected = false
    private readonly callback: Callback

    constructor(callback: Callback) {
        this.callback = callback
        StubResizeObserver.instances.push(this)
    }

    observe(element: Element) {
        this.observed.add(element)
    }

    unobserve(element: Element) {
        this.observed.delete(element)
    }

    disconnect() {
        this.disconnected = true
        this.observed.clear()
    }

    report(element: Element, width: number, height: number) {
        const entry = { target: element, contentRect: { width, height } } as ResizeObserverEntry
        this.callback([entry], this as unknown as ResizeObserver)
    }
}

;(globalThis as any).ResizeObserver = StubResizeObserver

beforeEach(() => {
    StubResizeObserver.instances = []
})

// the class the code under test gets from `globalThis`, so these helpers and the code share one list of observers
const installed = () => (globalThis as any).ResizeObserver as typeof StubResizeObserver

// tells the observers of `element` its size, as the browser does when it changes (and once when observing starts)
export function resizeTo(element: Element, width: number, height = 450) {
    for (const observer of installed().instances) {
        if (observer.observed.has(element)) observer.report(element, width, height)
    }
}

// the observers created in the current test
export function createdResizeObservers() {
    return installed().instances
}
