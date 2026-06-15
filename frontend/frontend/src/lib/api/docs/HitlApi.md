# HitlApi

All URIs are relative to *http://localhost:8000*

| Method | HTTP request | Description |
|------------- | ------------- | -------------|
| [**hitlStatus**](HitlApi.md#hitlstatus) | **GET** /v1/hitl/status | HITL subsystem health and queue depth |
| [**listPendingRequests**](HitlApi.md#listpendingrequests) | **GET** /v1/hitl/requests | List pending HITL approval requests |
| [**submitDecision**](HitlApi.md#submitdecision) | **POST** /v1/hitl/requests/{request_id}/decision | Submit an APPROVE or REJECT decision |



## hitlStatus

> HITLStatusResponse hitlStatus()

HITL subsystem health and queue depth

### Example

```ts
import {
  Configuration,
  HitlApi,
} from '';
import type { HitlStatusRequest } from '';

async function example() {
  console.log("🚀 Testing  SDK...");
  const api = new HitlApi();

  try {
    const data = await api.hitlStatus();
    console.log(data);
  } catch (error) {
    console.error(error);
  }
}

// Run the test
example().catch(console.error);
```

### Parameters

This endpoint does not need any parameter.

### Return type

[**HITLStatusResponse**](HITLStatusResponse.md)

### Authorization

No authorization required

### HTTP request headers

- **Content-Type**: Not defined
- **Accept**: `application/json`


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
| **200** | HITL operational status |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#api-endpoints) [[Back to Model list]](../README.md#models) [[Back to README]](../README.md)


## listPendingRequests

> Array&lt;HITLRequestSummary&gt; listPendingRequests(limit, offset)

List pending HITL approval requests

Returns the pending requests awaiting an operator decision. Requires an operator JWT (role hitl-operator). Only the PII-masked context_summary is exposed per request; raw action_parameters never leave the gateway. Paginated (SPEC-API-003): optional limit/offset; X-Total-Count and an RFC-5988 Link header are always set. The body remains an array (backward-compatible).

### Example

```ts
import {
  Configuration,
  HitlApi,
} from '';
import type { ListPendingRequestsRequest } from '';

async function example() {
  console.log("🚀 Testing  SDK...");
  const api = new HitlApi();

  const body = {
    // number | Page size (1–200). Defaults to the full queue. (optional)
    limit: 56,
    // number | Zero-based index of the first item to return. (optional)
    offset: 56,
  } satisfies ListPendingRequestsRequest;

  try {
    const data = await api.listPendingRequests(body);
    console.log(data);
  } catch (error) {
    console.error(error);
  }
}

// Run the test
example().catch(console.error);
```

### Parameters


| Name | Type | Description  | Notes |
|------------- | ------------- | ------------- | -------------|
| **limit** | `number` | Page size (1–200). Defaults to the full queue. | [Optional] [Defaults to `undefined`] |
| **offset** | `number` | Zero-based index of the first item to return. | [Optional] [Defaults to `0`] |

### Return type

[**Array&lt;HITLRequestSummary&gt;**](HITLRequestSummary.md)

### Authorization

No authorization required

### HTTP request headers

- **Content-Type**: Not defined
- **Accept**: `application/json`


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
| **200** | Pending HITL requests (a page) |  * X-Total-Count - Total number of pending requests (before paging). <br>  * Link - RFC-5988 pagination links (rel&#x3D;\&quot;next\&quot;/\&quot;prev\&quot;), when further pages exist. <br>  |
| **422** | Invalid pagination parameters |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#api-endpoints) [[Back to Model list]](../README.md#models) [[Back to README]](../README.md)


## submitDecision

> DecisionOut submitDecision(requestId, decisionIn)

Submit an APPROVE or REJECT decision

### Example

```ts
import {
  Configuration,
  HitlApi,
} from '';
import type { SubmitDecisionRequest } from '';

async function example() {
  console.log("🚀 Testing  SDK...");
  const api = new HitlApi();

  const body = {
    // string
    requestId: 38400000-8cf0-11bd-b23e-10b96e4ef00d,
    // DecisionIn
    decisionIn: ...,
  } satisfies SubmitDecisionRequest;

  try {
    const data = await api.submitDecision(body);
    console.log(data);
  } catch (error) {
    console.error(error);
  }
}

// Run the test
example().catch(console.error);
```

### Parameters


| Name | Type | Description  | Notes |
|------------- | ------------- | ------------- | -------------|
| **requestId** | `string` |  | [Defaults to `undefined`] |
| **decisionIn** | [DecisionIn](DecisionIn.md) |  | |

### Return type

[**DecisionOut**](DecisionOut.md)

### Authorization

No authorization required

### HTTP request headers

- **Content-Type**: `application/json`
- **Accept**: `application/json`


### HTTP response details
| Status code | Description | Response headers |
|-------------|-------------|------------------|
| **200** | Decision recorded |  -  |
| **404** | Request not found or no longer pending |  -  |
| **422** | Validation error |  -  |

[[Back to top]](#) [[Back to API list]](../README.md#api-endpoints) [[Back to Model list]](../README.md#models) [[Back to README]](../README.md)

