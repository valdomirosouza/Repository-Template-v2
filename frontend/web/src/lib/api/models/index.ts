/* tslint:disable */
/* eslint-disable */
/**
 * 
 * @export
 * @interface DecisionIn
 */
export interface DecisionIn {
    /**
     * 
     * @type {DecisionInDecisionEnum}
     * @memberof DecisionIn
     */
    decision: DecisionInDecisionEnum;
    /**
     * 
     * @type {string}
     * @memberof DecisionIn
     */
    rationale: string;
}


/**
 * @export
 */
export const DecisionInDecisionEnum = {
    Approved: 'APPROVED',
    Rejected: 'REJECTED'
} as const;
export type DecisionInDecisionEnum = typeof DecisionInDecisionEnum[keyof typeof DecisionInDecisionEnum];

/**
 * 
 * @export
 * @interface DecisionOut
 */
export interface DecisionOut {
    /**
     * 
     * @type {string}
     * @memberof DecisionOut
     */
    requestId: string;
    /**
     * 
     * @type {DecisionOutDecisionEnum}
     * @memberof DecisionOut
     */
    decision: DecisionOutDecisionEnum;
    /**
     * 
     * @type {string}
     * @memberof DecisionOut
     */
    message: string;
}


/**
 * @export
 */
export const DecisionOutDecisionEnum = {
    Approved: 'APPROVED',
    Rejected: 'REJECTED'
} as const;
export type DecisionOutDecisionEnum = typeof DecisionOutDecisionEnum[keyof typeof DecisionOutDecisionEnum];

/**
 * 
 * @export
 * @interface FieldError
 */
export interface FieldError {
    /**
     * 
     * @type {string}
     * @memberof FieldError
     */
    field: string;
    /**
     * 
     * @type {string}
     * @memberof FieldError
     */
    message: string;
}
/**
 * 
 * @export
 * @interface HITLRequestSummary
 */
export interface HITLRequestSummary {
    /**
     * 
     * @type {string}
     * @memberof HITLRequestSummary
     */
    requestId: string;
    /**
     * 
     * @type {string}
     * @memberof HITLRequestSummary
     */
    agentId: string;
    /**
     * 
     * @type {string}
     * @memberof HITLRequestSummary
     */
    actionType: string;
    /**
     * PII-masked summary shown to the reviewer (never raw action parameters).
     * @type {string}
     * @memberof HITLRequestSummary
     */
    contextSummary: string;
    /**
     * 
     * @type {number}
     * @memberof HITLRequestSummary
     */
    riskScore: number;
    /**
     * 
     * @type {HITLRequestSummaryStatusEnum}
     * @memberof HITLRequestSummary
     */
    status: HITLRequestSummaryStatusEnum;
    /**
     * 
     * @type {string}
     * @memberof HITLRequestSummary
     */
    createdAt: string;
    /**
     * 
     * @type {string}
     * @memberof HITLRequestSummary
     */
    expiresAt: string;
}


/**
 * @export
 */
export const HITLRequestSummaryStatusEnum = {
    Pending: 'PENDING',
    Approved: 'APPROVED',
    Rejected: 'REJECTED',
    Expired: 'EXPIRED'
} as const;
export type HITLRequestSummaryStatusEnum = typeof HITLRequestSummaryStatusEnum[keyof typeof HITLRequestSummaryStatusEnum];

/**
 * 
 * @export
 * @interface HITLStatusResponse
 */
export interface HITLStatusResponse {
    /**
     * 
     * @type {string}
     * @memberof HITLStatusResponse
     */
    status: string;
    /**
     * 
     * @type {number}
     * @memberof HITLStatusResponse
     */
    pendingCount: number;
    /**
     * 
     * @type {string}
     * @memberof HITLStatusResponse
     */
    message: string;
}
/**
 * 
 * @export
 * @interface HealthResponse
 */
export interface HealthResponse {
    /**
     * 
     * @type {string}
     * @memberof HealthResponse
     */
    status: string;
    /**
     * 
     * @type {string}
     * @memberof HealthResponse
     */
    version: string;
}
/**
 * 
 * @export
 * @interface ModelError
 */
export interface ModelError {
    /**
     * Mirrors the HTTP status code.
     * @type {number}
     * @memberof ModelError
     */
    status: number;
    /**
     * Stable, screaming-snake error code clients branch on (adding is non-breaking).
     * @type {ModelErrorCodeEnum}
     * @memberof ModelError
     */
    code: ModelErrorCodeEnum;
    /**
     * Short, human-readable, stable for a given code.
     * @type {string}
     * @memberof ModelError
     */
    title: string;
    /**
     * Instance-specific message; PII-masked.
     * @type {string}
     * @memberof ModelError
     */
    detail?: string;
    /**
     * Correlation id; echoed in the X-Request-ID response header.
     * @type {string}
     * @memberof ModelError
     */
    requestId: string;
    /**
     * OpenTelemetry trace id for support correlation.
     * @type {string}
     * @memberof ModelError
     */
    traceId?: string;
    /**
     * Field-level validation problems (422).
     * @type {Array<FieldError>}
     * @memberof ModelError
     */
    errors?: Array<FieldError>;
}


/**
 * @export
 */
export const ModelErrorCodeEnum = {
    ValidationError: 'VALIDATION_ERROR',
    BadRequest: 'BAD_REQUEST',
    Unauthorized: 'UNAUTHORIZED',
    Forbidden: 'FORBIDDEN',
    NotFound: 'NOT_FOUND',
    Conflict: 'CONFLICT',
    RateLimited: 'RATE_LIMITED',
    Unavailable: 'UNAVAILABLE',
    InternalError: 'INTERNAL_ERROR',
    IdempotencyKeyReused: 'IDEMPOTENCY_KEY_REUSED'
} as const;
export type ModelErrorCodeEnum = typeof ModelErrorCodeEnum[keyof typeof ModelErrorCodeEnum];

/**
 * 
 * @export
 * @interface RequestIn
 */
export interface RequestIn {
    /**
     * 
     * @type {string}
     * @memberof RequestIn
     */
    requestText: string;
    /**
     * 
     * @type {RequestInPriorityEnum}
     * @memberof RequestIn
     */
    priority?: RequestInPriorityEnum;
}


/**
 * @export
 */
export const RequestInPriorityEnum = {
    Low: 'low',
    Normal: 'normal',
    High: 'high'
} as const;
export type RequestInPriorityEnum = typeof RequestInPriorityEnum[keyof typeof RequestInPriorityEnum];

/**
 * 
 * @export
 * @interface RequestOut
 */
export interface RequestOut {
    /**
     * 
     * @type {string}
     * @memberof RequestOut
     */
    requestId: string;
    /**
     * 
     * @type {RequestOutStatusEnum}
     * @memberof RequestOut
     */
    status: RequestOutStatusEnum;
    /**
     * 
     * @type {string}
     * @memberof RequestOut
     */
    createdAt: string;
    /**
     * 
     * @type {string}
     * @memberof RequestOut
     */
    message: string;
}


/**
 * @export
 */
export const RequestOutStatusEnum = {
    Queued: 'queued',
    Processing: 'processing',
    Completed: 'completed',
    Failed: 'failed'
} as const;
export type RequestOutStatusEnum = typeof RequestOutStatusEnum[keyof typeof RequestOutStatusEnum];

/**
 * 
 * @export
 * @interface RunTraceResponse
 */
export interface RunTraceResponse {
    /**
     * 
     * @type {string}
     * @memberof RunTraceResponse
     */
    requestId: string;
    /**
     * 
     * @type {RunTraceResponseStatusEnum}
     * @memberof RunTraceResponse
     */
    status: RunTraceResponseStatusEnum;
    /**
     * 
     * @type {string}
     * @memberof RunTraceResponse
     */
    createdAt: string;
    /**
     * 
     * @type {string}
     * @memberof RunTraceResponse
     */
    updatedAt: string;
    /**
     * 
     * @type {{ [key: string]: any; }}
     * @memberof RunTraceResponse
     */
    result?: { [key: string]: any; };
    /**
     * 
     * @type {string}
     * @memberof RunTraceResponse
     */
    error?: string;
    /**
     * 
     * @type {Array<TraceEvent>}
     * @memberof RunTraceResponse
     */
    timeline: Array<TraceEvent>;
    /**
     * Which real strategy built the timeline. metadata_request_id = exact metadata.request_id match; time_window_approximate = reserved (off by default); none = no event could be honestly associated (SPEC-API-004 §9.1).
     * @type {RunTraceResponseTimelineAssociationEnum}
     * @memberof RunTraceResponse
     */
    timelineAssociation: RunTraceResponseTimelineAssociationEnum;
}


/**
 * @export
 */
export const RunTraceResponseStatusEnum = {
    Queued: 'queued',
    Processing: 'processing',
    Completed: 'completed',
    Failed: 'failed'
} as const;
export type RunTraceResponseStatusEnum = typeof RunTraceResponseStatusEnum[keyof typeof RunTraceResponseStatusEnum];

/**
 * @export
 */
export const RunTraceResponseTimelineAssociationEnum = {
    MetadataRequestId: 'metadata_request_id',
    TimeWindowApproximate: 'time_window_approximate',
    None: 'none'
} as const;
export type RunTraceResponseTimelineAssociationEnum = typeof RunTraceResponseTimelineAssociationEnum[keyof typeof RunTraceResponseTimelineAssociationEnum];

/**
 * 
 * @export
 * @interface SLOItemStatus
 */
export interface SLOItemStatus {
    /**
     * 
     * @type {string}
     * @memberof SLOItemStatus
     */
    name: string;
    /**
     * 
     * @type {string}
     * @memberof SLOItemStatus
     */
    sliType: string;
    /**
     * 
     * @type {string}
     * @memberof SLOItemStatus
     */
    description?: string;
    /**
     * 
     * @type {number}
     * @memberof SLOItemStatus
     */
    target?: number;
    /**
     * 
     * @type {number}
     * @memberof SLOItemStatus
     */
    targetMs?: number;
    /**
     * 
     * @type {number}
     * @memberof SLOItemStatus
     */
    targetMax?: number;
    /**
     * 
     * @type {string}
     * @memberof SLOItemStatus
     */
    window?: string;
    /**
     * 
     * @type {SLOObserved}
     * @memberof SLOItemStatus
     */
    observed: SLOObserved;
}
/**
 * Honest observed block. When a real value cannot be computed, data_available is false and note explains why — a number is never fabricated (CLAUDE.md §3.6).
 * @export
 * @interface SLOObserved
 */
export interface SLOObserved {
    /**
     * 
     * @type {boolean}
     * @memberof SLOObserved
     */
    dataAvailable: boolean;
    /**
     * 
     * @type {number}
     * @memberof SLOObserved
     */
    value?: number;
    /**
     * 
     * @type {string}
     * @memberof SLOObserved
     */
    unit?: string;
    /**
     * 
     * @type {string}
     * @memberof SLOObserved
     */
    source?: string;
    /**
     * e.g. "process_lifetime" — NOT the 30-day SLO window.
     * @type {string}
     * @memberof SLOObserved
     */
    scope?: string;
    /**
     * 
     * @type {string}
     * @memberof SLOObserved
     */
    note?: string;
}
/**
 * 
 * @export
 * @interface SLOServiceStatus
 */
export interface SLOServiceStatus {
    /**
     * 
     * @type {string}
     * @memberof SLOServiceStatus
     */
    name: string;
    /**
     * 
     * @type {string}
     * @memberof SLOServiceStatus
     */
    description?: string;
    /**
     * 
     * @type {Array<SLOItemStatus>}
     * @memberof SLOServiceStatus
     */
    slos: Array<SLOItemStatus>;
}
/**
 * 
 * @export
 * @interface SLOStatusResponse
 */
export interface SLOStatusResponse {
    /**
     * Top-level version from docs/sre/slo/slo.yaml.
     * @type {string}
     * @memberof SLOStatusResponse
     */
    sourceVersion?: string;
    /**
     * 
     * @type {string}
     * @memberof SLOStatusResponse
     */
    generatedAt: string;
    /**
     * 
     * @type {Array<SLOServiceStatus>}
     * @memberof SLOStatusResponse
     */
    services: Array<SLOServiceStatus>;
}
/**
 * One audit event taken verbatim from the immutable audit trail.
 * @export
 * @interface TraceEvent
 */
export interface TraceEvent {
    /**
     * 
     * @type {string}
     * @memberof TraceEvent
     */
    eventType: string;
    /**
     * 
     * @type {string}
     * @memberof TraceEvent
     */
    action: string;
    /**
     * 
     * @type {string}
     * @memberof TraceEvent
     */
    outcome: string;
    /**
     * 
     * @type {number}
     * @memberof TraceEvent
     */
    riskScore?: number;
    /**
     * 
     * @type {string}
     * @memberof TraceEvent
     */
    traceId?: string;
    /**
     * 
     * @type {string}
     * @memberof TraceEvent
     */
    occurredAt: string;
}
