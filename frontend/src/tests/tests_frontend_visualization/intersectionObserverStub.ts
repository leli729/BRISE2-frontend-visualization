import { vi } from 'vitest'

// jsdom has no IntersectionObserver. This stub lets a test decide when an observed element is in view.
// By default an observed element is reported in view right after `observe` (as a visible element is by the browser),
// so a spec that does not care sees its chart drawn; `reportOnObserve: false` leaves it to `setInView`.

// eslint-disable-next-line no-unused-vars -- the names document the parameters
type Callback = (entries: IntersectionObserverEntry[], observer: IntersectionObserver) => void

class StubIntersectionObserver {
    static reportOnObserve = true
    static instances: StubIntersectionObserver[] = []

    readonly observed = new Set<Element>()
    disconnected = false
    private readonly callback: Callback
    readonly options?: object

    constructor(callback: Callback, options?: object) {
        this.callback = callback
        this.options = options
        StubIntersectionObserver.instances.push(this)
    }

    observe(element: Element) {
        this.observed.add(element)
        if (StubIntersectionObserver.reportOnObserve) {
            void Promise.resolve().then(() => {
                if (!this.disconnected && this.observed.has(element)) this.report(element, true)
            })
        }
    }

    unobserve(element: Element) {
        this.observed.delete(element)
    }

    disconnect() {
        this.disconnected = true
        this.observed.clear()
    }

    takeRecords() {
        return []
    }

    report(element: Element, inView: boolean) {
        const entry = { target: element, isIntersecting: inView, intersectionRatio: inView ? 1 : 0 } as IntersectionObserverEntry
        this.callback([entry], this as unknown as IntersectionObserver)
    }
}

export function installIntersectionObserver({ reportOnObserve = true } = {}) {
    StubIntersectionObserver.reportOnObserve = reportOnObserve
    StubIntersectionObserver.instances = []
    vi.stubGlobal('IntersectionObserver', StubIntersectionObserver)
}

export function uninstallIntersectionObserver() {
    vi.unstubAllGlobals()
    StubIntersectionObserver.instances = []
}

// tells the observers of `element` that it entered or left the view
export function setInView(element: Element, inView: boolean) {
    for (const observer of StubIntersectionObserver.instances) {
        if (observer.observed.has(element)) observer.report(element, inView)
    }
}

// the observers created since `installIntersectionObserver`
export function createdObservers() {
    return StubIntersectionObserver.instances
}
