import type { StompHeaders } from '@stomp/stompjs'

export const MainEvent = {
    CONNECT: 'connect',
    DISCONNECT: 'disconnect',
    EXPERIMENT: 'experiment',
    DEFAULT: 'default',
    NEW: 'new',
    PREDICTIONS: 'predictions',
    FINAL: 'final',
    LOG: 'log'
} as const;
// eslint-disable-next-line no-redeclare
export type MainEvent = typeof MainEvent[keyof typeof MainEvent];

export const SubEvent = {
    EXPERIMENT: ['description'],
    DEFAULT: ['configuration'],
    NEW: ['task', 'configuration'],
    PREDICTIONS: ['configurations'],
    FINAL: ['configuration'],
    LOG: ['info', 'debug', 'critical']
}

// a message of the event service with its body parsed (the store parses each message once)
export interface ParsedMessage {
    headers: StompHeaders
    body: any
}
