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

